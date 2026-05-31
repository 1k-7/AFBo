import time
import asyncio
import re
import os
import json
import requests
from hydrogram import Client, filters, enums
from hydrogram.errors import FloodWait, MessageNotModified
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from info import ADMINS, INDEX_EXTENSIONS, LOG_CHANNEL, API_ID, API_HASH
from database.ia_filterdb import save_file, save_file_custom 
from database.users_chats_db import db as data_db
from utils import temp, get_readable_time
import logging

logger = logging.getLogger(__name__)

index_queue = []
is_indexing = False
current_index_job = None
smart_index_state = {}

class UserbotPool:
    def __init__(self, sessions, api_id, api_hash, main_bot=None):
        self.sessions = sessions
        self.api_id = api_id
        self.api_hash = api_hash
        self.clients = []
        self.cooldowns = {}
        if main_bot:
            self.clients.append(main_bot)
            self.cooldowns[main_bot] = 0

    async def start_all(self):
        count = 0
        for s in self.sessions:
            try:
                c = Client(f"helper_{count}", session_string=s, api_id=self.api_id, api_hash=self.api_hash, in_memory=True)
                await c.start()
                self.clients.append(c)
                self.cooldowns[c] = 0
                count += 1
            except Exception as e:
                logger.error(f"Failed to start userbot: {e}")
        return count

    def get_client(self):
        now = time.time()
        available = [c for c in self.clients if self.cooldowns.get(c, 0) <= now]
        if available:
            c = available[0]
            self.clients.remove(c)
            self.clients.append(c)
            return c, 0
        
        min_client = min(self.clients, key=lambda c: self.cooldowns.get(c, 0))
        wait_time = self.cooldowns[min_client] - now
        return min_client, max(0, wait_time)

    def set_cooldown(self, client, wait_seconds):
        self.cooldowns[client] = time.time() + wait_seconds

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
    except Exception as e:
        logger.error(f"Failed to send log via secondary bot: {e}")

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

@Client.on_message(filters.private & filters.user(ADMINS) & ~filters.command(["smartindex", "multiindex", "index", "indexhelper", "exportmulti", "start", "help", "stats", "export", "import", "delete", "index_channels"]))
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
        state['step'] = 'get_json'
        
        btn = [[InlineKeyboardButton("❌ No JSON (Scan with Userbots)", callback_data=f"no_json_{user_id}")]]
        await message.reply(f"**Target:** {chat_name}\n\nSend the JSON backup file if you have it. Otherwise, click 'No JSON'.", reply_markup=InlineKeyboardMarkup(btn))

    elif step == 'get_json':
        if message.document and message.document.file_name.endswith('.json'):
            file_path = await message.download()
            try:
                with open(file_path, 'r') as f:
                    valid_ids = json.load(f)
                os.remove(file_path)
                state['valid_ids'] = valid_ids
                await execute_smart_multi_index(client, message, state)
            except Exception as e:
                await message.reply(f"❌ Error reading JSON: {e}")
            del smart_index_state[user_id]
        else:
            await message.reply("Please send a valid JSON file, or click 'No JSON' above.")

@Client.on_callback_query(filters.regex(r'^no_json_'))
async def handle_no_json(bot, query: CallbackQuery):
    user_id = query.from_user.id
    if user_id not in smart_index_state: return await query.answer("State expired.", show_alert=True)
    
    await query.message.edit("Initiating Userbot Scanning Phase...")
    state = smart_index_state[user_id]
    chat_id = state['chat_id']
    chat_name = state['chat_name']
    last_msg_id = state['last_msg_id']
    
    stg = await data_db.get_bot_sttgs()
    sessions = stg.get("INDEX_SESSIONS", [])
    
    pool = UserbotPool(sessions, API_ID, API_HASH, main_bot=bot)
    helpers_count = await pool.start_all()
    
    if helpers_count > 0:
        try:
            invite_link = await bot.create_chat_invite_link(chat_id)
            await pool.join_chat(invite_link.invite_link)
        except Exception as e: pass
            
    valid_ids = []
    chunk_size = 200
    current_id = 1
    
    sts = await query.message.reply(f"🔎 Scanning `{chat_name}` with {helpers_count} helpers...")
    
    while current_id <= last_msg_id:
        c, wait_time = pool.get_client()
        if wait_time > 0:
            await asyncio.sleep(wait_time)
            continue
            
        chunk = list(range(current_id, min(current_id + chunk_size, last_msg_id + 1)))
        try:
            msgs = await c.get_messages(chat_id, chunk)
            for m in msgs:
                if m.empty: continue
                if m.media and m.media in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT]:
                    media = getattr(m, m.media.value, None)
                    if media and getattr(media, 'file_name', None):
                        if any(media.file_name.lower().endswith(ext) for ext in INDEX_EXTENSIONS):
                            valid_ids.append(m.id)
            current_id += chunk_size
            if current_id % 2000 == 0 or current_id >= last_msg_id:
                try: await sts.edit(f"🔎 Scanning `{chat_name}`... ({current_id}/{last_msg_id})")
                except: pass
        except FloodWait as e:
            pool.set_cooldown(c, e.value)
            continue
        except Exception:
            current_id += chunk_size

    await pool.stop_all(main_bot=bot)
    
    json_file = f"{chat_name}_{chat_id}.json".replace(" ", "_")
    with open(json_file, "w") as f:
        json.dump(valid_ids, f)
        
    await query.message.reply_document(json_file, caption=f"✔️ Backup generated! Found {len(valid_ids)} files.")
    os.remove(json_file)
    
    state['valid_ids'] = valid_ids
    await execute_smart_multi_index(bot, sts, state)
    del smart_index_state[user_id]


async def execute_smart_multi_index(client, message, state):
    valid_ids = state['valid_ids']
    chat_id = state['chat_id']
    job_type = state['type']
    
    if not valid_ids:
        return await message.reply("❌ No valid files to index.")
        
    sts = await message.reply(f"🚀 Starting File ID Fetching Phase for {len(valid_ids)} files...")
    
    if job_type == 'smartindex':
        stg = await data_db.get_bot_sttgs()
        sessions = stg.get("INDEX_SESSIONS", [])
        pool = UserbotPool(sessions, API_ID, API_HASH, main_bot=client)
        await pool.start_all()
        
        saved = 0
        i = 0
        while i < len(valid_ids):
            c, wait_time = pool.get_client()
            if wait_time > 0:
                await asyncio.sleep(wait_time)
                continue
                
            chunk = valid_ids[i:i+200]
            try:
                msgs = await c.get_messages(chat_id, chunk)
                for m in msgs:
                    if m.empty: continue
                    media = getattr(m, m.media.value, None) if m.media else None
                    if media:
                        res = await save_file(media, replace=True)
                        if res == 'suc': saved += 1
                i += 200
                if i % 1000 == 0:
                    try: await sts.edit(f"Fetching... ({i}/{len(valid_ids)})\nSaved: {saved}")
                    except: pass
            except FloodWait as e:
                pool.set_cooldown(c, e.value)
                continue
            except Exception as e:
                i += 200
                
        await pool.stop_all(main_bot=client)
        await sts.edit(f"✔️ Smart Index Complete! Saved {saved} files to Main DB.")

    elif job_type == 'multiindex':
        tokens = state['tokens']
        sub_bots = []
        for token in tokens:
            try:
                b = Client(f"sub_{token.split(':')[0]}", bot_token=token, api_id=API_ID, api_hash=API_HASH, in_memory=True)
                await b.start()
                sub_bots.append(b)
            except Exception as e:
                await message.reply(f"❌ Failed to start sub-bot: {e}")
                
        if not sub_bots:
            return await sts.edit("❌ No active sub-bots.")
            
        await sts.edit(f"🚀 Fetching for {len(sub_bots)} sub-bots simultaneously. Ensure they are Admins in the source chat!")
        
        for b in sub_bots:
            saved = 0
            db_name = f"multi_{b.me.username}.db"
            bot_sts = await message.reply(f"🤖 Fetching for @{b.me.username}...")
            
            for i in range(0, len(valid_ids), 200):
                chunk = valid_ids[i:i+200]
                try:
                    msgs = await b.get_messages(chat_id, chunk)
                    for m in msgs:
                        if m.empty: continue
                        media = getattr(m, m.media.value, None) if m.media else None
                        if media:
                            res = await save_file_custom(media, db_name, replace=True)
                            if res == 'suc': saved += 1
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except Exception as e:
                    pass
            await bot_sts.edit(f"✔️ Finished @{b.me.username} - Saved {saved} files to `{db_name}`.")
            await b.stop()
        
        await sts.edit("✔️ Multi-Index Complete! Use `/exportmulti` to download DBs.")

@Client.on_message(filters.command('exportmulti') & filters.user(ADMINS))
async def export_multi_cmd(client, message):
    db_files = [f for f in os.listdir() if f.startswith("multi_") and f.endswith(".db")]
    if not db_files: return await message.reply("❌ No multi-index DBs found.")
    
    sts = await message.reply("⏳ Converting Multi-DBs to JSON...")
    
    import aiosqlite
    for db_file in db_files:
        try:
            async with aiosqlite.connect(db_file) as sql_db:
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

# ================================
# BASIC INDEX ENGINE (Queue)
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

    skip_ask_msg = await response_msg.reply("🔢 Messages to skip from 0 (e.g., 0):")
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
        if not is_indexing: asyncio.create_task(process_index_queue(bot))
    elif ident == 'cancel':
        temp.CANCEL = True
        await query.answer("Cancellation requested for current job.", show_alert=True)

async def process_index_queue(bot):
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
    
    stg = await data_db.get_bot_sttgs()
    sec_token = stg.get('SECONDARY_BOT_TOKEN')
    sessions = stg.get("INDEX_SESSIONS", [])
    
    pool = UserbotPool(sessions, API_ID, API_HASH, main_bot=bot)
    await pool.start_all()
    
    SAVE_BATCH_SIZE = 100
    temp.CANCEL = False
    save_tasks = []
    loop = asyncio.get_running_loop()
    
    current_id = skip if skip > 0 else 1
    
    try:
        while current_id <= lst_msg_id:
            if temp.CANCEL: break
            
            c, wait_time = pool.get_client()
            if wait_time > 0:
                await asyncio.sleep(wait_time)
                continue
                
            chunk_size = min(200, lst_msg_id - current_id + 1)
            chunk_ids = list(range(current_id, current_id + chunk_size))
            
            try:
                msgs = await c.get_messages(chat_id, chunk_ids)
                for message in msgs:
                    current_index_job["current"] = message.id
                    if message.empty: current_index_job["deleted"] += 1; continue
                    if not message.media or message.media not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT]: current_index_job["unsupported"] += 1; continue
                    media = getattr(message, message.media.value, None)
                    if not media or not getattr(media, 'file_name', None): current_index_job["unsupported"] += 1; continue
                    if not any(media.file_name.lower().endswith(ext) for ext in INDEX_EXTENSIONS): current_index_job["unsupported"] += 1; continue
                    media.caption = message.caption
                    save_tasks.append(save_file(media, replace=replace))
                    
                    if len(save_tasks) >= SAVE_BATCH_SIZE:
                        results = await asyncio.gather(*save_tasks, return_exceptions=True)
                        for res in results:
                             if isinstance(res, Exception): current_index_job["errors"] += 1; (loop.run_in_executor(None, send_error_log, sec_token, f"DB Error: {res}") if sec_token else None)
                             elif res == 'err': current_index_job["errors"] += 1
                             elif res == 'suc': current_index_job["total_files"] += 1
                             elif res == 'dup': current_index_job["duplicate"] += 1
                        save_tasks = []
                        
                current_id += chunk_size
            except FloodWait as e:
                pool.set_cooldown(c, e.value)
                continue
            except Exception as e:
                current_id += chunk_size
                
        if save_tasks:
            results = await asyncio.gather(*save_tasks, return_exceptions=True)
            for res in results:
                 if isinstance(res, Exception): current_index_job["errors"] += 1; (loop.run_in_executor(None, send_error_log, sec_token, f"DB Error: {res}") if sec_token else None)
                 elif res == 'err': current_index_job["errors"] += 1
                 elif res == 'suc': current_index_job["total_files"] += 1
                 elif res == 'dup': current_index_job["duplicate"] += 1
                 
        elapsed = time.time() - current_index_job["start_time"]
        status = "🛑 Cancelled" if temp.CANCEL else "✔️ Completed"
        final_text = f"{status}!\n\n**Chat:** {chat_name} (`{chat_id}`)\n**Processed:** {current_index_job['current'] - skip}\n**Saved:** {current_index_job['total_files']}\n**Duplicates:** {current_index_job['duplicate']}\n**Errors:** {current_index_job['errors']}\n**Time:** {get_readable_time(elapsed)}"
        await msg.edit(final_text)
    except Exception as e:
        logger.exception(f"Fatal indexing error: {e}")
        if sec_token: loop.run_in_executor(None, send_error_log, sec_token, f"Fatal Loop Error: {e}")
        try: await msg.edit(f'❌ Fatal Error: {e}')
        except: pass
    finally:
        temp.CANCEL = False
        await pool.stop_all(main_bot=bot)

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
