import re
import time
import asyncio
from math import ceil
from hydrogram import Client, filters, enums
from hydrogram.errors import FloodWait, MessageNotModified, MessageTooLong
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from info import ADMINS, INDEX_EXTENSIONS
from database.ia_filterdb import save_file 
from database.users_chats_db import db as data_db
from utils import temp, get_readable_time
import logging

logger = logging.getLogger(__name__)
lock = asyncio.Lock()

index_stats = {
    "status_message": "Initializing...",
    "start_time": 0,
    "total_files": 0,
    "duplicate": 0,
    "errors": 0,
    "deleted": 0,
    "no_media": 0,
    "unsupported": 0,
    "current": 0,
    "total_to_process": 0,
    "last_msg_id": 0,
    "chat_id": None,
    "skip": 0,
    "last_update_time": 0
}

@Client.on_callback_query(filters.regex(r'^index#(yes|cancel|replace)'))
async def index_files_callback(bot, query: CallbackQuery):
    global index_stats
    user_id = query.from_user.id
    if user_id not in ADMINS:
        return await query.answer("ᴏɴʟʏ ᴀᴅᴍɪɴꜱ ᴄᴀɴ ᴍᴀɴᴀɢᴇ ɪɴᴅᴇхɪɴɢ.", show_alert=True)

    try:
        parts = query.data.split("#")
        if len(parts) != 5: raise ValueError("Incorrect callback data format")
        _, ident, chat, lst_msg_id_str, skip_str = parts
        lst_msg_id = int(lst_msg_id_str)
        skip = int(skip_str)
        try: chat_id_int = int(chat)
        except ValueError: chat_id_int = chat 
    except (ValueError, IndexError) as e:
        logger.error(f"Error splitting index control callback: {e}")
        return await query.answer("ɪɴᴠᴀʟɪᴅ ᴄᴀʟʟʙᴀᴄᴋ.", show_alert=True)

    if ident == 'yes' or ident == 'replace':
        if lock.locked():
             return await query.answer("⏳ ᴀɴᴏᴛʜᴇʀ ɪɴᴅᴇхɪɴɢ ɪꜱ ᴀʟʀᴇᴀᴅʏ ɪɴ ᴘʀᴏɢʀᴇꜱꜱ.", show_alert=True)

        replace_mode = (ident == 'replace')
        mode_text = " (REPLACE MODE)" if replace_mode else ""

        index_stats = {
            "status_message": f"Starting{mode_text}...",
            "start_time": time.time(),
            "total_files": 0, "duplicate": 0, "errors": 0, "deleted": 0,
            "no_media": 0, "unsupported": 0, "current": skip,
            "total_to_process": lst_msg_id - skip, "last_msg_id": lst_msg_id,
            "chat_id": chat_id_int, "skip": skip, "last_update_time": time.time()
        }
        msg = query.message
        await msg.edit(f"⏳ ɪɴᴅᴇхɪɴɢ ꜱᴛᴀʀᴛɪɴɢ ꜰᴏʀ ᴄʜᴀɴɴᴇʟ ɪᴅ: `{chat_id_int}`{mode_text}\n~ ꜱᴋɪᴘᴘɪɴɢ ꜰɪʀꜱᴛ {skip} ᴍᴇꜱꜱᴀɢᴇꜱ.")
        
        asyncio.create_task(index_files_to_db_iter(lst_msg_id, chat_id_int, msg, bot, skip, replace=replace_mode))
        await query.answer(f"ɪɴᴅᴇхɪɴɢ ꜱᴛᴀʀᴛᴇᴅ{mode_text}.", show_alert=False)

    elif ident == 'cancel':
        if not temp.CANCEL:
             temp.CANCEL = True
             logger.warning(f"User {user_id} requested indexing cancellation.")
             await query.message.edit("❗️ ᴛʀʏɪɴɢ ᴛᴏ ᴄᴀɴᴄᴇʟ ɪɴᴅᴇхɪɴɢ...")
             await query.answer("ᴄᴀɴᴄᴇʟʟᴀᴛɪᴏɴ ʀᴇǫᴜᴇꜱᴛ ꜱᴇɴᴛ.", show_alert=False)
        else:
             await query.answer("ᴄᴀɴᴄᴇʟʟᴀᴛɪᴏన్ ᴀʟʀᴇᴀᴅʏ ʀᴇǫᴜᴇꜱᴛᴇᴅ.", show_alert=False)

@Client.on_message(filters.command(['index', 'indexrc']) & filters.private & filters.user(ADMINS))
async def send_for_index(bot, message):
    if lock.locked():
        return await message.reply('⏳ ᴀɴᴏᴛʜᴇʀ ɪɴᴅᴇхɪɴɢ ᴘʀᴏᴄᴇꜱꜱ ɪꜱ ʀᴜɴɴɪɴɢ. ᴘʟᴇᴀꜱᴇ ᴡᴀɪᴛ.')

    is_replace = (message.command[0] == 'indexrc')
    action_text = "REPLACE/UPDATE" if is_replace else "INDEX"

    ask_msg = None
    response_msg = None
    try:
        ask_msg = await message.reply(f"➡️ <b>[{action_text}]</b> ꜰᴏʀᴡᴀʀᴅ ᴛʜᴇ ʟᴀꜱᴛ ᴍᴇꜱꜱᴀɢᴇ ꜰʀᴏᴍ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ (ᴡɪᴛʜ ǫᴜᴏᴛᴇꜱ)\nᴏʀ ꜱᴇɴᴅ ᴛʜᴇ ᴄʜᴀᴛ'ꜱ ʟᴀꜱᴛ ᴍᴇꜱꜱᴀɢᴇ ʟɪɴᴋ.")
        response_msg = await bot.listen(chat_id=message.chat.id, user_id=message.from_user.id, timeout=120)
    except asyncio.TimeoutError:
        if ask_msg: await ask_msg.edit("⏰ ᴛɪᴍᴇᴏᴜᴛ. ɪɴᴅᴇхɪɴɢ ᴄᴀɴᴄᴇʟʟᴇᴅ.")
        return
    except Exception as e:
         if ask_msg: await ask_msg.edit(f"ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ: {e}")
         return
    finally:
         if ask_msg:
             try: await ask_msg.delete()
             except: pass

    if not response_msg:
        return

    chat_id = None
    last_msg_id = None
    if response_msg.forward_from_chat and response_msg.forward_from_chat.type == enums.ChatType.CHANNEL:
        last_msg_id = response_msg.forward_from_message_id
        chat_id = response_msg.forward_from_chat.username or response_msg.forward_from_chat.id
    elif response_msg.text and response_msg.text.startswith(("https://t.me/", "http://t.me/")):
        try:
            msg_link = response_msg.text.strip()
            match = re.match(r"https?://t\.me/(?:c/)?([\w\-]+)/(\d+)", msg_link)
            if match:
                 channel_part = match.group(1)
                 last_msg_id = int(match.group(2))
                 try: chat_id = int(f"-100{channel_part}")
                 except ValueError: chat_id = channel_part
            else:
                 await response_msg.reply('⚠️ ɪɴᴠᴀʟɪᴅ ᴍᴇꜱꜱᴀɢᴇ ʟɪɴᴋ ꜰᴏʀᴍᴀᴛ.')
                 return
        except Exception as e:
            await response_msg.reply(f'⚠️ ɪɴᴠᴀʟɪᴅ ᴍᴇꜱꜱᴀɢᴇ ʟɪɴᴋ ({e}).')
            return
    else:
        await response_msg.reply('❌ ᴛʜɪꜱ ɪꜱ ɴᴏᴛ ᴀ ᴠᴀʟɪᴅ ꜰᴏʀᴡᴀʀᴅᴇᴅ ᴍᴇꜱꜱᴀɢᴇ ᴏʀ ᴄʜᴀɴɴᴇʟ ᴍᴇꜱꜱᴀɢᴇ ʟɪɴᴋ.')
        return

    try:
        chat = await bot.get_chat(chat_id)
        if chat.type != enums.ChatType.CHANNEL:
            return await response_msg.reply("❌ ɪ ᴄᴀɴ ᴏɴʟʏ ɪɴᴅᴇх ᴄʜᴀɴɴᴇʟꜱ.")
    except Exception as e:
        return await response_msg.reply(f'❌ ᴄᴏᴜʟᴅ ɴᴏᴛ ᴀᴄᴄᴇꜱꜱ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ/ʟɪɴᴋ.\nᴍᴀᴋᴇ ꜱᴜʀᴇ ᴛʜᴇ ʙᴏᴛ ɪꜱ ᴀɴ ᴀᴅᴍɪɴ.\nᴇʀʀᴏʀ: {e}')

    skip_ask_msg = None
    skip_response = None
    try:
        skip_ask_msg = await response_msg.reply("🔢 ᴇɴᴛᴇʀ ᴛʜᴇ ɴᴜᴍʙᴇʀ ᴏꜰ ᴍᴇꜱꜱᴀɢᴇꜱ ᴛᴏ ꜱᴋɪᴘ ꜰʀᴏᴍ ᴛʜᴇ ꜱᴛᴀʀᴛ (ᴇ.ɢ., `0` ᴛᴏ ꜱᴋɪᴘ ɴᴏɴᴇ).")
        skip_response = await bot.listen(chat_id=message.chat.id, user_id=message.from_user.id, timeout=60)
    except asyncio.TimeoutError:
         if skip_ask_msg: await skip_ask_msg.edit("⏰ ᴛɪᴍᴇᴏᴜᴛ. ɪɴᴅᴇхɪɴɢ ᴄᴀɴᴄᴇʟʟᴇᴅ.")
         return
    finally:
         if skip_ask_msg:
             try: await skip_ask_msg.delete()
             except: pass

    if not skip_response:
        return

    try:
        skip = int(skip_response.text.strip())
        if skip < 0: raise ValueError
    except ValueError:
        await skip_response.reply("❌ ɪɴᴠᴀʟɪᴅ ɴᴜᴍʙᴇʀ.")
        return

    ident = "replace" if is_replace else "yes"
    btn_text = "✔️ ꜱᴛᴀʀᴛ ʀᴇᴘʟᴀᴄᴇ/ᴜᴘᴅᴀᴛᴇ" if is_replace else "✔️ ʏᴇꜱ, ꜱᴛᴀʀᴛ ɪɴᴅᴇхɪɴɢ"
    
    buttons = [[ InlineKeyboardButton(btn_text, callback_data=f'index#{ident}#{chat_id}#{last_msg_id}#{skip}') ],
               [ InlineKeyboardButton('❌ ɴᴏ, ᴄᴀɴᴄᴇʟ', callback_data='close_data') ]]
    reply_markup = InlineKeyboardMarkup(buttons)
    await skip_response.reply(f'❓ ᴅᴏ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ <b>{action_text}</b> ᴍᴇꜱꜱᴀɢᴇꜱ ꜰʀᴏᴍ `{chat.title}`?\n\n • ᴛᴏᴛᴀʟ: ~`{last_msg_id}`\n • ꜱᴋɪᴘ: `{skip}`', reply_markup=reply_markup)


def get_progress_bar(percent, length=10):
    filled = int(length * percent / 100)
    unfilled = length - filled
    return '█' * filled + '▒' * unfilled

async def index_files_to_db_iter(lst_msg_id, chat, msg, bot, skip, replace=False):
    global index_stats
    SAVE_BATCH_SIZE = 100
    EDIT_INTERVAL = 15
    status_callback_data = 'index_status'

    if lock.locked():
         try: await msg.edit("⚠️ ɪɴᴅᴇхɪɴɢ ʟᴏᴄᴋ ɪꜱ ᴀʟʀᴇᴀᴅʏ ʜᴇʟᴅ.")
         except: pass
         return

    async with lock:
        try:
            temp.CANCEL = False
            save_tasks = []
            last_processed_msg_id = skip
            index_stats["start_time"] = time.time()
            index_stats["last_update_time"] = time.time()

            async for message in bot.iter_messages(chat, limit=lst_msg_id + 1, offset=skip):
                if temp.CANCEL:
                    break

                last_processed_msg_id = message.id
                index_stats["current"] = last_processed_msg_id

                if message.empty: index_stats["deleted"] += 1; continue
                if not message.media: index_stats["no_media"] += 1; continue
                if message.media not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT]: index_stats["unsupported"] += 1; continue
                media = getattr(message, message.media.value, None)
                if not media or not hasattr(media, 'file_name') or not media.file_name: index_stats["unsupported"] += 1; continue
                file_name_lower = media.file_name.lower()
                if not any(file_name_lower.endswith("." + ext.lstrip('.')) for ext in INDEX_EXTENSIONS): index_stats["unsupported"] += 1; continue

                media.caption = message.caption
                save_tasks.append(save_file(media, data_db, replace=replace))

                if len(save_tasks) >= SAVE_BATCH_SIZE:
                    results = await asyncio.gather(*save_tasks, return_exceptions=True)
                    for result in results:
                         if isinstance(result, Exception): index_stats["errors"] += 1; logger.error(f"Save error: {result}")
                         elif result == 'suc': index_stats["total_files"] += 1
                         elif result == 'dup': index_stats["duplicate"] += 1
                         elif result == 'err': index_stats["errors"] += 1
                    save_tasks = []

                current_time = time.time()
                if current_time - index_stats["last_update_time"] > EDIT_INTERVAL:
                    progress = last_processed_msg_id - skip
                    percentage = min((progress / index_stats["total_to_process"]) * 100, 100.0) if index_stats["total_to_process"] > 0 else 100.0
                    progress_bar_str = get_progress_bar(int(percentage))
                    elapsed = current_time - index_stats["start_time"]
                    processed_per_sec = progress / elapsed if elapsed > 0 else 0
                    remaining = index_stats["total_to_process"] - progress
                    eta = (remaining / processed_per_sec) if processed_per_sec > 0 else 0

                    mode_str = "REPLACE" if replace else "INDEX"
                    index_stats["status_message"] = (
                         f"⏳ <b>{mode_str}</b> `{chat}`...\n"
                         f"{progress_bar_str} {percentage:.1f}%\n"
                         f"~ ᴍꜱɢ ɪᴅ: {last_processed_msg_id}/{lst_msg_id}\n"
                         f"~ ꜱᴀᴠᴇᴅ: {index_stats['total_files']} | ᴅᴜᴘ: {index_stats['duplicate']}\n"
                         f"~ ꜱᴋɪᴘ: {index_stats['no_media'] + index_stats['unsupported']} | ᴇʀʀ: {index_stats['errors']}\n"
                         f"~ ᴇʟᴀᴘ: {get_readable_time(elapsed)} | ᴇᴛᴀ: {get_readable_time(eta)}"
                    )

                    try:
                        await msg.edit_text(
                            text=index_stats["status_message"],
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton('ꜱᴛᴀᴛᴜꜱ', callback_data=status_callback_data)],
                                [InlineKeyboardButton('❌ ᴄᴀɴᴄᴇʟ', callback_data=f'index#cancel#{chat}#{lst_msg_id}#{skip}')]]))
                        index_stats["last_update_time"] = current_time
                    except FloodWait as e: await asyncio.sleep(e.value)
                    except MessageNotModified: pass
                    except Exception as e_edit: logger.error(f"Error editing progress: {e_edit}")

            if save_tasks:
                results = await asyncio.gather(*save_tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, Exception): index_stats["errors"] += 1
                    elif result == 'suc': index_stats["total_files"] += 1
                    elif result == 'dup': index_stats["duplicate"] += 1
                    elif result == 'err': index_stats["errors"] += 1

            elapsed = time.time() - index_stats["start_time"]
            final_status_msg = "✔️ ᴄᴏᴍᴘʟᴇᴛᴇᴅ!" if not temp.CANCEL else "🛑 ᴄᴀɴᴄᴇʟʟᴇᴅ!"
            mode_str = "REPLACE" if replace else "INDEX"
            
            final_text_summary = (
                f"{final_status_msg} ({mode_str})\nᴄʜᴀɴɴᴇʟ: `{chat}`\nᴛᴏᴏᴋ {get_readable_time(elapsed)}\n\n"
                f"▷ ᴘʀᴏᴄᴇꜱꜱᴇᴅ: {last_processed_msg_id - skip}\n"
                f"▷ ꜱᴀᴠᴇᴅ/ᴜᴘᴅᴀᴛᴇᴅ: {index_stats['total_files']}\n"
                f"▷ ᴅᴜᴘʟɪᴄᴀᴛᴇꜱ: {index_stats['duplicate']}\n"
                f"▷ ᴇʀʀᴏʀꜱ: {index_stats['errors']}"
            )
            index_stats["status_message"] = final_text_summary
            await msg.edit(final_text_summary, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('ᴄʟᴏꜱᴇ', callback_data='close_data')]]))

        except Exception as e:
            logger.exception(f"Fatal indexing error: {e}")
            try: await msg.edit(f'❌ ꜰᴀᴛᴀʟ ᴇʀʀᴏʀ: {e}', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('ᴄʟᴏꜱᴇ', callback_data='close_data')]]))
            except: pass
        finally:
            temp.CANCEL = False

@Client.on_callback_query(filters.regex(r"^index_status$"))
async def index_status_alert(bot, query: CallbackQuery):
    global index_stats
    if lock.locked():
        elapsed = time.time() - index_stats.get("start_time", time.time())
        progress = index_stats.get("current", 0) - index_stats.get("skip", 0)
        total_to_process = index_stats.get("total_to_process", 1) 
        percentage = min((progress / total_to_process) * 100, 100.0) if total_to_process > 0 else 0.0
        
        status_text = (
             f"STATS (`{index_stats.get('chat_id', 'N/A')}`)\n"
             f"▷ {percentage:.1f}%\n"
             f"▷ Saved: {index_stats.get('total_files', 0)}\n"
             f"▷ Dups: {index_stats.get('duplicate', 0)}\n"
             f"▷ Errors: {index_stats.get('errors', 0)}\n"
             f"▷ Time: {get_readable_time(elapsed)}"
         )
    else:
        status_text = index_stats.get("status_message", "No active process.")

    try:
        await query.answer(text=status_text[:199], show_alert=True)
    except Exception: await query.answer("Status Error.", show_alert=True)