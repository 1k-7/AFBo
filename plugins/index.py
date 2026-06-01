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
from database.ia_filterdb import save_file, save_file_custom 
from database.users_chats_db import db as data_db
from utils import temp, get_readable_time
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
active_smart_jobs = {} # Tracks live jobs by Unique Job ID

class UserbotPool:
    def __init__(self, sessions, api_id, api_hash, main_bot=None):
        self.sessions = sessions
        self.api_id = api_id
        self.api_hash = api_hash
        self.clients = []
        self.cooldowns = {}
        self.main_bot = main_bot
        
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
        
        # Prioritize helpers first
        helpers = [c for c in self.clients if c != self.main_bot and self.cooldowns.get(c, 0) <= now]
        if helpers:
            c = helpers[0]
            # Rotate helper to the back of the line
            self.clients.remove(c)
            self.clients.append(c)
            return c, 0
            
        # Fallback to main bot if all helpers are floodwaited
        if self.main_bot and self.cooldowns.get(self.main_bot, 0) <= now:
            return self.main_bot, 0
            
        # If absolutely everything is floodwaited, find the shortest cooldown
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

def get_multi_db_path(bot_username):
    # Extracts the directory from DATABASE_FILE to ensure persistent storage
    db_dir = os.path.dirname(DATABASE_FILE) or "."
    return os.path.join(db_dir, f"multi_{bot_username}.db")

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
                
                # Filter out IDs before the offset
                offset = state.get('offset', 0)
                valid_ids = [vid for vid in raw_valid_ids if vid >= offset]
                state['valid_ids'] = valid_ids
                
                # Add to queue with a Unique Job ID
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
            
    active_smart_jobs[job_id] = {
        "user_id": user_id,
        "chat_name": chat_name,
        "chat_id": chat_id,
        "job_type": job_type,
        "start_time": time.time(),
        "total_to_process": max(0, last_msg_id - offset),
        "current": 0, # Relative to offset
        "scanned_files": 0,
        "helpers": helpers_count,
        "sub_bots": len(sub_bots),
        "stats": stats_dict,
        "cancel": False,
        "scanner_done": False,
        "mode": "Dynamic Scan & Save"
    }
    
    btn = [[InlineKeyboardButton("🔄 Update Status", callback_data=f"smart_status_{job_id}")],
           [InlineKeyboardButton("❌ Cancel", callback_data=f"smart_cancel_{job_id}")]]
    sts = await message.reply(f"🚀 **Started Dynamic Indexing**\n**Target:** {chat_name}\n\nClick 'Update Status' below to view progress.", reply_markup=InlineKeyboardMarkup(btn))
    
    valid_ids = []
    chunk_size = 200
    current_id = offset
    loop = asyncio.get_running_loop()

    # Create background worker queues for true async fetching
    workers = []
    bot_queues = {}
    
    if job_type == 'smartindex':
        bot_queues['main'] = asyncio.Queue()
        async def main_worker():
            while True:
                batch = await bot_queues['main'].get()
                if batch is None: break # Sentinel to stop
                while True:
                    if active_smart_jobs[job_id]["cancel"]: break
                    try:
                        bot_msgs = await bot.get_messages(chat_id, batch)
                        for m in bot_msgs:
                            if m.empty: continue
                            media = getattr(m, m.media.value, None) if m.media else None
                            if media:
                                res = await save_file(media, replace=False)
                                if res == 'suc': active_smart_jobs[job_id]["stats"]["Main Bot"]["saved"] += 1
                                elif res == 'dup': active_smart_jobs[job_id]["stats"]["Main Bot"]["dup"] += 1
                                else: 
                                    active_smart_jobs[job_id]["stats"]["Main Bot"]["err"] += 1
                                    if sec_token: loop.run_in_executor(None, send_error_log, sec_token, "Save Error Main Bot")
                        break # batch successful
                    except FloodWait as e:
                        await asyncio.sleep(e.value + 1)
                    except Exception:
                        break # hard error, drop batch
                bot_queues['main'].task_done()
        workers.append(asyncio.create_task(main_worker()))

    elif job_type == 'multiindex':
        bot_queues = {b: asyncio.Queue() for b in sub_bots}
        async def sub_worker(b):
            db_name = get_multi_db_path(b.me.username)
            while True:
                batch = await bot_queues[b].get()
                if batch is None: break
                while True:
                    if active_smart_jobs[job_id]["cancel"]: break
                    try:
                        b_msgs = await b.get_messages(chat_id, batch)
                        for m in b_msgs:
                            if m.empty: continue
                            media = getattr(m, m.media.value, None) if m.media else None
                            if media:
                                res = await save_file_custom(media, db_name, replace=False)
                                if res == 'suc': active_smart_jobs[job_id]["stats"][b.me.username]["saved"] += 1
                                elif res == 'dup': active_smart_jobs[job_id]["stats"][b.me.username]["dup"] += 1
                                else: active_smart_jobs[job_id]["stats"][b.me.username]["err"] += 1
                        break 
                    except FloodWait as e:
                        await asyncio.sleep(e.value + 1)
                    except Exception:
                        break 
                bot_queues[b].task_done()
        for b in sub_bots:
            workers.append(asyncio.create_task(sub_worker(b)))

    # Main Scanning Loop
    buffer_valid_ids = []
    loop_count = 0
    
    while current_id <= last_msg_id:
        if active_smart_jobs[job_id]["cancel"]: break
        loop_count += 1
        
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
                            buffer_valid_ids.append(m.id)
                            valid_ids.append(m.id)
        except FloodWait as e:
            pool.set_cooldown(c, e.value)
            continue
        except Exception:
            pass

        active_smart_jobs[job_id]["scanned_files"] = len(valid_ids)
        current_id += chunk_size
        active_smart_jobs[job_id]["current"] = min(current_id - offset, active_smart_jobs[job_id]["total_to_process"])

        # Flush buffer in chunks of 200 OR if there's a long dry spell
        while len(buffer_valid_ids) >= 200 or (loop_count % 5 == 0 and buffer_valid_ids) or current_id > last_msg_id:
            if not buffer_valid_ids: break
            chunk_to_send = buffer_valid_ids[:200]
            
            # Don't send a partial chunk unless it's a forced flush cycle or the end of the channel
            if len(chunk_to_send) < 200 and not (loop_count % 5 == 0 or current_id > last_msg_id):
                break
                
            buffer_valid_ids = buffer_valid_ids[len(chunk_to_send):]
            
            if job_type == 'smartindex':
                bot_queues['main'].put_nowait(chunk_to_send)
            elif job_type == 'multiindex':
                for b in sub_bots:
                    bot_queues[b].put_nowait(chunk_to_send)

    # Scanner finished, signal workers to stop when queue empties
    active_smart_jobs[job_id]["scanner_done"] = True
    
    if job_type == 'smartindex':
        bot_queues['main'].put_nowait(None)
    elif job_type == 'multiindex':
        for b in sub_bots:
            bot_queues[b].put_nowait(None)
            
    # Wait for all bots to finish saving the remaining queue
    await asyncio.gather(*workers)

    # Cleanup & Export
    await pool.stop_all(main_bot=bot)
    for b in sub_bots:
        try: await b.stop()
        except: pass
        
    safe_chat_name = re.sub(r'[\\/*?:"<>|]', "", chat_name).strip()
    json_file = f"{safe_chat_name}_{chat_id}.json".replace(" ", "_")
    with open(json_file, "w") as f:
        json.dump(valid_ids, f)
        
    final_text = f"✔️ **Dynamic Indexing Completed**\n" if not active_smart_jobs[job_id]["cancel"] else f"🛑 **Cancelled**\n"
    final_text += f"**Chat:** {chat_name}\n**Scanned Messages:** {active_smart_jobs[job_id]['current']}\n**Found Valid Media:** {len(valid_ids)}"
    await sts.edit(final_text)
    
    await message.reply_document(json_file, caption=f"✔️ JSON Backup generated for {chat_name}!\nStored {len(valid_ids)} media IDs.")
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
    sec_token = stg.get('SECONDARY_BOT_TOKEN')
    
    sub_bots = []
    stats_dict = {}
    
    if job_type == 'smartindex':
        stats_dict["Main Bot"] = {"saved": 0, "dup": 0, "err": 0}
        sessions = stg.get("INDEX_SESSIONS", [])
        pool = UserbotPool(sessions, API_ID, API_HASH, main_bot=client)
        helpers_count = await pool.start_all()
    elif job_type == 'multiindex':
        tokens = state['tokens']
        helpers_count = 0
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
            
    active_smart_jobs[job_id] = {
        "user_id": user_id,
        "chat_name": chat_name,
        "chat_id": chat_id,
        "job_type": job_type,
        "start_time": time.time(),
        "total_to_process": len(valid_ids),
        "current": 0,
        "scanned_files": len(valid_ids), 
        "helpers": helpers_count,
        "sub_bots": len(sub_bots),
        "stats": stats_dict,
        "cancel": False,
        "scanner_done": False, # Always false since we just dispatch
        "mode": "JSON Fetch & Save"
    }

    btn = [[InlineKeyboardButton("🔄 Update Status", callback_data=f"smart_status_{job_id}")],
           [InlineKeyboardButton("❌ Cancel", callback_data=f"smart_cancel_{job_id}")]]
    sts = await message.reply(f"🚀 **Started JSON Indexing**\n**Target:** {chat_name}\n\nClick 'Update Status' below to view progress.", reply_markup=InlineKeyboardMarkup(btn))
    
    loop = asyncio.get_running_loop()
    workers = []
    bot_queues = {}

    if job_type == 'smartindex':
        bot_queues['main'] = asyncio.Queue()
        async def main_worker():
            while True:
                batch = await bot_queues['main'].get()
                if batch is None: break
                while True:
                    if active_smart_jobs[job_id]["cancel"]: break
                    try:
                        bot_msgs = await client.get_messages(chat_id, batch)
                        for m in bot_msgs:
                            if m.empty: continue
                            media = getattr(m, m.media.value, None) if m.media else None
                            if media:
                                res = await save_file(media, replace=False)
                                if res == 'suc': active_smart_jobs[job_id]["stats"]["Main Bot"]["saved"] += 1
                                elif res == 'dup': active_smart_jobs[job_id]["stats"]["Main Bot"]["dup"] += 1
                                else: 
                                    active_smart_jobs[job_id]["stats"]["Main Bot"]["err"] += 1
                                    if sec_token: loop.run_in_executor(None, send_error_log, sec_token, "Save Error Main Bot")
                        break
                    except FloodWait as e:
                        await asyncio.sleep(e.value + 1)
                    except Exception:
                        break
                bot_queues['main'].task_done()
        workers.append(asyncio.create_task(main_worker()))
        
        for i in range(0, len(valid_ids), 200):
            if active_smart_jobs[job_id]["cancel"]: break
            chunk = valid_ids[i:i+200]
            bot_queues['main'].put_nowait(chunk)
            active_smart_jobs[job_id]["current"] = min(i + 200, len(valid_ids))
            
        bot_queues['main'].put_nowait(None)

    elif job_type == 'multiindex':
        bot_queues = {b: asyncio.Queue() for b in sub_bots}
        async def sub_worker(b):
            db_name = get_multi_db_path(b.me.username)
            while True:
                batch = await bot_queues[b].get()
                if batch is None: break
                while True:
                    if active_smart_jobs[job_id]["cancel"]: break
                    try:
                        b_msgs = await b.get_messages(chat_id, batch)
                        for m in b_msgs:
                            if m.empty: continue
                            media = getattr(m, m.media.value, None) if m.media else None
                            if media:
                                res = await save_file_custom(media, db_name, replace=False)
                                if res == 'suc': active_smart_jobs[job_id]["stats"][b.me.username]["saved"] += 1
                                elif res == 'dup': active_smart_jobs[job_id]["stats"][b.me.username]["dup"] += 1
                                else: active_smart_jobs[job_id]["stats"][b.me.username]["err"] += 1
                        break 
                    except FloodWait as e:
                        await asyncio.sleep(e.value + 1)
                    except Exception:
                        break 
                bot_queues[b].task_done()
        for b in sub_bots:
            workers.append(asyncio.create_task(sub_worker(b)))

        for i in range(0, len(valid_ids), 200):
            if active_smart_jobs[job_id]["cancel"]: break
            chunk = valid_ids[i:i+200]
            for b in sub_bots:
                bot_queues[b].put_nowait(chunk)
            active_smart_jobs[job_id]["current"] = min(i + 200, len(valid_ids))
            
        for b in sub_bots:
            bot_queues[b].put_nowait(None)

    active_smart_jobs[job_id]["scanner_done"] = True
    await asyncio.gather(*workers)

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
        # Check if it's sitting in the queue
        for idx, job in enumerate(smart_queue):
            if job['job_id'] == job_id:
                return await query.answer(f"Job is currently in Queue.\nPosition: {idx + 1}", show_alert=True)
        return await query.answer("No active process.", show_alert=True)
    
    state = active_smart_jobs[job_id]
    elapsed = time.time() - state["start_time"]
    progress = state["current"]
    total = state["total_to_process"]
    percent = (progress / total * 100) if total > 0 else 0
    
    eta = 0
    if progress > 0 and elapsed > 0:
        speed = progress / elapsed
        rem = total - progress
        eta = rem / speed if speed > 0 else 0

    text = f"🚀 **{state['mode']} In Progress**\n"
    text += f"**Chat:** {state['chat_name']} (`{state['chat_id']}`)\n\n"
    text += f"**Scanner Progress:** {progress}/{total} ({percent:.1f}%)\n"
    if state.get("scanner_done"):
        text += "✅ **Scanner:** Finished! Waiting for bots to finish saving...\n"
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
    
    import aiosqlite
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
            
        import aiosqlite
        async with aiosqlite.connect(full_db_path) as db:
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
    
    stg = await data_db.get_bot_sttgs()
    sec_token = stg.get('SECONDARY_BOT_TOKEN')
    
    SAVE_BATCH_SIZE = 100
    temp.CANCEL = False
    save_tasks = []
    loop = asyncio.get_running_loop()
    
    current_id = skip if skip > 0 else 1
    
    try:
        while current_id <= lst_msg_id:
            if temp.CANCEL: break
            
            chunk_size = min(200, lst_msg_id - current_id + 1)
            chunk_ids = list(range(current_id, current_id + chunk_size))
            
            try:
                msgs = await bot.get_messages(chat_id, chunk_ids)
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
                await asyncio.sleep(e.value + 1)
                continue
            except Exception:
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
