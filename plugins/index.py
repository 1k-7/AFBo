import time
import asyncio
import re
import os
import json
import requests
from hydrogram import Client, filters, enums, StopPropagation
from hydrogram.errors import FloodWait, MessageNotModified
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from info import ADMINS, INDEX_EXTENSIONS, LOG_CHANNEL, API_ID, API_HASH, DATABASE_FILE
from database.users_chats_db import db as data_db
from utils import temp, get_readable_time, get_size
import aiosqlite
import logging

logger = logging.getLogger(__name__)

# Standard Index Globals
index_queue = []
is_indexing = False
current_index_job = None

# Smart & Multi Index Globals
smart_index_state = {}
smart_queue = []
is_smart_indexing = False
active_smart_jobs = {} 

class UserbotPool:
    def __init__(self, sessions, api_id, api_hash, main_bot=None):
        self.sessions = sessions
        self.api_id = api_id
        self.api_hash = api_hash
        self.clients = []
        self.cooldowns = {}
        self.floodwaits = {}
        self.main_bot = main_bot
        
        if main_bot:
            self.clients.append(main_bot)
            self.cooldowns[main_bot] = 0
            self.floodwaits['Main Bot'] = 0

    async def start_all(self):
        count = 0
        for s in self.sessions:
            try:
                c = Client(f"helper_{count}", session_string=s, api_id=self.api_id, api_hash=self.api_hash, in_memory=True)
                await c.start()
                self.clients.append(c)
                self.cooldowns[c] = 0
                self.floodwaits[f"Helper {count+1}"] = 0
                count += 1
            except Exception as e:
                logger.error(f"Failed to start userbot: {e}")
        return count

    def get_client(self):
        now = time.time()
        helpers = [c for c in self.clients if c != self.main_bot and self.cooldowns.get(c, 0) <= now]
        if helpers:
            c = helpers[0]
            self.clients.remove(c)
            self.clients.append(c)
            return c, 0
            
        if self.main_bot and self.cooldowns.get(self.main_bot, 0) <= now:
            return self.main_bot, 0
            
        min_client = min(self.clients, key=lambda c: self.cooldowns.get(c, 0))
        wait_time = self.cooldowns[min_client] - now
        return min_client, max(0, wait_time)

    def set_cooldown(self, client, wait_seconds):
        self.cooldowns[client] = time.time() + wait_seconds
        if client == self.main_bot:
            self.floodwaits['Main Bot'] += 1
        else:
            try:
                idx = self.clients.index(client)
                self.floodwaits[f"Helper {idx}"] += 1
            except:
                pass

    async def join_chat(self, invite_link):
        for c in self.clients:
            try: await c.join_chat(invite_link)
            except: pass

    async def stop_all(self, main_bot=None):
        for c in self.clients:
            if c != main_bot:
                try: await c.stop()
                except: pass


def send_error_log(token, text):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": LOG_CHANNEL, "text": f"⚠️ <b>Indexing Error:</b>\n{text}", "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=5)
    except Exception: pass

def get_multi_db_path(bot_username):
    db_dir = os.path.dirname(DATABASE_FILE) or "."
    return os.path.join(db_dir, f"multi_{bot_username}.db")

async def init_custom_db(db_path):
    async with aiosqlite.connect(db_path) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS files (
                file_id TEXT PRIMARY KEY,
                file_name TEXT,
                file_size INTEGER,
                caption TEXT
            )
        ''')
        await db.execute('CREATE INDEX IF NOT EXISTS idx_file_name ON files(file_name)')
        await db.commit()

async def fast_db_save(db_path, media_list, replace=False):
    saved = dup = err = 0
    await init_custom_db(db_path)
    
    async with aiosqlite.connect(db_path) as db:
        for media in media_list:
            file_id = media.file_id
            if not file_id:
                err += 1; continue
            
            raw_file_name = str(media.file_name) if getattr(media, 'file_name', None) else "UnknownFile"
            file_name = re.sub(r"[@\(\)\[\]]", "", raw_file_name.strip())
            file_name = re.sub(r"(_|\-|\.|\+)+", " ", file_name)
            file_name = re.sub(r'\s+', ' ', file_name).strip()
            
            caption_text = str(media.caption) if getattr(media, 'caption', None) else ""
            file_caption = re.sub(r"@\w+|(_|\-|\.|\+)|https?://\S+", " ", caption_text).strip()
            file_caption = re.sub(r'\s+', ' ', file_caption)
            file_size = getattr(media, 'file_size', 0) or 0
            
            if replace:
                await db.execute('DELETE FROM files WHERE file_name = ? AND file_size = ?', (file_name, file_size))
            else:
                async with db.execute('SELECT 1 FROM files WHERE file_name = ? AND file_size = ?', (file_name, file_size)) as cursor:
                    if await cursor.fetchone():
                        dup += 1; continue
            try:
                await db.execute('INSERT INTO files (file_id, file_name, file_size, caption) VALUES (?, ?, ?, ?)', (file_id, file_name, file_size, file_caption))
                saved += 1
            except aiosqlite.IntegrityError:
                dup += 1
            except Exception:
                err += 1
        await db.commit()
    return saved, dup, err

# ================================
# SMART & MULTI INDEX ENGINE
# ================================

@Client.on_message(filters.command('indexhelper') & filters.user(ADMINS))
async def add_helper(client, message):
    try: session_str = message.text.split(" ", 1)[1].strip()
    except: return await message.reply("Usage: `/indexhelper session_string_here`")
    stg = await data_db.get_bot_sttgs()
    sessions = stg.get("INDEX_SESSIONS", [])
    sessions.append(session_str)
    await data_db.update_bot_sttgs("INDEX_SESSIONS", sessions)
    await message.reply(f"✔️ Helper session added! Total helpers: {len(sessions)}")

@Client.on_message(filters.command(['smartindex', 'multiindex']) & filters.private & filters.user(ADMINS))
async def init_smart_index(client, message):
    user_id = message.from_user.id
    cmd = message.command[0]
    
    data = {'type': cmd}
    if cmd == 'multiindex':
        try: tokens = message.text.split(" ", 1)[1].split(",")
        except: return await message.reply("Usage: `/multiindex token1,token2`")
        data['tokens'] = [t.strip() for t in tokens if t.strip()]
        
    smart_index_state[user_id] = data
    await message.reply("➡️ Forward a message from the target channel or send its link.")

# Added group=-1 to ensure this runs BEFORE the auto-filter in group 0
@Client.on_message(filters.private & filters.user(ADMINS) & ~filters.command(["smartindex", "multiindex", "index", "indexhelper", "exportmulti", "importmulti", "start", "help", "stats", "export", "import", "delete", "index_channels"]), group=-1)
async def process_smart_index_state(client, message):
    user_id = message.from_user.id
    if user_id not in smart_index_state: 
        return # Not in state, allow other handlers to process normally
    
    state = smart_index_state[user_id]
    step = state.get('step', 'get_channel')
    
    if step == 'get_channel':
        text = message.text
        chat_id, last_msg_id = None, None
        
        if text and "t.me/" in text:
            match = re.search(r"t\.me/(?:c/)?([^/]+)/(\d+)", text)
            if match:
                chat_id_str = match.group(1)
                last_msg_id = int(match.group(2))
                chat_id = int(f"-100{chat_id_str}") if chat_id_str.isdigit() else (chat_id_str if chat_id_str.startswith("@") else f"@{chat_id_str}")
            else: 
                await message.reply("❌ Invalid link format.")
                raise StopPropagation
        elif message.forward_from_chat and message.forward_from_chat.type == enums.ChatType.CHANNEL:
            last_msg_id = message.forward_from_message_id
            chat_id = message.forward_from_chat.id
        else: 
            await message.reply("❌ Invalid channel message or link.")
            raise StopPropagation

        try:
            chat = await client.get_chat(chat_id)
            chat_name = chat.title
            chat_id = chat.id 
        except Exception as e:
            await message.reply(f"❌ Cannot access chat: `{e}`")
            raise StopPropagation

        state['chat_id'] = chat_id
        state['chat_name'] = chat_name
        state['last_msg_id'] = last_msg_id
        state['step'] = 'get_offset'
        
        await message.reply(f"**Target:** {chat_name}\n\n🔢 Enter the **Message ID** to start from (Offset) to resume progress, or type `0` to start from the beginning.")
        raise StopPropagation # Crucial: Destroy the message before Auto-Filter sees it

    elif step == 'get_offset':
        try: offset_val = int(message.text.strip())
        except ValueError: 
            await message.reply("❌ Invalid offset. Please enter a valid number (e.g., `0`).")
            raise StopPropagation
            
        state['offset'] = offset_val
        state['step'] = 'get_json'
        
        btn = [[InlineKeyboardButton("❌ No JSON (Scan & Index Dynamically)", callback_data=f"no_json_{user_id}")]]
        await message.reply(f"**Target:** {state['chat_name']}\n**Offset:** {offset_val}\n\nSend the JSON backup file if you have it. Otherwise, click the button below to scan and index on the fly.", reply_markup=InlineKeyboardMarkup(btn))
        raise StopPropagation 

    elif step == 'get_json':
        if message.document and message.document.file_name.endswith('.json'):
            file_path = await message.download()
            try:
                with open(file_path, 'r') as f:
                    raw_valid_ids = json.load(f)
                os.remove(file_path)
                
                offset = state.get('offset', 0)
                valid_ids = [vid for vid in raw_valid_ids if vid >= offset]
                state['valid_ids'] = valid_ids
                
                job_id = str(time.time()).replace(".", "")
                smart_queue.append({"job_id": job_id, "user_id": user_id, "state": state, "message": message, "mode": "json"})
                queue_pos = len(smart_queue)
                
                btn = [[InlineKeyboardButton("🔄 Update Status", callback_data=f"smart_status_{job_id}")],
                       [InlineKeyboardButton("❌ Cancel", callback_data=f"smart_cancel_{job_id}")]]
                await message.reply(f"✅ Added to Smart Queue! Position: {queue_pos}\nTarget: {state['chat_name']}", reply_markup=InlineKeyboardMarkup(btn))
                
                if not is_smart_indexing:
                    asyncio.create_task(process_smart_queue(client))
                    
            except Exception as e:
                await message.reply(f"❌ Error reading JSON: {e}")
            del smart_index_state[user_id]
        else:
            await message.reply("Please send a valid JSON file, or click the button above.")
        raise StopPropagation

    raise StopPropagation

@Client.on_callback_query(filters.regex(r'^no_json_'))
async def handle_no_json(bot, query: CallbackQuery):
    user_id = query.from_user.id
    if user_id not in smart_index_state: return await query.answer("State expired.", show_alert=True)
    
    state = smart_index_state[user_id]
    
    job_id = str(time.time()).replace(".", "")
    smart_queue.append({"job_id": job_id, "user_id": user_id, "state": state, "message": query.message, "mode": "scan"})
    queue_pos = len(smart_queue)
    
    btn = [[InlineKeyboardButton("🔄 Update Status", callback_data=f"smart_status_{job_id}")],
           [InlineKeyboardButton("❌ Cancel", callback_data=f"smart_cancel_{job_id}")]]
    await query.message.edit(f"✅ Added to Smart Queue! Position: {queue_pos}\nTarget: {state['chat_name']}", reply_markup=InlineKeyboardMarkup(btn))
    
    if not is_smart_indexing:
        asyncio.create_task(process_smart_queue(bot))
        
    del smart_index_state[user_id]

async def process_smart_queue(bot):
    global is_smart_indexing, smart_queue
    if is_smart_indexing: return
    is_smart_indexing = True
    
    while smart_queue:
        job = smart_queue.pop(0)
        try:
            if job['mode'] == 'json':
                await execute_smart_multi_index(bot, job['message'], job['state'], job['user_id'], job['job_id'])
            else:
                await execute_smart_scan_and_index(bot, job['message'], job['state'], job['user_id'], job['job_id'])
        except Exception as e:
            logger.error(f"Smart job failed: {e}")
            
    is_smart_indexing = False


async def execute_smart_scan_and_index(bot, message, state, user_id, job_id):
    chat_id = state['chat_id']
    chat_name = state['chat_name']
    last_msg_id = state['last_msg_id']
    job_type = state['type']
    offset = state.get('offset', 1)
    if offset <= 0: offset = 1
    
    stg = await data_db.get_bot_sttgs()
    sessions = stg.get("INDEX_SESSIONS", [])
    sec_token = stg.get('SECONDARY_BOT_TOKEN')
    
    pool = UserbotPool(sessions, API_ID, API_HASH, main_bot=bot)
    helpers_count = await pool.start_all()
    
    if helpers_count > 0:
        try:
            invite_link = await bot.create_chat_invite_link(chat_id)
            await pool.join_chat(invite_link.invite_link)
        except Exception: pass

    sub_bots = []
    stats_dict = {}
    
    if job_type == 'smartindex':
        stats_dict["Main Bot"] = {"saved": 0, "dup": 0, "err": 0, "fw": 0, "start_time": time.time()}
    elif job_type == 'multiindex':
        tokens = state['tokens']
        for token in tokens:
            try:
                b = Client(f"sub_{token.split(':')[0]}", bot_token=token, api_id=API_ID, api_hash=API_HASH, in_memory=True)
                await b.start()
                sub_bots.append(b)
                stats_dict[b.me.username] = {"saved": 0, "dup": 0, "err": 0, "fw": 0, "start_time": time.time()}
            except Exception as e:
                await message.reply(f"❌ Failed to start sub-bot: {e}")
        if not sub_bots:
            await pool.stop_all(main_bot=bot)
            return await message.edit("❌ No active sub-bots. Aborting.")

    total_msgs = max(1, last_msg_id - offset + 1)
    bot_queues = {'main': asyncio.Queue()} if job_type == 'smartindex' else {b: asyncio.Queue() for b in sub_bots}
    
    all_valid_ids = []

    active_smart_jobs[job_id] = {
        "user_id": user_id,
        "chat_name": chat_name,
        "chat_id": chat_id,
        "job_type": job_type,
        "start_time": time.time(),
        "total_msgs": total_msgs,
        "last_msg_id": last_msg_id,
        "highest_msg_id": offset,
        "msgs_processed": 0,
        "scanned_files": 0,
        "pool": pool,
        "helpers": helpers_count,
        "sub_bots": len(sub_bots),
        "bot_queues": bot_queues,
        "stats": stats_dict,
        "cancel": False,
        "scanner_done": False,
        "mode": "Dynamic Scan & Save"
    }
    
    btn = [[InlineKeyboardButton("🔄 Update Status", callback_data=f"smart_status_{job_id}")],
           [InlineKeyboardButton("❌ Cancel", callback_data=f"smart_cancel_{job_id}")]]
    sts = await message.reply(f"🚀 **Started Parallel Indexing**\n**Target:** {chat_name}\n\nClick 'Update Status' below to view progress.", reply_markup=InlineKeyboardMarkup(btn))
    
    chunk_queue = asyncio.Queue()
    chunk_size = 200
    for i in range(offset, last_msg_id + 1, chunk_size):
        chunk_queue.put_nowait((i, min(i + chunk_size - 1, last_msg_id)))

    collector_queue = asyncio.Queue()

    # 1. SCANNER WORKER
    async def scanner_worker(client):
        while not chunk_queue.empty():
            if active_smart_jobs[job_id]["cancel"]: break
            try: start_id, end_id = chunk_queue.get_nowait()
            except asyncio.QueueEmpty: break
                
            while True:
                if active_smart_jobs[job_id]["cancel"]: break
                try:
                    msgs = await client.get_messages(chat_id, list(range(start_id, end_id + 1)))
                    valid_for_chunk = []
                    for m in msgs:
                        if m.empty: continue
                        if m.media and m.media in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT]:
                            media = getattr(m, m.media.value, None)
                            if media and getattr(media, 'file_name', None):
                                if any(media.file_name.lower().endswith(ext) for ext in INDEX_EXTENSIONS):
                                    valid_for_chunk.append(m.id)
                    
                    if valid_for_chunk:
                        await collector_queue.put(valid_for_chunk)
                    
                    active_smart_jobs[job_id]["msgs_processed"] += (end_id - start_id + 1)
                    active_smart_jobs[job_id]["highest_msg_id"] = max(active_smart_jobs[job_id]["highest_msg_id"], end_id)
                    chunk_queue.task_done()
                    break 
                except FloodWait as e:
                    pool.set_cooldown(client, e.value)
                    await asyncio.sleep(e.value + 1)
                except Exception:
                    active_smart_jobs[job_id]["msgs_processed"] += (end_id - start_id + 1)
                    active_smart_jobs[job_id]["highest_msg_id"] = max(active_smart_jobs[job_id]["highest_msg_id"], end_id)
                    chunk_queue.task_done()
                    break

    # 2. COLLECTOR WORKER
    async def collector_worker():
        buffer = []
        while True:
            try:
                chunk_valid_ids = await asyncio.wait_for(collector_queue.get(), timeout=1.0)
                if chunk_valid_ids is None: break 
                
                buffer.extend(chunk_valid_ids)
                active_smart_jobs[job_id]["scanned_files"] += len(chunk_valid_ids)
                all_valid_ids.extend(chunk_valid_ids) 
                
                while len(buffer) >= 200:
                    batch = buffer[:200]
                    buffer = buffer[200:]
                    if job_type == 'smartindex': await bot_queues['main'].put(batch)
                    elif job_type == 'multiindex':
                        for b in sub_bots: await bot_queues[b].put(batch)
                
                collector_queue.task_done()
            except asyncio.TimeoutError:
                if active_smart_jobs[job_id]["scanner_done"]: break

        if buffer:
            if job_type == 'smartindex': await bot_queues['main'].put(buffer)
            elif job_type == 'multiindex':
                for b in sub_bots: await bot_queues[b].put(buffer)

    # 3. DATABASE SAVER WORKER
    async def saver_worker(client, db_path, bot_name):
        while True:
            batch = await bot_queues[client if job_type == 'multiindex' else 'main'].get()
            if batch is None: break
            
            while True:
                if active_smart_jobs[job_id]["cancel"]: break
                try:
                    msgs = await client.get_messages(chat_id, batch)
                    media_list = [getattr(m, m.media.value, None) for m in msgs if not m.empty and m.media]
                    media_list = [m for m in media_list if m]
                    
                    if media_list:
                        s, d, e = await fast_db_save(db_path, media_list, replace=False)
                        active_smart_jobs[job_id]["stats"][bot_name]["saved"] += s
                        active_smart_jobs[job_id]["stats"][bot_name]["dup"] += d
                        active_smart_jobs[job_id]["stats"][bot_name]["err"] += e
                    break
                except FloodWait as e:
                    active_smart_jobs[job_id]["stats"][bot_name]["fw"] += 1
                    await asyncio.sleep(e.value + 1)
                except Exception:
                    break
            bot_queues[client if job_type == 'multiindex' else 'main'].task_done()

    # Execution 
    active_scanners = pool.clients if pool.clients else [bot]
    scanner_tasks = [asyncio.create_task(scanner_worker(c)) for c in active_scanners]
    collector_task = asyncio.create_task(collector_worker())
    
    saver_tasks = []
    if job_type == 'smartindex':
        saver_tasks.append(asyncio.create_task(saver_worker(bot, DATABASE_FILE, "Main Bot")))
    elif job_type == 'multiindex':
        for b in sub_bots:
            saver_tasks.append(asyncio.create_task(saver_worker(b, get_multi_db_path(b.me.username), b.me.username)))

    await chunk_queue.join()
    for task in scanner_tasks: task.cancel()
    
    active_smart_jobs[job_id]["scanner_done"] = True
    await collector_task
    
    if job_type == 'smartindex': bot_queues['main'].put_nowait(None)
    elif job_type == 'multiindex':
        for b in sub_bots: bot_queues[b].put_nowait(None)
        
    await asyncio.gather(*saver_tasks)

    # Compile Final Complete Summary Message Details
    elapsed_total = time.time() - active_smart_jobs[job_id]["start_time"]
    status_str = "🛑 Multi-Index Job Cancelled" if active_smart_jobs[job_id]["cancel"] else "✔️ Multi-Index Job Completed Successfully"
    
    summary_text = f"<b>{status_str}!</b>\n\n"
    summary_text += f"<b>Chat Target:</b> {chat_name} (<code>{chat_id}</code>)\n"
    summary_text += f"<b>Total Messages Scanned:</b> {active_smart_jobs[job_id]['msgs_processed']}\n"
    summary_text += f"<b>Total Valid Media Found:</b> {len(all_valid_ids)}\n"
    summary_text += f"<b>Total Time Taken:</b> {get_readable_time(elapsed_total)}\n\n"
    summary_text += "<b>📊 Final Breakdown Across Bots:</b>\n"
    
    for b_name, b_stats in active_smart_jobs[job_id]["stats"].items():
        db_path = DATABASE_FILE if job_type == 'smartindex' else get_multi_db_path(b_name)
        size_str = get_size(os.path.getsize(db_path)) if os.path.exists(db_path) else "0 B"
        summary_text += f"🤖 <b>{b_name}</b>\n"
        summary_text += f" ├ Saved: {b_stats['saved']} | Duplicates: {b_stats['dup']} | Errors: {b_stats['err']}\n"
        summary_text += f" └ Rate Limits Faced: {b_stats['fw']} FWs | Database Size: {size_str}\n\n"

    await sts.edit(summary_text)

    # Generate JSON Arrays file
    await pool.stop_all(main_bot=bot)
    for b in sub_bots:
        try: await b.stop()
        except: pass
        
    safe_chat_name = re.sub(r'[\\/*?:"<>|]', "", chat_name).strip()
    json_file = f"{safe_chat_name}_{chat_id}.json".replace(" ", "_")
    with open(json_file, "w") as f:
        all_valid_ids.sort()
        json.dump(all_valid_ids, f)
        
    await message.reply_document(json_file, caption=f"📦 Verification Array generated for {chat_name}!")
    os.remove(json_file)
    del active_smart_jobs[job_id]


async def execute_smart_multi_index(client, message, state, user_id, job_id):
    valid_ids = state['valid_ids']
    chat_id = state['chat_id']
    chat_name = state['chat_name']
    job_type = state['type']
    
    if not valid_ids:
        return await message.reply("❌ No valid files to index.")
        
    stg = await data_db.get_bot_sttgs()
    
    sub_bots = []
    stats_dict = {}
    
    if job_type == 'smartindex':
        stats_dict["Main Bot"] = {"saved": 0, "dup": 0, "err": 0, "fw": 0, "start_time": time.time()}
        sessions = stg.get("INDEX_SESSIONS", [])
        pool = UserbotPool(sessions, API_ID, API_HASH, main_bot=client)
    elif job_type == 'multiindex':
        pool = None
        tokens = state['tokens']
        for token in tokens:
            try:
                b = Client(f"sub_{token.split(':')[0]}", bot_token=token, api_id=API_ID, api_hash=API_HASH, in_memory=True)
                await b.start()
                sub_bots.append(b)
                stats_dict[b.me.username] = {"saved": 0, "dup": 0, "err": 0, "fw": 0, "start_time": time.time()}
            except Exception as e:
                await message.reply(f"❌ Failed to start sub-bot: {e}")
        if not sub_bots:
            return await message.reply("❌ No active sub-bots. Aborting.")
            
    bot_queues = {'main': asyncio.Queue()} if job_type == 'smartindex' else {b: asyncio.Queue() for b in sub_bots}
            
    active_smart_jobs[job_id] = {
        "user_id": user_id,
        "chat_name": chat_name,
        "chat_id": chat_id,
        "job_type": job_type,
        "start_time": time.time(),
        "total_msgs": len(valid_ids), 
        "msgs_processed": 0,
        "scanned_files": len(valid_ids), 
        "pool": pool,
        "sub_bots": len(sub_bots),
        "bot_queues": bot_queues,
        "stats": stats_dict,
        "cancel": False,
        "scanner_done": True, 
        "mode": "JSON Parallel Batch Fetch"
    }

    btn = [[InlineKeyboardButton("🔄 Update Status", callback_data=f"smart_status_{job_id}")],
           [InlineKeyboardButton("❌ Cancel", callback_data=f"smart_cancel_{job_id}")]]
    sts = await message.reply(f"🚀 **Started JSON Indexing**\n**Target:** {chat_name}\n\nClick 'Update Status' below to view progress.", reply_markup=InlineKeyboardMarkup(btn))
    
    saver_tasks = []

    async def saver_worker(worker_client, db_path, bot_name):
        while True:
            batch = await bot_queues[worker_client if job_type == 'multiindex' else 'main'].get()
            if batch is None: break
            
            while True:
                if active_smart_jobs[job_id]["cancel"]: break
                try:
                    msgs = await worker_client.get_messages(chat_id, batch)
                    media_list = [getattr(m, m.media.value, None) for m in msgs if not m.empty and m.media]
                    media_list = [m for m in media_list if m]
                    
                    if media_list:
                        s, d, e = await fast_db_save(db_path, media_list, replace=False)
                        active_smart_jobs[job_id]["stats"][bot_name]["saved"] += s
                        active_smart_jobs[job_id]["stats"][bot_name]["dup"] += d
                        active_smart_jobs[job_id]["stats"][bot_name]["err"] += e
                    break
                except FloodWait as e:
                    active_smart_jobs[job_id]["stats"][bot_name]["fw"] += 1
                    await asyncio.sleep(e.value + 1)
                except Exception:
                    break
            
            active_smart_jobs[job_id]["msgs_processed"] += (len(batch) if job_type == 'smartindex' else (len(batch) / len(sub_bots)))
            bot_queues[worker_client if job_type == 'multiindex' else 'main'].task_done()

    if job_type == 'smartindex':
        saver_tasks.append(asyncio.create_task(saver_worker(client, DATABASE_FILE, "Main Bot")))
    elif job_type == 'multiindex':
        for b in sub_bots:
            saver_tasks.append(asyncio.create_task(saver_worker(b, get_multi_db_path(b.me.username), b.me.username)))

    for i in range(0, len(valid_ids), 200):
        if active_smart_jobs[job_id]["cancel"]: break
        chunk = valid_ids[i:i+200]
        if job_type == 'smartindex': bot_queues['main'].put_nowait(chunk)
        elif job_type == 'multiindex':
            for b in sub_bots: bot_queues[b].put_nowait(chunk)

    if job_type == 'smartindex': bot_queues['main'].put_nowait(None)
    elif job_type == 'multiindex':
        for b in sub_bots: bot_queues[b].put_nowait(None)

    await asyncio.gather(*saver_tasks)

    # Post-Execution Final Complete Summary Edit
    elapsed_total = time.time() - active_smart_jobs[job_id]["start_time"]
    status_str = "🛑 JSON Indexing Cancelled" if active_smart_jobs[job_id]["cancel"] else "✔️ JSON Indexing Job Completed Successfully"
    
    summary_text = f"<b>{status_str}!</b>\n\n"
    summary_text += f"<b>Chat Target:</b> {chat_name} (<code>{chat_id}</code>)\n"
    summary_text += f"<b>Total Backed up Files Extracted:</b> {len(valid_ids)}\n"
    summary_text += f"<b>Total Time Taken:</b> {get_readable_time(elapsed_total)}\n\n"
    summary_text += "<b>📊 Final Breakdown Across Bots:</b>\n"
    
    for b_name, b_stats in active_smart_jobs[job_id]["stats"].items():
        db_path = DATABASE_FILE if job_type == 'smartindex' else get_multi_db_path(b_name)
        size_str = get_size(os.path.getsize(db_path)) if os.path.exists(db_path) else "0 B"
        summary_text += f"🤖 <b>{b_name}</b>\n"
        summary_text += f" ├ Saved: {b_stats['saved']} | Duplicates: {b_stats['dup']} | Errors: {b_stats['err']}\n"
        summary_text += f" └ Rate Limits Faced: {b_stats['fw']} FWs | Database Size: {size_str}\n\n"

    await sts.edit(summary_text)

    if job_type == 'multiindex':
        for b in sub_bots:
            try: await b.stop()
            except: pass
    del active_smart_jobs[job_id]


# Status Button Callback for Smart/Multi Indexing
@Client.on_callback_query(filters.regex(r"^smart_status_"))
async def smart_status_update(bot, query: CallbackQuery):
    job_id = query.data.split("_")[2]
    
    if job_id not in active_smart_jobs:
        for idx, job in enumerate(smart_queue):
            if job['job_id'] == job_id:
                return await query.answer(f"Job is currently in Queue.\nPosition: {idx + 1}", show_alert=True)
        return await query.answer("No active process.", show_alert=True)
    
    state = active_smart_jobs[job_id]
    elapsed = time.time() - state["start_time"]
    
    # Accurate Cumulative DB Metrics to figure overall execution status
    total_saved_across_bots = sum(b_info['saved'] for b_info in state['stats'].values())
    total_dups_across_bots = sum(b_info['dup'] for b_info in state['stats'].values())
    processed_files_combined = total_saved_across_bots + total_dups_across_bots
    
    # Target values adjust dynamically based on processing modes
    expected_total_operations = state['scanned_files'] * state['sub_bots'] if state['mode'] == "Dynamic Scan & Save" else state['total_msgs'] * state['sub_bots']
    
    overall_percent = (processed_files_combined / expected_total_operations * 100) if expected_total_operations > 0 else 0
    
    overall_eta = 0
    if processed_files_combined > 0 and elapsed > 0:
        speed = processed_files_combined / elapsed
        rem = expected_total_operations - processed_files_combined
        overall_eta = rem / speed if speed > 0 else 0

    text = f"🚀 <b>{state['mode']} In Progress</b>\n"
    text += f"<b>Chat:</b> {state['chat_name']} (<code>{state['chat_id']}</code>)\n\n"
    
    text += f"<b>Overall Save Progress:</b> {overall_percent:.1f}%\n"
    text += f"<b>Overall ETA:</b> {get_readable_time(overall_eta)}\n"
    text += f"<b>Time Elapsed:</b> {get_readable_time(elapsed)}\n\n"
    
    if state['mode'] == "Dynamic Scan & Save":
        scan_progress = int(state["msgs_processed"])
        scan_total = state["total_msgs"]
        scan_percent = (scan_progress / scan_total * 100) if scan_total > 0 else 0
        text += f"<b>Scanner Matrix:</b> {scan_progress} / {scan_total} ({scan_percent:.1f}%)\n"
        text += f"<b>Latest Msg ID:</b> {state.get('highest_msg_id', 0)} / {state.get('last_msg_id', 0)}\n"
        text += f"<b>Valid Media Found:</b> {state['scanned_files']}\n"
        
        pool = state.get('pool')
        if pool:
            fw_list = [f"{k.replace('helper_', ''):>2}: {v} FW" for k, v in pool.floodwaits.items() if k != 'Main Bot']
            text += f"<b>Helper Stats:</b>\n"
            text += f" Main Bot: {pool.floodwaits.get('Main Bot', 0)} FW\n"
            text += f" Helpers ->  " + "  |  ".join(fw_list) + "\n\n"
    else:
        text += f"<b>Source Array Size:</b> {state['total_msgs']} structural file entries\n\n"
        
    text += "<b>📊 Connected Bots Performance:</b>\n"
    for bot_name, stats in state["stats"].items():
        fw = stats.get('fw', 0)
        bot_processed = stats['saved'] + stats['dup']
        bot_target = state['scanned_files'] if state['mode'] == "Dynamic Scan & Save" else state['total_msgs']
        bot_percent = (bot_processed / bot_target * 100) if bot_target > 0 else 0
        
        bot_elapsed = time.time() - stats['start_time']
        bot_eta = 0
        if bot_processed > 0 and bot_elapsed > 0:
            bot_speed = bot_processed / bot_elapsed
            bot_rem = bot_target - bot_processed
            bot_eta = bot_rem / bot_speed if bot_speed > 0 else 0
            
        text += f"🤖 <b>{bot_name}</b> (FW: {fw}) — {bot_percent:.1f}% (ETA: {get_readable_time(bot_eta) if bot_processed < bot_target else 'Done'})\n"
        text += f" ├ Saved: {stats['saved']} | Duplicates: {stats['dup']} | Errors: {stats['err']}\n"
        
        db_size_str = "Unknown"
        try:
            db_path = DATABASE_FILE if state['job_type'] == 'smartindex' else get_multi_db_path(bot_name)
            if os.path.exists(db_path):
                db_size_str = get_size(os.path.getsize(db_path))
        except: pass
        
        pending_files = 0
        if 'bot_queues' in state:
            if state['job_type'] == 'smartindex':
                pending_files = state['bot_queues']['main'].qsize() * 200
            else:
                for b_client, b_queue in state['bot_queues'].items():
                    if getattr(b_client, 'me', None) and b_client.me.username == bot_name:
                        pending_files = b_queue.qsize() * 200
                        break
                        
        text += f" └ Size: {db_size_str} | Queue Buffer: ~{pending_files} remaining\n\n"

    text += f"<b>Queue System:</b> {len(smart_queue)} channel tasks suspended."

    btn = [[InlineKeyboardButton("🔄 Update Status", callback_data=f"smart_status_{job_id}")],
           [InlineKeyboardButton("❌ Cancel", callback_data=f"smart_cancel_{job_id}")]]
           
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))
        await query.answer("Status Metrics Synchronized!", show_alert=False)
    except MessageNotModified:
        await query.answer("No new changes.", show_alert=False)
    except FloodWait as e:
        await query.answer(f"Flood wait... {e.value}s", show_alert=True)

@Client.on_callback_query(filters.regex(r"^smart_cancel_"))
async def smart_cancel_process(bot, query: CallbackQuery):
    job_id = query.data.split("_")[2]
    
    if job_id in active_smart_jobs:
        if query.from_user.id != active_smart_jobs[job_id]['user_id']:
            return await query.answer("Not your process.", show_alert=True)
        active_smart_jobs[job_id]["cancel"] = True
        await query.answer("Cancellation requested...", show_alert=True)
    else:
        for job in smart_queue:
            if job['job_id'] == job_id:
                if query.from_user.id != job['user_id']:
                    return await query.answer("Not your process.", show_alert=True)
                smart_queue.remove(job)
                await query.message.edit("🛑 **Cancelled before starting.** Removed from Queue.")
                return await query.answer("Removed from queue.", show_alert=True)
        await query.answer("Process not found.", show_alert=True)


@Client.on_message(filters.command('exportmulti') & filters.user(ADMINS))
async def export_multi_cmd(client, message):
    db_dir = os.path.dirname(DATABASE_FILE) or "."
    db_files = [f for f in os.listdir(db_dir) if f.startswith("multi_") and f.endswith(".db")]
    if not db_files: return await message.reply("❌ No multi-index DBs found.")
    
    sts = await message.reply("⏳ Converting Multi-DBs to JSON...")
    
    for db_file in db_files:
        full_path = os.path.join(db_dir, db_file)
        try:
            async with aiosqlite.connect(full_path) as sql_db:
                sql_db.row_factory = aiosqlite.Row
                async with sql_db.execute('SELECT file_id as _id, file_name, file_size, caption FROM files') as cursor:
                    rows = await cursor.fetchall()
                    docs = [dict(row) for row in rows]
            
            json_filename = db_file.replace(".db", "_export.json")
            with open(json_filename, "w") as f:
                json.dump(docs, f, indent=4) 
                
            await message.reply_document(
                document=json_filename, 
                caption=f"📦 Export for {db_file}\nTotal Files: {len(docs)}"
            )
            os.remove(json_filename)
        except Exception as e:
            await message.reply(f"❌ Error exporting {db_file}: {e}")
            
    await sts.delete()

@Client.on_message(filters.command('importmulti') & filters.user(ADMINS))
async def import_multi_cmd(client, message):
    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply("Usage: Reply to a multi-index JSON export file with `/importmulti`")
        
    doc = message.reply_to_message.document
    filename = doc.file_name
    
    if not filename or not filename.startswith("multi_") or not filename.endswith(".json"):
        return await message.reply("❌ Unrecognized filename. Must start with 'multi_' and end with '.json'")
        
    target_db = filename.replace("_export.json", ".db").replace(".json", ".db")
    db_dir = os.path.dirname(DATABASE_FILE) or "."
    full_db_path = os.path.join(db_dir, target_db)
    
    msg = await message.reply(f"⏳ Downloading JSON file for `{target_db}`...")
    
    try:
        file_path = await message.reply_to_message.download()
        await msg.edit(f"⏳ Parsing JSON and importing to `{target_db}`. Please wait...")
        
        with open(file_path, "r") as f:
            docs = json.load(f)
            
        if not isinstance(docs, list):
            raise ValueError("JSON file must contain a list of documents.")
            
        await init_custom_db(full_db_path)
            
        success = 0; duplicate = 0; errors = 0
        
        async with aiosqlite.connect(full_db_path) as sql_db:
            for doc_item in docs:
                try:
                    file_id = doc_item.get('_id') or doc_item.get('file_id')
                    file_name = doc_item.get('file_name', '')
                    file_size = doc_item.get('file_size', 0)
                    caption = doc_item.get('caption', '')
                    
                    if not file_id:
                        errors += 1
                        continue
                        
                    await sql_db.execute(
                        'INSERT INTO files (file_id, file_name, file_size, caption) VALUES (?, ?, ?, ?)', 
                        (file_id, file_name, file_size, caption)
                    )
                    success += 1
                except aiosqlite.IntegrityError:
                    duplicate += 1
                except Exception:
                    errors += 1
            await sql_db.commit()

        os.remove(file_path)
        await msg.edit(
            f"✔️ **Import Complete for `{target_db}`**\n\n"
            f"Total Processed: {len(docs)}\n"
            f"Successfully Inserted: {success}\n"
            f"Skipped (Duplicates): {duplicate}\n"
            f"Errors: {errors}"
        )
        
    except Exception as e:
        logger.error(f"ImportMulti Error: {e}", exc_info=True)
        await msg.edit(f"❌ Error during import: {e}")
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)


# ================================
# BASIC INDEX ENGINE 
# ================================

@Client.on_message(filters.command(['index', 'indexrc']) & filters.private & filters.user(ADMINS))
async def send_for_index(bot, message):
    is_replace = (message.command[0] == 'indexrc')
    ask_msg = await message.reply("➡️ Forward the last message from the channel or send the message link.")
    try: response_msg = await bot.listen(chat_id=message.chat.id, user_id=message.from_user.id, timeout=120)
    except asyncio.TimeoutError: return await ask_msg.edit("⏰ Timeout.")
    finally: await ask_msg.delete()

    chat_id, last_msg_id = None, None
    text = response_msg.text

    if text and "t.me/" in text:
        match = re.search(r"t\.me/(?:c/)?([^/]+)/(\d+)", text)
        if match:
            chat_id_str = match.group(1)
            last_msg_id = int(match.group(2))
            if chat_id_str.isdigit(): chat_id = int(f"-100{chat_id_str}")
            else: chat_id = chat_id_str if chat_id_str.startswith("@") else f"@{chat_id_str}"
        else: return await response_msg.reply("❌ Invalid link format.")
    elif response_msg.forward_from_chat and response_msg.forward_from_chat.type == enums.ChatType.CHANNEL:
        last_msg_id = response_msg.forward_from_message_id
        chat_id = response_msg.forward_from_chat.id
    else: return await response_msg.reply("❌ Invalid channel message or link.")

    try:
        chat = await bot.get_chat(chat_id)
        chat_name = chat.title
        chat_id = chat.id 
    except Exception as e: return await response_msg.reply(f"❌ Cannot access chat: `{e}`")

    skip_ask_msg = await message.reply(f"**Target:** {chat_name}\n\n🔢 Enter the Message ID to start from (offset), or 0 to start from the beginning:")
    try: skip_response = await bot.listen(chat_id=message.chat.id, user_id=message.from_user.id, timeout=60)
    except asyncio.TimeoutError: return await skip_ask_msg.edit("⏰ Timeout.")
    finally: await skip_ask_msg.delete()

    skip = int(skip_response.text.strip())
    ident = "replace" if is_replace else "yes"
    btn = [[InlineKeyboardButton("✔️ Start Indexing", callback_data=f'index#{ident}#{chat_id}#{last_msg_id}#{skip}')],
           [InlineKeyboardButton("❌ Cancel", callback_data='close_data')]]
    await skip_response.reply(f"Index {last_msg_id - skip} messages from **{chat_name}** (`{chat_id}`)?", reply_markup=InlineKeyboardMarkup(btn))

@Client.on_callback_query(filters.regex(r'^index#(yes|cancel|replace)'))
async def index_files_callback(bot, query: CallbackQuery):
    global index_queue, is_indexing
    user_id = query.from_user.id
    if user_id not in ADMINS: return await query.answer("Admins only.", show_alert=True)
    parts = query.data.split("#")
    _, ident, chat, lst_msg_id_str, skip_str = parts
    lst_msg_id, skip = int(lst_msg_id_str), int(skip_str)
    try: chat_id = int(chat)
    except: chat_id = chat

    if ident in ['yes', 'replace']:
        replace_mode = (ident == 'replace')
        job_data = {"chat_id": chat_id, "last_msg_id": lst_msg_id, "skip": skip, "replace": replace_mode, "message": query.message}
        index_queue.append(job_data)
        queue_pos = len(index_queue)
        await query.message.edit(f"✅ Added to Indexing Queue! Position: {queue_pos}")
        if not is_indexing: asyncio.create_task(process_index_queue_fallback(bot))
    elif ident == 'cancel':
        temp.CANCEL = True
        await query.answer("Cancellation requested for current job.", show_alert=True)

async def process_index_queue_fallback(bot):
    global index_queue, is_indexing, current_index_job
    if is_indexing: return
    is_indexing = True
    while index_queue:
        job = index_queue.pop(0)
        try: await execute_index_job(bot, job)
        except Exception as e: logger.error(f"Job failed: {e}")
    is_indexing = False
    current_index_job = None

async def execute_index_job(bot, job):
    global current_index_job
    chat_id, lst_msg_id, skip, replace, msg = job["chat_id"], job["last_msg_id"], job["skip"], job["replace"], job["message"]
    try: chat = await bot.get_chat(chat_id); chat_name = chat.title
    except: chat_name = "Unknown"
    current_index_job = {
        "status_message": "Initializing...", "start_time": time.time(), "total_files": 0, "duplicate": 0, "errors": 0, "deleted": 0, 
        "no_media": 0, "unsupported": 0, "current": skip, "total_to_process": lst_msg_id - skip, "last_msg_id": lst_msg_id, 
        "chat_id": chat_id, "chat_name": chat_name, "skip": skip
    }
    btn = [[InlineKeyboardButton("🔄 Update Status", callback_data="index_status")], [InlineKeyboardButton("❌ Cancel Current", callback_data='cancel_current_index')]]
    await msg.edit(f"⏳ **Indexing Started:** {chat_name}\nClick 'Update Status' below.", reply_markup=InlineKeyboardMarkup(btn))
    
    current_id = skip if skip > 0 else 1
    
    try:
        while current_id <= lst_msg_id:
            if temp.CANCEL: break
            
            chunk_size = min(200, lst_msg_id - current_id + 1)
            chunk_ids = list(range(current_id, current_id + chunk_size))
            
            try:
                msgs = await bot.get_messages(chat_id, chunk_ids)
                media_list = []
                for message in msgs:
                    current_index_job["current"] = message.id
                    if message.empty: current_index_job["deleted"] += 1; continue
                    if not message.media or message.media not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT]: current_index_job["unsupported"] += 1; continue
                    media = getattr(message, message.media.value, None)
                    if not media or not getattr(media, 'file_name', None): current_index_job["unsupported"] += 1; continue
                    if not any(media.file_name.lower().endswith(ext) for ext in INDEX_EXTENSIONS): current_index_job["unsupported"] += 1; continue
                    media.caption = message.caption
                    media_list.append(media)
                
                if media_list:
                    s, d, e = await fast_db_save(DATABASE_FILE, media_list, replace=replace)
                    current_index_job["total_files"] += s
                    current_index_job["duplicate"] += d
                    current_index_job["errors"] += e

                current_id += chunk_size
            except FloodWait as e:
                await asyncio.sleep(e.value + 1)
                continue
            except Exception:
                current_id += chunk_size
                
        elapsed = time.time() - current_index_job["start_time"]
        status = "🛑 Cancelled" if temp.CANCEL else "✔️ Completed"
        final_text = f"{status}!\n\n**Chat:** {chat_name} (`{chat_id}`)\n**Processed:** {current_index_job['current'] - skip}\n**Saved:** {current_index_job['total_files']}\n**Duplicates:** {current_index_job['duplicate']}\n**Errors:** {current_index_job['errors']}\n**Time:** {get_readable_time(elapsed)}"
        await msg.edit(final_text)
    except Exception as e:
        logger.exception(f"Fatal indexing error: {e}")
        try: await msg.edit(f'❌ Fatal Error: {e}')
        except: pass
    finally:
        temp.CANCEL = False

@Client.on_callback_query(filters.regex(r"^index_status$"))
async def index_status_update(bot, query: CallbackQuery):
    global current_index_job, index_queue
    if not current_index_job: return await query.answer("No active process.", show_alert=True)
    elapsed = time.time() - current_index_job["start_time"]
    progress = current_index_job["current"] - current_index_job["skip"]
    total = current_index_job["total_to_process"]
    percent = (progress / total * 100) if total > 0 else 0
    text = (f"⏳ **Indexing In Progress**\n**Chat:** {current_index_job['chat_name']} (`{current_index_job['chat_id']}`)\n\n"
            f"**Progress:** {progress}/{total} ({percent:.1f}%)\n**Saved:** {current_index_job['total_files']}\n"
            f"**Duplicates:** {current_index_job['duplicate']}\n**Errors:** {current_index_job['errors']}\n"
            f"**Time Elapsed:** {get_readable_time(elapsed)}\n\n**Queue:** {len(index_queue)} jobs waiting.")
    btn = [[InlineKeyboardButton("🔄 Update Status", callback_data="index_status")], [InlineKeyboardButton("❌ Cancel Current", callback_data='cancel_current_index')]]
    try: await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn)); await query.answer("Status Updated!", show_alert=False)
    except MessageNotModified: await query.answer("No new changes.", show_alert=False)
    except FloodWait as e: await query.answer(f"Flood wait... {e.value}s", show_alert=True)

@Client.on_callback_query(filters.regex(r"^cancel_current_index$"))
async def cancel_current(bot, query: CallbackQuery):
    if query.from_user.id not in ADMINS: return await query.answer("Admins only.", show_alert=True)
    temp.CANCEL = True
    await query.answer("Cancellation requested for the current job.", show_alert=True)
