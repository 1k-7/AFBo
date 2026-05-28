import time
import asyncio
from hydrogram import Client, filters, enums
from hydrogram.errors import FloodWait, MessageNotModified
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from info import ADMINS, INDEX_EXTENSIONS
from database.ia_filterdb import save_file 
from utils import temp, get_readable_time
import logging

logger = logging.getLogger(__name__)
lock = asyncio.Lock()

index_stats = {
    "status_message": "Initializing...", "start_time": 0, "total_files": 0, "duplicate": 0, 
    "errors": 0, "deleted": 0, "no_media": 0, "unsupported": 0, "current": 0, 
    "total_to_process": 0, "last_msg_id": 0, "chat_id": None, "skip": 0
}

@Client.on_message(filters.command(['index', 'indexrc']) & filters.private & filters.user(ADMINS))
async def send_for_index(bot, message):
    if lock.locked(): return await message.reply('⏳ Indexing already in progress.')

    is_replace = (message.command[0] == 'indexrc')
    ask_msg = await message.reply("➡️ Forward the last message from the channel or send the message link.")
    
    try: response_msg = await bot.listen(chat_id=message.chat.id, user_id=message.from_user.id, timeout=120)
    except asyncio.TimeoutError: return await ask_msg.edit("⏰ Timeout.")
    finally: await ask_msg.delete()

    chat_id, last_msg_id = None, None
    if response_msg.forward_from_chat and response_msg.forward_from_chat.type == enums.ChatType.CHANNEL:
        last_msg_id = response_msg.forward_from_message_id
        chat_id = response_msg.forward_from_chat.id
    else:
        return await response_msg.reply("❌ Invalid channel message. Make sure it's forwarded from a channel.")

    skip_ask_msg = await response_msg.reply("🔢 Messages to skip from 0 (e.g., 0):")
    try: skip_response = await bot.listen(chat_id=message.chat.id, user_id=message.from_user.id, timeout=60)
    except asyncio.TimeoutError: return await skip_ask_msg.edit("⏰ Timeout.")
    finally: await skip_ask_msg.delete()

    skip = int(skip_response.text.strip())
    ident = "replace" if is_replace else "yes"
    btn = [[InlineKeyboardButton("✔️ Start", callback_data=f'index#{ident}#{chat_id}#{last_msg_id}#{skip}')],
           [InlineKeyboardButton("❌ Cancel", callback_data='close_data')]]
    await skip_response.reply(f"Index {last_msg_id} messages from {chat_id}?", reply_markup=InlineKeyboardMarkup(btn))


@Client.on_callback_query(filters.regex(r'^index#(yes|cancel|replace)'))
async def index_files_callback(bot, query: CallbackQuery):
    global index_stats
    user_id = query.from_user.id
    if user_id not in ADMINS: return await query.answer("Admins only.", show_alert=True)

    parts = query.data.split("#")
    _, ident, chat, lst_msg_id_str, skip_str = parts
    lst_msg_id, skip = int(lst_msg_id_str), int(skip_str)
    chat_id_int = int(chat)

    if ident in ['yes', 'replace']:
        if lock.locked(): return await query.answer("Indexing in progress.", show_alert=True)
        replace_mode = (ident == 'replace')
        index_stats = {
            "start_time": time.time(), "total_files": 0, "duplicate": 0, "errors": 0, "deleted": 0,
            "no_media": 0, "unsupported": 0, "current": skip, "total_to_process": lst_msg_id - skip, 
            "last_msg_id": lst_msg_id, "chat_id": chat_id_int, "skip": skip
        }
        
        btn = [[InlineKeyboardButton("🔄 Update Status", callback_data="index_status")],
               [InlineKeyboardButton("❌ Cancel", callback_data=f'index#cancel#{chat_id_int}#{lst_msg_id}#{skip}')]]
        
        msg = query.message
        await msg.edit("⏳ Indexing started... Click 'Update Status' below to view progress.", reply_markup=InlineKeyboardMarkup(btn))
        asyncio.create_task(index_files_to_db_iter(lst_msg_id, chat_id_int, msg, bot, skip, replace=replace_mode))
        
    elif ident == 'cancel':
        temp.CANCEL = True
        await query.answer("Cancellation requested.", show_alert=True)

async def index_files_to_db_iter(lst_msg_id, chat, msg, bot, skip, replace=False):
    global index_stats
    SAVE_BATCH_SIZE = 100

    async with lock:
        try:
            temp.CANCEL = False
            save_tasks = []
            
            async for message in bot.iter_messages(chat, limit=lst_msg_id + 1, offset=skip):
                if temp.CANCEL: break
                index_stats["current"] = message.id

                if message.empty: index_stats["deleted"] += 1; continue
                if not message.media or message.media not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT]:
                    index_stats["unsupported"] += 1; continue
                    
                media = getattr(message, message.media.value, None)
                if not media or not getattr(media, 'file_name', None): index_stats["unsupported"] += 1; continue
                
                if not any(media.file_name.lower().endswith(ext) for ext in INDEX_EXTENSIONS): 
                    index_stats["unsupported"] += 1; continue

                media.caption = message.caption
                save_tasks.append(save_file(media, replace=replace))

                if len(save_tasks) >= SAVE_BATCH_SIZE:
                    results = await asyncio.gather(*save_tasks, return_exceptions=True)
                    for res in results:
                         if isinstance(res, Exception) or res == 'err': index_stats["errors"] += 1
                         elif res == 'suc': index_stats["total_files"] += 1
                         elif res == 'dup': index_stats["duplicate"] += 1
                    save_tasks = []

            if save_tasks:
                results = await asyncio.gather(*save_tasks, return_exceptions=True)
                for res in results:
                    if isinstance(res, Exception) or res == 'err': index_stats["errors"] += 1
                    elif res == 'suc': index_stats["total_files"] += 1
                    elif res == 'dup': index_stats["duplicate"] += 1

            elapsed = time.time() - index_stats["start_time"]
            status = "🛑 Cancelled" if temp.CANCEL else "✔️ Completed"
            final_text = f"{status}!\nProcessed: {index_stats['current'] - skip}\nSaved: {index_stats['total_files']}\nDuplicates: {index_stats['duplicate']}\nErrors: {index_stats['errors']}\nTime: {get_readable_time(elapsed)}"
            await msg.edit(final_text)

        except Exception as e:
            logger.exception(f"Fatal indexing error: {e}")
            try: await msg.edit(f'❌ Fatal Error: {e}')
            except: pass
        finally:
            temp.CANCEL = False

@Client.on_callback_query(filters.regex(r"^index_status$"))
async def index_status_update(bot, query: CallbackQuery):
    global index_stats
    if not lock.locked(): return await query.answer("No active process.", show_alert=True)
    
    elapsed = time.time() - index_stats["start_time"]
    progress = index_stats["current"] - index_stats["skip"]
    total = index_stats["total_to_process"]
    percent = (progress / total * 100) if total > 0 else 0
    
    text = (f"⏳ **Indexing In Progress**\n\n"
            f"**Progress:** {progress}/{total} ({percent:.1f}%)\n"
            f"**Saved:** {index_stats['total_files']}\n"
            f"**Duplicates:** {index_stats['duplicate']}\n"
            f"**Errors:** {index_stats['errors']}\n"
            f"**Time Elapsed:** {get_readable_time(elapsed)}")
            
    btn = [[InlineKeyboardButton("🔄 Update Status", callback_data="index_status")],
           [InlineKeyboardButton("❌ Cancel", callback_data=f'index#cancel#{index_stats["chat_id"]}#{index_stats["last_msg_id"]}#{index_stats["skip"]}')]]
           
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))
        await query.answer("Status Updated!", show_alert=False)
    except MessageNotModified:
        await query.answer("No new changes.", show_alert=False)
    except FloodWait as e:
        await query.answer(f"Flood wait... {e.value}s", show_alert=True)