import asyncio
import re
import math
from hydrogram.errors import MessageNotModified, FloodWait
from Script import script
from info import ADMINS, MAX_BTN, DELETE_TIME, LOG_CHANNEL, SUPPORT_GROUP, UPDATES_LINK
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from hydrogram import Client, filters, enums
from utils import get_size, is_check_admin, get_readable_time, temp, get_settings, save_group_settings
from database.users_chats_db import db
from database.ia_filterdb import get_search_results, delete_files
from plugins.commands import get_grp_stg
import logging

logger = logging.getLogger(__name__)

BUTTONS = {}
CAP = {}

@Client.on_message(filters.private & filters.text & filters.incoming)
async def pm_search(client, message: Message):
    if message.text.startswith("/") or not message.text: return
    stg = await db.get_bot_sttgs()
    if not stg.get('AUTO_FILTER', True): 
        return await message.reply_text('⚙️ ᴀᴜᴛᴏ ꜰɪʟᴛᴇʀ ɪꜱ ᴅɪꜱᴀʙʟᴇᴅ.')
    s = await message.reply(f"<b><i>⏳ `{message.text}` ꜱᴇᴀʀᴄʜɪɴɢ...</i></b>", quote=True)
    await auto_filter(client, message, s)

@Client.on_message(filters.group & filters.text & filters.incoming)
async def group_search(client, message: Message):
    if not message.text or message.text.startswith("/"): return
    user_id = message.from_user.id if message and message.from_user else 0
    if not user_id: return 

    stg = await db.get_bot_sttgs()
    if stg.get('AUTO_FILTER', True):
        if len(message.text) < 2: return 
        s = await message.reply(f"<b><i>⏳ `{message.text}` ꜱᴇᴀʀᴄʜɪɴɢ...</i></b>")
        await auto_filter(client, message, s)

async def auto_filter(client, msg, s):
    message = msg
    settings = await get_settings(message.chat.id)
    search = re.sub(r"\s+", " ", re.sub(r"[-:\"';!]", " ", message.text)).strip()
    if not search: return await s.edit("ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ᴛᴇхᴛ ᴛᴏ ꜱᴇᴀʀᴄʜ.")
    
    files, offset, total_results = await get_search_results(query=search, offset=0)
    if not files:
        not_found_text = f"👋 ʜᴇʟʟᴏ {message.from_user.mention},\n\nɪ ᴄᴏᴜʟᴅɴ'ᴛ ꜰɪɴᴅ `<b>{search}</b>` ɪɴ ᴍʏ ᴅᴀᴛᴀʙᴀꜱᴇ!"
        return await s.edit(not_found_text)

    req = message.from_user.id if message and message.from_user else 0
    key = f"{message.chat.id}-{message.id}"
    temp.FILES[key] = files
    BUTTONS[key] = search
    
    files_link = ""
    btn = []

    if settings.get('links', False): 
        for i, file in enumerate(files):
             files_link += f"<b>\n\n{i+1}. <a href=https://t.me/{temp.U_NAME}?start=filep_{key}_{i}>[{get_size(file['file_size'])}] {file['file_name']}</a></b>"
    else: 
        btn = [[InlineKeyboardButton(f"[{get_size(file['file_size'])}] {file['file_name'][:60]}", callback_data=f'fileidx#{key}#{i}')] for i, file in enumerate(files)]

    if offset != "": 
        pg = 1
        total_pg = math.ceil(total_results / MAX_BTN)
        pg_row = [ InlineKeyboardButton(f"ᴘɢ {pg}/{total_pg}", callback_data="buttons"), InlineKeyboardButton("ɴᴇхᴛ »", callback_data=f"next_{req}_{key}_{offset}") ]
        btn.append(pg_row)

    cap = f"<b>👋 {message.from_user.mention},\n\n🔎 ʀᴇꜱᴜʟᴛꜱ ꜰᴏʀ: {search}</b>"
    CAP[key] = cap 
    del_msg = f"\n\n<b>⚠️ ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ɪɴ {get_readable_time(DELETE_TIME)}.</b>" if settings.get("auto_delete", False) else ''
    final_caption = cap[:1024] + files_link + del_msg 

    try:
        await s.delete()
        k = await message.reply_text(final_caption, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML, quote=True)
        if settings.get("auto_delete", False) and k:
            await asyncio.sleep(DELETE_TIME)
            try: 
                await k.delete()
                await message.delete() 
            except: pass
    except FloodWait as e: 
        await asyncio.sleep(e.value)
    except Exception as e: 
        logger.error(f"Final auto_filter error: {e}", exc_info=True)
        await s.edit("❌ ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ.")

@Client.on_callback_query(filters.regex(r"^next"))
async def next_page(bot, query: CallbackQuery):
    await query.answer() 
    parts = query.data.split("_")
    ident, req, key, offset_str = parts[0], parts[1], parts[2], parts[3]
    try: 
        req_user_id = int(req)
        offset = int(offset_str)
    except: return
    
    if req_user_id != 0 and query.from_user.id != req_user_id: 
        return await query.answer(f"ʜᴇʟʟᴏ {query.from_user.first_name},\nɴᴏᴛ ꜰᴏʀ ʏᴏᴜ!", show_alert=True)
    
    search = BUTTONS.get(key)
    cap = CAP.get(key)
    if not search or not cap: 
        return await query.answer("ʀᴇǫᴜᴇꜱᴛ ᴇхᴘɪʀᴇᴅ.", show_alert=True)
    
    files, n_offset, total = await get_search_results(query=search, offset=offset)
    if not files: return 

    temp.FILES[key] = files 
    settings = await get_settings(query.message.chat.id)
    del_msg = f"\n\n<b>⚠️ ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ɪɴ {get_readable_time(DELETE_TIME)}.</b>" if settings.get("auto_delete", False) else ''
    files_link = ''
    btn = []

    if settings.get('links', False): 
        for i, file in enumerate(files):
            files_link += f"<b>\n\n{offset + 1 + i}. <a href=https://t.me/{temp.U_NAME}?start=filep_{key}_{i}>[{get_size(file['file_size'])}] {file['file_name']}</a></b>"
    else: 
        btn = [[InlineKeyboardButton(f"[{get_size(file['file_size'])}] {file['file_name'][:60]}", callback_data=f"fileidx#{key}#{i}")] for i, file in enumerate(files)]

    pg = math.ceil((offset + 1) / MAX_BTN)
    total_pg = math.ceil(total / MAX_BTN)
    pg_row = []
    
    if offset > 0: 
        pg_row.append(InlineKeyboardButton("« ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{max(0, offset - MAX_BTN)}"))
    pg_row.append(InlineKeyboardButton(f"ᴘɢ {pg}/{total_pg}", callback_data="buttons")) 
    if n_offset != "": 
        pg_row.append(InlineKeyboardButton("ɴᴇхᴛ »", callback_data=f"next_{req}_{key}_{n_offset}"))
    
    if pg_row: btn.append(pg_row)

    try: 
        await query.message.edit_text(cap + files_link + del_msg, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML)
    except MessageNotModified: pass 
    except Exception as e: logger.error(f"Error editing next_page: {e}")


@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    data = query.data
    if data and not data.startswith(("buttons", "set_", "default_", "delete", "send_all", "get_del_", "file", "bool_setgs", "open_", "back_setgs", "caption_setgs", "checksub", "index")):
        try: await query.answer()
        except: pass

    if data == "close_data":
        try: 
            await query.message.delete()
            await query.message.reply_to_message.delete()
        except: pass
        return 

    elif data.startswith("fileidx"):
        _, key, idx_str = data.split("#")
        try: idx = int(idx_str)
        except ValueError: return
        await query.answer(url=f"https://t.me/{temp.U_NAME}?start=filep_{key}_{idx}")
        return

    elif data.startswith("file"): 
        ident, file_id = data.split("#")
        await query.answer(url=f"https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file_id}")
        return

    elif data.startswith("get_del_file"):
        ident, group_id, file_id = data.split("#")
        await query.answer(url=f"https://t.me/{temp.U_NAME}?start=file_{group_id}_{file_id}")
        return

    elif data.startswith("get_del_send_all_files"):
        ident, group_id, key = data.split("#")
        await query.answer(url=f"https://t.me/{temp.U_NAME}?start=all_{group_id}_{key}")
        return

    elif data == "buttons": 
        return await query.answer()

    elif data.startswith("checksub"):
        ident, mc = data.split("#")
        await query.answer(url=f"https://t.me/{temp.U_NAME}?start={mc}")
        return

    elif data.startswith("bool_setgs"):
        ident, set_type, status, grp_id_str = data.split("#")
        try: grp_id = int(grp_id_str)
        except ValueError: return await query.answer("ɪɴᴠᴀʟɪᴅ ɪᴅ.", show_alert=True)
        userid = query.from_user.id
        if not await is_check_admin(client, grp_id, userid): return await query.answer("ɴᴏᴛ ᴀᴅᴍɪɴ.", show_alert=True)
        new_status = not (status == "True")
        await save_group_settings(grp_id, set_type, new_status)
        btn = await get_grp_stg(grp_id)
        try: await query.message.edit_reply_markup(InlineKeyboardMarkup(btn))
        except: pass
        await query.answer(f"{set_type.replace('_',' ').upper()} ꜱᴇᴛ ᴛᴏ {new_status}")
        return

    elif data.startswith("caption_setgs"):
        _, grp_id_str = data.split("#")
        try: grp_id = int(grp_id_str)
        except ValueError: return await query.answer("ɪɴᴠᴀʟɪᴅ ɪᴅ.", show_alert=True)
        userid = query.from_user.id
        if not await is_check_admin(client, grp_id, userid): return await query.answer("ɴᴏᴛ ᴀᴅᴍɪɴ.", show_alert=True)
        settings = await get_settings(grp_id)
        current_val = settings.get('caption', "N/A")
        btn = [[ InlineKeyboardButton(f'ꜱᴇᴛ CAPTION', callback_data=f'set_caption#{grp_id}') ],
               [ InlineKeyboardButton(f'ᴅᴇꜰᴀᴜʟᴛ CAPTION', callback_data=f'default_caption#{grp_id}') ],
               [ InlineKeyboardButton('« ʙᴀᴄᴋ', callback_data=f'back_setgs#{grp_id}') ]]
        await query.message.edit(f'⚙️ CAPTION ꜱᴇᴛᴛɪɴɢꜱ:\n\nᴄᴜʀʀᴇɴᴛ:\n`{current_val}`', reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
        return

    elif data.startswith("set_caption"):
        _, grp_id_str = data.split("#")
        try: grp_id = int(grp_id_str)
        except ValueError: return await query.answer("ɪɴᴠᴀʟɪᴅ ɪᴅ.", show_alert=True)
        userid = query.from_user.id
        if not await is_check_admin(client, grp_id, userid): return await query.answer("ɴᴏᴛ ᴀᴅᴍɪɴ.", show_alert=True)
        ask_msg = None
        try:
            ask_msg = await query.message.edit("➡️ ꜱᴇɴᴅ ɴᴇᴡ CAPTION.")
            r1 = await client.listen(chat_id=query.message.chat.id, user_id=userid, timeout=300)
            if not r1 or not r1.text: raise asyncio.TimeoutError
            v1 = r1.text.strip()
            await r1.delete()
            await save_group_settings(grp_id, 'caption', v1)
            back_btn = [[ InlineKeyboardButton('« ʙᴀᴄᴋ', callback_data=f'caption_setgs#{grp_id}') ]]
            if ask_msg: await ask_msg.edit(f"✔️ ᴜᴘᴅᴀᴛᴇᴅ CAPTION!\n\nɴᴇᴡ:\n`{v1}`", reply_markup=InlineKeyboardMarkup(back_btn))
        except: 
            if ask_msg: await ask_msg.edit("ᴇʀʀᴏʀ ᴏʀ ᴛɪᴍᴇᴏᴜᴛ.")
        return

    elif data.startswith("default_caption"):
        _, grp_id_str = data.split("#")
        try: grp_id = int(grp_id_str)
        except ValueError: return await query.answer("ɪɴᴠᴀʟɪᴅ ɪᴅ.", show_alert=True)
        userid = query.from_user.id
        if not await is_check_admin(client, grp_id, userid): return await query.answer("ɴᴏᴛ ᴀᴅᴍɪɴ.", show_alert=True)
        await save_group_settings(grp_id, 'caption', script.FILE_CAPTION)
        back_btn = [[ InlineKeyboardButton('« ʙᴀᴄᴋ', callback_data=f'caption_setgs#{grp_id}') ]]
        await query.message.edit(f"✔️ ʀᴇꜱᴇᴛ CAPTION ᴛᴏ ᴅᴇꜰᴀᴜʟᴛ.", reply_markup=InlineKeyboardMarkup(back_btn))
        return

    elif data.startswith("back_setgs"):
        _, grp_id_str = data.split("#")
        try: grp_id = int(grp_id_str)
        except ValueError: return await query.answer("ɪɴᴠᴀʟɪᴅ ɪᴅ.", show_alert=True)
        userid = query.from_user.id
        if not await is_check_admin(client, grp_id, userid): return await query.answer("ɴᴏᴛ ᴀᴅᴍɪɴ.", show_alert=True)
        btn = await get_grp_stg(grp_id)
        chat = await client.get_chat(grp_id)
        await query.message.edit(f"⚙️ ꜱᴇᴛᴛɪɴɢꜱ ꜰᴏʀ <b>'{chat.title}'</b>:", reply_markup=InlineKeyboardMarkup(btn))
        return

    elif data == "open_group_settings":
        userid = query.from_user.id
        grp_id = query.message.chat.id
        if not await is_check_admin(client, grp_id, userid): return await query.answer("ɴᴏᴛ ᴀᴅᴍɪɴ.", show_alert=True)
        btn = await get_grp_stg(grp_id)
        await query.message.edit(f"⚙️ ꜱᴇᴛᴛɪɴɢꜱ ꜰᴏʀ <b>'{query.message.chat.title}'</b>:", reply_markup=InlineKeyboardMarkup(btn))
        return

    elif data == "open_pm_settings":
        userid = query.from_user.id
        grp_id = query.message.chat.id
        if not await is_check_admin(client, grp_id, userid): return await query.answer("ɴᴏᴛ ᴀᴅᴍɪɴ.", show_alert=True)
        btn = await get_grp_stg(grp_id)
        pm_btn = [[ InlineKeyboardButton('ɢᴏ ᴛᴏ ᴘᴍ ➔', url=f"https://t.me/{temp.U_NAME}?start=settings_{grp_id}") ]]
        try: 
            await client.send_message(userid, f"⚙️ ꜱᴇᴛᴛɪɴɢꜱ ꜰᴏʀ <b>'{query.message.chat.title}'</b>:", reply_markup=InlineKeyboardMarkup(btn))
            await query.message.edit("✔️ ꜱᴇɴᴛ ᴛᴏ ᴘᴍ.", reply_markup=InlineKeyboardMarkup(pm_btn))
        except: 
            await query.message.edit("⚠️ ᴄʟɪᴄᴋ ʙᴜᴛᴛᴏɴ ᴛᴏ ᴏᴘᴇɴ ɪɴ ᴘᴍ.", reply_markup=InlineKeyboardMarkup(pm_btn))
        return

    elif data.startswith("delete"):
        if query.from_user.id not in ADMINS: 
            return await query.answer("ᴀᴅᴍɪɴꜱ ᴏɴʟʏ.", show_alert=True)
        _, query_text = data.split("_", 1)
        await query.message.edit('⏳ ᴅᴇʟᴇᴛɪɴɢ...')
        deleted_count = await delete_files(query_text)
        await query.message.edit(f'✔️ ᴅᴇʟᴇᴛᴇᴅ {deleted_count} ꜰɪʟᴇꜱ ꜰᴏʀ `{query_text}`.')
        return