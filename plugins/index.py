import time
import asyncio
import re
import os
import json
import requests
from hydrogram import Client, filters, enums
from hydrogram.errors import FloodWait, MessageNotModified
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from info import ADMINS, INDEX_EXTENSIONS, LOG_CHANNEL, API_ID, API_HASH, DATABASE_FILE
from database.users_chats_db import db as data_db
from utils import temp, get_readable_time
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
        self.main_bot = main_bot

    async def start_all(self):
        count = 0
        for s in self.sessions:
            try:
                c = Client(f"helper_{count}", session_string=s, api_id=self.api_id, api_hash=self.api_hash, in_memory=True)
                await c.start()
                self.clients.append(c)
                count += 1
            except Exception as e:
                logger.error(f"Failed to start userbot: {e}")
        return count

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

# --- THE BULK SAVE ENGINE ---
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

@Client.on_message(filters.private & filters.user(ADMINS) & ~filters.command(["smartindex", "multiindex", "index", "indexhelper", "exportmulti", "importmulti", "start", "help", "stats", "export", "import", "delete", "index_channels"]))
async def process_smart_index_state(client, message):
    user_id = message.from_user.id
    if user_id not in smart_index_state: return
    
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
            else: return await message.reply("❌ Invalid link format.")
        elif message.forward_from_chat and message.forward_from_chat.type == enums.ChatType.CHANNEL:
            last_msg_id = message.forward_from_message_id
            chat_id = message.forward_from_chat.id
        else: return await message.reply("❌ Invalid channel message or link.")

        try:
            chat = await client.get_chat(chat_id)
            chat_name = chat.title
            chat_id = chat.id 
        except Exception as e:
            return await message.reply(f"❌ Cannot access chat: `{e}`")

        state['chat_id'] = chat_id
        state['chat_name'] = chat_name
        state['last_msg_id'] = last_msg_id
        state['step'] = 'get_offset'
        
        await message.reply(f"**Target:** {chat_name}\n\n🔢 Enter the **Message ID** to start from (Offset) to resume progress, or type `0` to start from the beginning.")

    elif step == 'get_offset':
        try: offset_val = int(message.text.strip())
        except ValueError: return await message.reply("❌ Invalid offset. Please enter a valid number (e.g., `0`).")
            
        state['offset'] = offset_val
        state['step'] = 'get_json'
        
        btn = [[InlineKeyboardButton("❌ No JSON (Scan & Index Dynamically)", callback_data=f"no_json_{user_id}")]]
        await message.reply(f"**Target:** {state['chat_name']}\n**Offset:** {offset_val}\n\nSend the JSON backup file if you have it. Otherwise, click the button below to scan and index on the fly.", reply_markup=InlineKeyboardMarkup(btn))

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
        stats_dict["Main Bot"] = {"saved": 0, "dup": 0, "err": 0}
    elif job_type == 'multiindex':
        tokens = state['tokens']
        for token in tokens:
            try:
                b = Client(f"sub_{token.split(':')[0]}", bot_token=token, api_id=API_ID, api_hash=API_HASH, in_memory=True)
                await b.start()
                sub_bots.append(b)
                stats_dict[b.me.username] = {"saved": 0, "dup": 0, "err": 0}
            except Exception as e:
                await message.reply(f"❌ Failed to start sub-bot: {e}")
        if not sub_bots:
            await pool.stop_all(main_bot=bot)
            return await message.edit("❌ No active sub-bots. Aborting.")

    # Calculate exact chunks
    chunk_size = 200
    total_chunks = max(1, (last_msg_id - offset) // chunk_size + 1)
    
    active_smart_jobs[job_id] = {
        "user_id": user_id,
        "chat_name": chat_name,
        "chat_id": chat_id,
        "job_type": job_type,
        "start_time": time.time(),
        "total_to_process": total_chunks,
        "current": 0, 
        "scanned_files": 0,
        "helpers": helpers_count,
        "sub_bots": len(sub_bots),
        "stats": stats_dict,
        "cancel": False,
        "scanner_done": False,
        "mode": "Parallel Scan & Batch Save"
    }
    
    btn = [[InlineKeyboardButton("🔄 Update Status", callback_data=f"smart_status_{job_id}")],
           [InlineKeyboardButton("❌ Cancel", callback_data=f"smart_cancel_{job_id}")]]
    sts = await message.reply(f"🚀 **Started Parallel Indexing**\n**Target:** {chat_name}\n\nClick 'Update Status' below to view progress.", reply_markup=InlineKeyboardMarkup(btn))
    
    chunk_queue = asyncio.Queue()
    for i in range(offset, last_msg_id + 1, chunk_size):
        chunk_queue.put_nowait((i, min(i + chunk_size - 1, last_msg_id)))

    collector_queue = asyncio.Queue()
    bot_queues = {'main': asyncio.Queue()} if job_type == 'smartindex' else {b: asyncio.Queue() for b in sub_bots}
    
    all_valid_ids = [] # To build the JSON file

    # 1. SCANNER WORKER (Pulls from chunk_queue, parses messages rapidly)
    async def scanner_worker(client):
        while not chunk_queue.empty():
            if active_smart_jobs[job_id]["cancel"]: 
                break
            try:
                start_id, end_id = chunk_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
                
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
                    
                    active_smart_jobs[job_id]["current"] += 1
                    chunk_queue.task_done()
                    break 
                except FloodWait as e:
                    await asyncio.sleep(e.value + 1)
                except Exception:
                    active_smart_jobs[job_id]["current"] += 1
                    chunk_queue.task_done()
                    break

    # 2. COLLECTOR WORKER (Batches valid IDs exactly by 200)
    async def collector_worker():
        buffer = []
        while True:
            try:
                chunk_valid_ids = await asyncio.wait_for(collector_queue.get(), timeout=1.0)
                if chunk_valid_ids is None: break # Shutdown signal
                
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

        # Flush anything left in buffer
        if buffer:
            if job_type == 'smartindex': await bot_queues['main'].put(buffer)
            elif job_type == 'multiindex':
                for b in sub_bots: await bot_queues[b].put(buffer)

    # 3. DATABASE SAVER WORKER (Opens SQLite once per batch)
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
                    await asyncio.sleep(e.value + 1)
                except Exception:
                    break
            bot_queues[client if job_type == 'multiindex' else 'main'].task_done()

    # Launch execution architecture
    active_scanners = pool.clients if pool.clients else [bot]
    scanner_tasks = [asyncio.create_task(scanner_worker(c)) for c in active_scanners]
    
    collector_task = asyncio.create_task(collector_worker())
    
    saver_tasks = []
    if job_type == 'smartindex':
        saver_tasks.append(asyncio.create_task(saver_worker(bot, DATABASE_FILE, "Main Bot")))
    elif job_type == 'multiindex':
        for b in sub_bots:
            saver_tasks.append(asyncio.create_task(saver_worker(b, get_multi_db_path(b.me.username), b.me.username)))

    # Wait for scanners to deplete the queue
    await chunk_queue.join()
    for task in scanner_tasks: task.cancel()
    
    active_smart_jobs[job_id]["scanner_done"] = True
    
    # Wait for collector to empty its buffer
    await collector_task
    
    # Send kill signal to saver workers
    if job_type == 'smartindex': bot_queues['main'].put_nowait(None)
    elif job_type == 'multiindex':
        for b in sub_bots: bot_queues[b].put_nowait(None)
        
    await asyncio.gather(*saver_tasks)

    # Cleanup & Export
    await pool.stop_all(main_bot=bot)
    for b in sub_bots:
        try: await b.stop()
        except: pass
        
    safe_chat_name = re.sub(r'[\\/*?:"<>|]', "", chat_name).strip()
    json_file = f"{safe_chat_name}_{chat_id}.json".replace(" ", "_")
    with open(json_file, "w") as f:
        all_valid_ids.sort() # Keep it orderly
        json.dump(all_valid_ids, f)
        
    final_text = f"✔️ **Parallel Indexing Completed**\n" if not active_smart_jobs[job_id]["cancel"] else f"🛑 **Cancelled**\n"
    final_text += f"**Chat:** {chat_name}\n**Scanned Chunks:** {active_smart_jobs[job_id]['current']}\n**Found Valid Media:** {len(all_valid_ids)}"
    await sts.edit(final_text)
    
    await message.reply_document(json_file, caption=f"✔️ JSON Backup generated for {chat_name}!\nStored {len(all_valid_ids)} media IDs.")
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
        stats_dict["Main Bot"] = {"saved": 0, "dup": 0, "err": 0}
    elif job_type == 'multiindex':
        tokens = state['tokens']
        for token in tokens:
            try:
                b = Client(f"sub_{token.split(':')[0]}", bot_token=token, api_id=API_ID, api_hash=API_HASH, in_memory=True)
                await b.start()
                sub_bots.append(b)
                stats_dict[b.me.username] = {"saved": 0, "dup": 0, "err": 0}
            except Exception as e:
                await message.reply(f"❌ Failed to start sub-bot: {e}")
        if not sub_bots:
            return await message.reply("❌ No active sub-bots. Aborting.")
            
    total_batches = (len(valid_ids) // 200) + (1 if len(valid_ids) % 200 != 0 else 0)
            
    active_smart_jobs[job_id] = {
        "user_id": user_id,
        "chat_name": chat_name,
        "chat_id": chat_id,
        "job_type": job_type,
        "start_time": time.time(),
        "total_to_process": total_batches,
        "current": 0,
        "scanned_files": len(valid_ids), 
        "helpers": 0,
        "sub_bots": len(sub_bots),
        "stats": stats_dict,
        "cancel": False,
        "scanner_done": True, 
        "mode": "JSON Parallel Batch Fetch"
    }

    btn = [[InlineKeyboardButton("🔄 Update Status", callback_data=f"smart_status_{job_id}")],
           [InlineKeyboardButton("❌ Cancel", callback_data=f"smart_cancel_{job_id}")]]
    sts = await message.reply(f"🚀 **Started JSON Indexing**\n**Target:** {chat_name}\n\nClick 'Update Status' below to view progress.", reply_markup=InlineKeyboardMarkup(btn))
    
    bot_queues = {'main': asyncio.Queue()} if job_type == 'smartindex' else {b: asyncio.Queue() for b in sub_bots}
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
                    await asyncio.sleep(e.value + 1)
                except Exception:
                    break
            
            active_smart_jobs[job_id]["current"] += (1 if job_type == 'smartindex' else (1 / len(sub_bots)))
            bot_queues[worker_client if job_type == 'multiindex' else 'main'].task_done()

    if job_type == 'smartindex':
        saver_tasks.append(asyncio.create_task(saver_worker(client, DATABASE_FILE, "Main Bot")))
    elif job_type == 'multiindex':
        for b in sub_bots:
            saver_tasks.append(asyncio.create_task(saver_worker(b, get_multi_db_path(b.me.username), b.me.username)))

    # Dispatch exact 200-batches
    for i in range(0, len(valid_ids), 200):
        if active_smart_jobs[job_id]["cancel"]: break
        chunk = valid_ids[i:i+200]
        if job_type == 'smartindex': bot_queues['main'].put_nowait(chunk)
        elif job_type == 'multiindex':
            for b in sub_bots: bot_queues[b].put_nowait(chunk)

    # Shutdown signals
    if job_type == 'smartindex': bot_queues['main'].put_nowait(None)
    elif job_type == 'multiindex':
        for b in sub_bots: bot_queues[b].put_nowait(None)

    await asyncio.gather(*saver_tasks)

    if job_type == 'multiindex':
        for b in sub_bots:
            try: await b.stop()
            except: pass

    final_text = f"✔️ **JSON Indexing Completed**\n" if not active_smart_jobs[job_id]["cancel"] else f"🛑 **Cancelled**\n"
    final_text += f"**Chat:** {chat_name}\n**Total Processed:** {len(valid_ids)}"
    await sts.edit(final_text)
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
    progress = int(state["current"])
    total = state["total_to_process"]
    percent = (progress / total * 100) if total > 0 else 0
    
    eta = 0
    if progress > 0 and elapsed > 0:
        speed = progress / elapsed
        rem = total - progress
        eta = rem / speed if speed > 0 else 0

    text = f"🚀 **{state['mode']} In Progress**\n"
    text += f"**Chat:** {state['chat_name']} (`{state['chat_id']}`)\n\n"
    text += f"**Batches/Chunks:** {progress}/{total} ({percent:.1f}%)\n"
    if state.get("scanner_done"):
        text += "✅ **Scanner:** Finished! Waiting for bots to finish DB writes...\n"
    text += f"**Time Elapsed:** {get_readable_time(elapsed)}\n"
    if not state.get("scanner_done"):
        text += f"**ETA:** {get_readable_time(eta)}\n"
    text += "\n"
    
    if state['mode'] == "Dynamic Scan & Save":
        text += f"**Helpers Active:** {state['helpers']}\n"
        text += f"**Valid Files Found:** {state['scanned_files']}\n\n"
    
    for bot_name, stats in state["stats"].items():
        text += f"🤖 **{bot_name}**\n"
        text += f"├ Saved: {stats['saved']}\n"
        text += f"├ Duplicates: {stats['dup']}\n"
        text += f"└ Errors: {stats['err']}\n\n"

    text += f"**Queue:** {len(smart_queue)} jobs waiting."

    btn = [[InlineKeyboardButton("🔄 Update Status", callback_data=f"smart_status_{job_id}")],
           [InlineKeyboardButton("❌ Cancel", callback_data=f"smart_cancel_{job_id}")]]
           
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))
        await query.answer("Status Updated!", show_alert=False)
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
