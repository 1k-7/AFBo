import time
import asyncio
import re
import requests
from hydrogram import Client, filters, enums
from hydrogram.errors import FloodWait, MessageNotModified
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from info import ADMINS, INDEX_EXTENSIONS, LOG_CHANNEL
from database.ia_filterdb import save_file 
from database.users_chats_db import db as data_db
from utils import temp, get_readable_time
import logging

logger = logging.getLogger(__name__)

# Queue variables
index_queue = []
is_indexing = False
current_index_job = None

# Fallback logger using requests to bypass main bot floodwaits
def send_error_log(token, text):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": LOG_CHANNEL, "text": f"⚠️ <b>Indexing Error:</b>\n{text}", "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        logger.error(f"Failed to send log via secondary bot: {e}")

@Client.on_message(filters.command(['index', 'indexrc']) & filters.private & filters.user(ADMINS))
async def send_for_index(bot, message):
    is_replace = (message.command[0] == 'indexrc')
    ask_msg = await message.reply("➡️ Forward the last message from the channel or send the message link (e.g., `https://t.me/c/123/456` or `https://t.me/channel/456`).")
    
    try: 
        response_msg = await bot.listen(chat_id=message.chat.id, user_id=message.from_user.id, timeout=120)
    except asyncio.TimeoutError: 
        return await ask_msg.edit("⏰ Timeout.")
    finally: 
        await ask_msg.delete()

    chat_id, last_msg_id = None, None
    text = response_msg.text

    # Parse Link
    if text and "t.me/" in text:
        match = re.search(r"t\.me/(?:c/)?([^/]+)/(\d+)", text)
        if match:
            chat_id_str = match.group(1)
            last_msg_id = int(match.group(2))
            # If it's purely digits, it's a private ID so add -100
            if chat_id_str.isdigit():
                chat_id = int(f"-100{chat_id_str}")
            else:
                chat_id = chat_id_str if chat_id_str.startswith("@") else f"@{chat_id_str}"
        else:
            return await response_msg.reply("❌ Invalid link format.")
    # Check if forwarded
    elif response_msg.forward_from_chat and response_msg.forward_from_chat.type == enums.ChatType.CHANNEL:
        last_msg_id = response_msg.forward_from_message_id
        chat_id = response_msg.forward_from_chat.id
    else:
        return await response_msg.reply("❌ Invalid channel message or link.")

    # Try resolving chat info to verify access
    try:
        chat = await bot.get_chat(chat_id)
        chat_name = chat.title
        chat_id = chat.id 
    except Exception as e:
        return await response_msg.reply(f"❌ Cannot access chat: `{e}`")

    skip_ask_msg = await response_msg.reply("🔢 Messages to skip from 0 (e.g., 0):")
    try: 
        skip_response = await bot.listen(chat_id=message.chat.id, user_id=message.from_user.id, timeout=60)
    except asyncio.TimeoutError: 
        return await skip_ask_msg.edit("⏰ Timeout.")
    finally: 
        await skip_ask_msg.delete()

    skip = int(skip_response.text.strip())
    ident = "replace" if is_replace else "yes"
    
    btn = [[InlineKeyboardButton("✔️ Start Indexing", callback_data=f'index#{ident}#{chat_id}#{last_msg_id}#{skip}')],
           [InlineKeyboardButton("❌ Cancel", callback_data='close_data')]]
           
    await skip_response.reply(f"Index {last_msg_id - skip} messages from **{chat_name}** (`{chat_id}`)?", reply_markup=InlineKeyboardMarkup(btn))


@Client.on_callback_query(filters.regex(r'^index#(yes|cancel|replace)'))
async def index_files_callback(bot, query: CallbackQuery):
    global index_queue, is_indexing
    user_id = query.from_user.id
    if user_id not in ADMINS: 
        return await query.answer("Admins only.", show_alert=True)

    parts = query.data.split("#")
    _, ident, chat, lst_msg_id_str, skip_str = parts
    lst_msg_id, skip = int(lst_msg_id_str), int(skip_str)
    
    try: chat_id = int(chat)
    except: chat_id = chat

    if ident in ['yes', 'replace']:
        replace_mode = (ident == 'replace')
        
        job_data = {
            "chat_id": chat_id,
            "last_msg_id": lst_msg_id,
            "skip": skip,
            "replace": replace_mode,
            "message": query.message
        }
        
        index_queue.append(job_data)
        
        queue_pos = len(index_queue)
        await query.message.edit(f"✅ Added to Indexing Queue! Position: {queue_pos}")
        
        # Start worker if not running
        if not is_indexing:
            asyncio.create_task(process_index_queue(bot))
            
    elif ident == 'cancel':
        temp.CANCEL = True
        await query.answer("Cancellation requested for current job.", show_alert=True)

async def process_index_queue(bot):
    global index_queue, is_indexing, current_index_job
    if is_indexing: return
    is_indexing = True
    
    while index_queue:
        job = index_queue.pop(0)
        try:
            await execute_index_job(bot, job)
        except Exception as e:
            logger.error(f"Job failed: {e}")
            
    is_indexing = False
    current_index_job = None

async def execute_index_job(bot, job):
    global current_index_job
    
    chat_id = job["chat_id"]
    lst_msg_id = job["last_msg_id"]
    skip = job["skip"]
    replace = job["replace"]
    msg = job["message"]
    
    try:
        chat = await bot.get_chat(chat_id)
        chat_name = chat.title
    except:
        chat_name = "Unknown"

    current_index_job = {
        "status_message": "Initializing...", "start_time": time.time(), 
        "total_files": 0, "duplicate": 0, "errors": 0, "deleted": 0, 
        "no_media": 0, "unsupported": 0, "current": skip, 
        "total_to_process": lst_msg_id - skip, "last_msg_id": lst_msg_id, 
        "chat_id": chat_id, "chat_name": chat_name, "skip": skip
    }
    
    btn = [[InlineKeyboardButton("🔄 Update Status", callback_data="index_status")],
           [InlineKeyboardButton("❌ Cancel Current", callback_data='cancel_current_index')]]
           
    await msg.edit(f"⏳ **Indexing Started:** {chat_name}\nClick 'Update Status' below.", reply_markup=InlineKeyboardMarkup(btn))
    
    SAVE_BATCH_SIZE = 100
    temp.CANCEL = False
    save_tasks = []
    
    loop = asyncio.get_running_loop()
    stg = await data_db.get_bot_sttgs()
    sec_token = stg.get('SECONDARY_BOT_TOKEN')

    try:
        async for message in bot.iter_messages(chat_id, limit=lst_msg_id + 1, offset=skip):
            if temp.CANCEL: break
            current_index_job["current"] = message.id

            if message.empty: 
                current_index_job["deleted"] += 1
                continue
            if not message.media or message.media not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT]:
                current_index_job["unsupported"] += 1
                continue
                
            media = getattr(message, message.media.value, None)
            if not media or not getattr(media, 'file_name', None): 
                current_index_job["unsupported"] += 1
                continue
            
            if not any(media.file_name.lower().endswith(ext) for ext in INDEX_EXTENSIONS): 
                current_index_job["unsupported"] += 1
                continue

            media.caption = message.caption
            save_tasks.append(save_file(media, replace=replace))

            if len(save_tasks) >= SAVE_BATCH_SIZE:
                results = await asyncio.gather(*save_tasks, return_exceptions=True)
                for res in results:
                     if isinstance(res, Exception): 
                         current_index_job["errors"] += 1
                         if sec_token: loop.run_in_executor(None, send_error_log, sec_token, f"DB Error: {res}")
                     elif res == 'err': current_index_job["errors"] += 1
                     elif res == 'suc': current_index_job["total_files"] += 1
                     elif res == 'dup': current_index_job["duplicate"] += 1
                save_tasks = []

        # Process remaining
        if save_tasks:
            results = await asyncio.gather(*save_tasks, return_exceptions=True)
            for res in results:
                 if isinstance(res, Exception): 
                     current_index_job["errors"] += 1
                     if sec_token: loop.run_in_executor(None, send_error_log, sec_token, f"DB Error: {res}")
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
    if not current_index_job: 
        return await query.answer("No active process.", show_alert=True)
    
    elapsed = time.time() - current_index_job["start_time"]
    progress = current_index_job["current"] - current_index_job["skip"]
    total = current_index_job["total_to_process"]
    percent = (progress / total * 100) if total > 0 else 0
    
    text = (f"⏳ **Indexing In Progress**\n"
            f"**Chat:** {current_index_job['chat_name']} (`{current_index_job['chat_id']}`)\n\n"
            f"**Progress:** {progress}/{total} ({percent:.1f}%)\n"
            f"**Saved:** {current_index_job['total_files']}\n"
            f"**Duplicates:** {current_index_job['duplicate']}\n"
            f"**Errors:** {current_index_job['errors']}\n"
            f"**Time Elapsed:** {get_readable_time(elapsed)}\n\n"
            f"**Queue:** {len(index_queue)} jobs waiting.")
            
    btn = [[InlineKeyboardButton("🔄 Update Status", callback_data="index_status")],
           [InlineKeyboardButton("❌ Cancel Current", callback_data='cancel_current_index')]]
           
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))
        await query.answer("Status Updated!", show_alert=False)
    except MessageNotModified:
        await query.answer("No new changes.", show_alert=False)
    except FloodWait as e:
        await query.answer(f"Flood wait... {e.value}s", show_alert=True)

@Client.on_callback_query(filters.regex(r"^cancel_current_index$"))
async def cancel_current(bot, query: CallbackQuery):
    user_id = query.from_user.id
    if user_id not in ADMINS: 
        return await query.answer("Admins only.", show_alert=True)
    temp.CANCEL = True
    await query.answer("Cancellation requested for the current job.", show_alert=True)