import asyncio
import re
from time import time as time_now
import math, os
import random
from functools import partial
from hydrogram.errors import ListenerTimeout, MessageNotModified, FloodWait
from hydrogram.errors.exceptions.bad_request_400 import MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty
from Script import script
import urllib.parse
from datetime import datetime, timedelta, timezone
import pytz
from info import (PICS, TUTORIAL, ADMINS, URL, MAX_BTN, BIN_CHANNEL,
                  DELETE_TIME, FILMS_LINK, LOG_CHANNEL, SUPPORT_GROUP, SUPPORT_LINK,
                  UPDATES_LINK, LANGUAGES, QUALITY, IS_STREAM, BOT_ID,
                  IS_VERIFY, VERIFY_TUTORIAL, VERIFY_EXPIRE,
                  SHORTLINK_API, SHORTLINK_URL, SHORTLINK, PM_FILE_DELETE_TIME
                  )
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto, Message
from hydrogram import Client, filters, enums
from utils import (get_size, is_subscribed, is_check_admin, get_wish,
                   get_shortlink, get_readable_time, get_poster, temp,
                   get_settings, save_group_settings,
                   get_verify_status, update_verify_status)
from database.users_chats_db import db
from database.ia_filterdb import get_total_files_count, get_search_results
from plugins.commands import get_grp_stg
import logging

logger = logging.getLogger(__name__)

BUTTONS = {}
CAP = {}


@Client.on_message(filters.private & filters.text & filters.incoming)
async def pm_search(client, message: Message):
    if message.text.startswith("/") or not message.text: return
    loop = asyncio.get_running_loop()
    stg = await loop.run_in_executor(None, db.get_bot_sttgs)

    if not stg.get('PM_SEARCH', True): return await message.reply_text('🔒 ᴘᴍ ꜱᴇᴀʀᴄʜ ɪꜱ ᴄᴜʀʀᴇɴᴛʟʏ ᴅɪꜱᴀʙʟᴇᴅ.')
    if not stg.get('AUTO_FILTER', True): return await message.reply_text('⚙️ ᴀᴜᴛᴏ ꜰɪʟᴛᴇʀ ᴡᴀꜱ ᴅɪꜱᴀʙʟᴇᴅ ɢʟᴏʙᴀʟʟʏ.')

    s = await message.reply(f"<b><i>⏳ `{message.text}` ꜱᴇᴀʀᴄʜɪɴɢ...</i></b>", quote=True)
    await auto_filter(client, message, s)

@Client.on_message(filters.group & filters.text & filters.incoming)
async def group_search(client, message: Message):
    if not message.text or message.text.startswith("/"): return
    user_id = message.from_user.id if message and message.from_user else 0
    if not user_id: return 

    loop = asyncio.get_running_loop()
    stg = await loop.run_in_executor(None, db.get_bot_sttgs)

    if stg.get('AUTO_FILTER', True):
        if message.chat.id == SUPPORT_GROUP:
            files, offset, total = await get_search_results(query=message.text)
            if files:
                btn = [[ InlineKeyboardButton("➡️ ɢᴇᴛ ꜰɪʟᴇꜱ ʜᴇʀᴇ", url=FILMS_LINK) ]]
                await message.reply_text(f'♢ {total} ʀᴇꜱᴜʟᴛꜱ ꜰᴏᴜɴᴅ.\n♢ ꜱᴇᴀʀᴄʜ ɪɴ ᴍᴀɪɴ ᴄʜᴀᴛ.', reply_markup=InlineKeyboardMarkup(btn))
            return 

        elif '@admin' in message.text.lower() or '@admins' in message.text.lower():
            if await is_check_admin(client, message.chat.id, user_id): return 
            admins = [m.user.id async for m in client.get_chat_members(message.chat.id, filter=enums.ChatMembersFilter.ADMINISTRATORS) if not m.user.is_bot]
            owner = next((m async for m in client.get_chat_members(message.chat.id, filter=enums.ChatMembersFilter.ADMINISTRATORS) if m.status == enums.ChatMemberStatus.OWNER), None)
            if owner and owner.user.id not in admins : admins.append(owner.user.id)
            if not admins: return await message.reply("ᴄᴏᴜʟᴅɴ'ᴛ ꜰɪɴᴅ ᴀᴅᴍɪɴꜱ.")
            target = message.reply_to_message or message
            text = f"#ᴀᴛᴛᴇɴᴛɪᴏɴ\n♢ ᴜꜱᴇʀ: {message.from_user.mention}\n♢ <a href={target.link}>ʀᴇᴘᴏʀᴛᴇᴅ ᴍᴇꜱꜱᴀɢᴇ</a>"
            notified = set()
            for admin_id in admins:
                if admin_id in notified: continue
                try: await target.forward(admin_id); await client.send_message(admin_id, text, disable_web_page_preview=True); notified.add(admin_id); await asyncio.sleep(0.3)
                except Exception as e: logger.error(f"Notify admin {admin_id} error: {e}")
            await message.reply_text('✔️ ʀᴇᴘᴏʀᴛ ꜱᴇɴᴛ!') if notified else await message.reply_text('❌ ᴄᴏᴜʟᴅ ɴᴏᴛ ɴᴏᴛɪꜰʏ.')
            return

        elif re.findall(r'https?://\S+|www\.\S+|t\.me/\S+', message.text):
            if await is_check_admin(client, message.chat.id, user_id): return
            try: await message.delete()
            except Exception as e: logger.warning(f"Delete link error {message.chat.id}: {e}")
            return

        elif '#request' in message.text.lower():
            if user_id in ADMINS: return 
            if not LOG_CHANNEL: return await message.reply("ʀᴇǫᴜᴇꜱᴛ ꜰᴇᴀᴛᴜʀᴇ ɪꜱ ᴄᴜʀʀᴇɴᴛʟʏ ᴅɪꜱᴀʙʟᴇᴅ.")
            try:
                req_text = re.sub(r'#request', '', message.text, flags=re.IGNORECASE).strip()
                if not req_text: return await message.reply("ᴘʟᴇᴀꜱᴇ ꜱᴘᴇᴄɪꜰʏ ʏᴏᴜʀ ʀᴇǫᴜᴇꜱᴛ ᴀꜰᴛᴇʀ #ʀᴇǫᴜᴇꜱᴛ.")
                log_msg = f"#ʀᴇǫᴜᴇꜱᴛ\n♢ ᴜꜱᴇʀ: {message.from_user.mention} (`{user_id}`)\n♢ ɢʀᴏᴜᴘ: {message.chat.title} (`{message.chat.id}`)\n\n♢ ʀᴇǫᴜᴇꜱᴛ: {req_text}"
                await client.send_message(LOG_CHANNEL, log_msg); await message.reply_text("✔️ ʀᴇǫᴜᴇꜱᴛ ꜱᴇɴᴛ! ᴀᴅᴍɪɴꜱ ᴡɪʟʟ ʟᴏᴏᴋ ɪɴᴛᴏ ɪᴛ.")
            except Exception as e: logger.error(f"Request log error: {e}"); await message.reply_text("❌ ꜰᴀɪʟᴇᴅ ᴛᴏ ꜱᴇɴᴅ ʀᴇǫᴜᴇꜱᴛ.")
            return

        else:
            if len(message.text) < 2: return 
            s = await message.reply(f"<b><i>⏳ `{message.text}` ꜱᴇᴀʀᴄʜɪɴɢ...</i></b>")
            await auto_filter(client, message, s)
    else: pass 

@Client.on_callback_query(filters.regex(r"^next"))
async def next_page(bot, query: CallbackQuery):
    await query.answer() 
    ident, req, key, offset_str = query.data.split("_")
    try:
        req_user_id = int(req)
        offset = int(offset_str)
    except (ValueError, TypeError):
        return
    if req_user_id != 0 and query.from_user.id != req_user_id:
        return await query.answer(f"ʜᴇʟʟᴏ {query.from_user.first_name},\nɴᴏᴛ ꜰᴏʀ ʏᴏᴜ!", show_alert=True)
    search = BUTTONS.get(key)
    cap = CAP.get(key)
    if not search or not cap:
        await query.answer("ʀᴇǫᴜᴇꜱᴛ ᴇхᴘɪʀᴇᴅ ᴏʀ ɪɴᴠᴀʟɪᴅ.", show_alert=True)
        try:
            await query.message.delete() 
        except:
            pass
        return
    files, n_offset, total = await get_search_results(query=search, offset=offset)
    try:
        n_offset = int(n_offset) if n_offset else ""
    except:
        n_offset = "" 

    if not files:
        return 

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

    btn.insert(0, [InlineKeyboardButton("• ᴜᴘᴅᴀᴛᴇꜱ •", url=UPDATES_LINK)])
    btn.insert(1, [ InlineKeyboardButton("⫸ ʟᴀɴɢᴜᴀɢᴇ", callback_data=f"languages#{key}#{req}#0"),
                   InlineKeyboardButton("⫸ ǫᴜᴀʟɪᴛʏ", callback_data=f"quality#{key}#{req}#0") ])

    pg = math.ceil(offset / MAX_BTN) + 1; total_pg = math.ceil(total / MAX_BTN); pg_lbl = f"ᴘɢ {pg}/{total_pg}"
    pg_row = []
    if offset > 0: 
        prev_offset = max(0, offset - MAX_BTN)
        pg_row.append(InlineKeyboardButton("« ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{prev_offset}"))
    pg_row.append(InlineKeyboardButton(pg_lbl, callback_data="buttons")) 
    if n_offset != "": 
        pg_row.append(InlineKeyboardButton("ɴᴇхᴛ »", callback_data=f"next_{req}_{key}_{n_offset}"))
    if pg_row: btn.append(pg_row)

    try:
        await query.message.edit_text(cap + files_link + del_msg, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML)
    except MessageNotModified:
        pass 
    except FloodWait as e:
        logger.warning(f"FloodWait editing next_page: {e.value}")
        await asyncio.sleep(e.value)
    except Exception as e:
        logger.error(f"Error editing next_page: {e}")


@Client.on_callback_query(filters.regex(r"^languages"))
async def languages_(client: Client, query: CallbackQuery):
    await query.answer()
    _, key, req, offset_str = query.data.split("#")
    try:
        req_user_id = int(req)
        original_offset = int(offset_str)
    except ValueError:
        return
    if req_user_id != query.from_user.id:
        return await query.answer(f"ʜᴇʟʟᴏ {query.from_user.first_name},\nɴᴏᴛ ꜰᴏʀ ʏᴏᴜ!", show_alert=True)
    search = BUTTONS.get(key)
    if not search:
        return await query.answer("ʀᴇǫᴜᴇꜱᴛ ᴇхᴘɪʀᴇᴅ.", show_alert=True)
    btn = []
    lang_iter = iter(LANGUAGES)
    for lang1 in lang_iter:
        try:
            lang2 = next(lang_iter)
            btn.append([ InlineKeyboardButton(lang1.title(), callback_data=f"lang_search#{lang1}#{key}#{original_offset}#{req}"),
                         InlineKeyboardButton(lang2.title(), callback_data=f"lang_search#{lang2}#{key}#{original_offset}#{req}") ])
        except StopIteration:
            btn.append([InlineKeyboardButton(lang1.title(), callback_data=f"lang_search#{lang1}#{key}#{original_offset}#{req}")])
            break
    btn.append([InlineKeyboardButton("⪻ ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{original_offset}")])
    try:
        await query.message.edit_text("<b>ꜱᴇʟᴇᴄᴛ ʟᴀɴɢᴜᴀɢᴇ:</b>", reply_markup=InlineKeyboardMarkup(btn))
    except MessageNotModified:
        pass
    except Exception as e:
        logger.error(f"languages_ error: {e}")

@Client.on_callback_query(filters.regex(r"^quality"))
async def quality(client: Client, query: CallbackQuery):
    await query.answer()
    _, key, req, offset_str = query.data.split("#")
    try:
        req_user_id = int(req)
        original_offset = int(offset_str)
    except ValueError:
        return
    if req_user_id != query.from_user.id:
        return await query.answer(f"ʜᴇʟʟᴏ {query.from_user.first_name},\nɴᴏᴛ ꜰᴏʀ ʏᴏᴜ!", show_alert=True)
    search = BUTTONS.get(key)
    if not search:
        return await query.answer("ʀᴇǫᴜᴇꜱᴛ ᴇхᴘɪʀᴇᴅ.", show_alert=True)
    btn = []
    qual_iter = iter(QUALITY)
    for q1 in qual_iter:
        try:
            q2 = next(qual_iter)
            btn.append([ InlineKeyboardButton(q1.upper(), callback_data=f"qual_search#{q1}#{key}#{original_offset}#{req}"),
                         InlineKeyboardButton(q2.upper(), callback_data=f"qual_search#{q2}#{key}#{original_offset}#{req}") ])
        except StopIteration:
            btn.append([InlineKeyboardButton(q1.upper(), callback_data=f"qual_search#{q1}#{key}#{original_offset}#{req}")])
            break
    btn.append([InlineKeyboardButton("⪻ ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{original_offset}")])
    try:
        await query.message.edit_text("<b>ꜱᴇʟᴇᴄᴛ ǫᴜᴀʟɪᴛʏ:</b>", reply_markup=InlineKeyboardMarkup(btn))
    except MessageNotModified:
        pass
    except Exception as e:
        logger.error(f"quality error: {e}")

@Client.on_callback_query(filters.regex(r"^lang_search"))
async def filter_languages_cb_handler(client: Client, query: CallbackQuery):
    await query.answer()
    _, lang, key, offset_str, req = query.data.split("#")
    try:
        req_user_id = int(req)
        original_offset = int(offset_str)
    except ValueError:
        return
    if req_user_id != query.from_user.id:
        return await query.answer(f"ʜᴇʟʟᴏ {query.from_user.first_name},\nɴᴏᴛ ꜰᴏʀ ʏᴏᴜ!", show_alert=True)
    original_search = BUTTONS.get(key)
    cap = CAP.get(key)
    if not original_search or not cap:
        return await query.answer("ʀᴇǫᴜᴇꜱᴛ ᴇхᴘɪʀᴇᴅ.", show_alert=True)
    current_offset = 0 
    files, next_filtered_offset, total_filtered = await get_search_results(query=original_search, lang=lang, offset=current_offset)
    if not files:
        return await query.answer(f"ɴᴏ '{lang.title()}' ꜰɪʟᴇꜱ ꜰᴏᴜɴᴅ.", show_alert=True)

    temp.FILES[key] = files 
    settings = await get_settings(query.message.chat.id)
    del_msg = f"\n\n<b>⚠️ ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ɪɴ {get_readable_time(DELETE_TIME)}.</b>" if settings.get("auto_delete", False) else ''
    files_link = ''
    btn = []

    if settings.get('links', False): 
        for i, file in enumerate(files):
             files_link += f"<b>\n\n{i+1}. <a href=https://t.me/{temp.U_NAME}?start=filep_{key}_{i}>[{get_size(file['file_size'])}] {file['file_name']}</a></b>"
    else: 
        btn = [[InlineKeyboardButton(f"[{get_size(file['file_size'])}] {file['file_name'][:60]}", callback_data=f"fileidx#{key}#{i}")] for i, file in enumerate(files)]

    btn.insert(0, [InlineKeyboardButton("• ᴜᴘᴅᴀᴛᴇꜱ •", url=UPDATES_LINK)])
    btn.insert(1, [ InlineKeyboardButton("⫸ ʟᴀɴɢᴜᴀɢᴇ", callback_data=f"languages#{key}#{req}#{original_offset}"),
                   InlineKeyboardButton("⫸ ǫᴜᴀʟɪᴛʏ", callback_data=f"quality#{key}#{req}#0") ])

    pg = 1; total_pg = math.ceil(total_filtered / MAX_BTN); pg_lbl = f"ᴘɢ {pg}/{total_pg}"
    pg_row = []
    if next_filtered_offset != "":
        pg_row.append(InlineKeyboardButton(pg_lbl, callback_data="buttons"))
        pg_row.append(InlineKeyboardButton("ɴᴇхᴛ »", callback_data=f"lang_next#{req}#{key}#{lang}#{next_filtered_offset}#{original_offset}"))
    elif total_filtered > 0: 
        pg_row.append(InlineKeyboardButton(pg_lbl, callback_data="buttons"))
    if pg_row: btn.append(pg_row)
    btn.append([InlineKeyboardButton("⪻ ʙᴀᴄᴋ ᴛᴏ ᴀʟʟ", callback_data=f"next_{req}_{key}_{original_offset}")])

    try:
        await query.message.edit_text(cap + files_link + del_msg, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)
    except MessageNotModified:
        pass
    except Exception as e:
        logger.error(f"Error edit lang_search: {e}")

@Client.on_callback_query(filters.regex(r"^qual_search"))
async def quality_search(client: Client, query: CallbackQuery):
    await query.answer()
    _, qual, key, offset_str, req = query.data.split("#")
    try:
        req_user_id = int(req)
        original_offset = int(offset_str)
    except ValueError:
        return
    if req_user_id != query.from_user.id:
        return await query.answer(f"ʜᴇʟʟᴏ {query.from_user.first_name},\nɴᴏᴛ ꜰᴏʀ ʏᴏᴜ!", show_alert=True)
    original_search = BUTTONS.get(key)
    cap = CAP.get(key)
    if not original_search or not cap:
        return await query.answer("ʀᴇǫᴜᴇꜱᴛ ᴇхᴘɪʀᴇᴅ.", show_alert=True)
    current_offset = 0 
    files, next_filtered_offset, total_filtered = await get_search_results(query=original_search, lang=qual, offset=current_offset) 
    if not files:
        return await query.answer(f"ɴᴏ '{qual.upper()}' ꜰɪʟᴇꜱ ꜰᴏᴜɴᴅ.", show_alert=True)

    temp.FILES[key] = files 
    settings = await get_settings(query.message.chat.id)
    del_msg = f"\n\n<b>⚠️ ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ɪɴ {get_readable_time(DELETE_TIME)}.</b>" if settings.get("auto_delete", False) else ''
    files_link = ''
    btn = []

    if settings.get('links', False): 
        for i, file in enumerate(files):
             files_link += f"<b>\n\n{i+1}. <a href=https://t.me/{temp.U_NAME}?start=filep_{key}_{i}>[{get_size(file['file_size'])}] {file['file_name']}</a></b>"
    else: 
        btn = [[InlineKeyboardButton(f"[{get_size(file['file_size'])}] {file['file_name'][:60]}", callback_data=f"fileidx#{key}#{i}")] for i, file in enumerate(files)]

    btn.insert(0, [InlineKeyboardButton("✨ ᴜᴘᴅᴀᴛᴇꜱ", url=UPDATES_LINK)])
    btn.insert(1, [ InlineKeyboardButton("⫸ ʟᴀɴɢᴜᴀɢᴇ", callback_data=f"languages#{key}#{req}#0"),
                   InlineKeyboardButton("⫸ ǫᴜᴀʟɪᴛʏ", callback_data=f"quality#{key}#{req}#{original_offset}") ])

    pg = 1; total_pg = math.ceil(total_filtered / MAX_BTN); pg_lbl = f"ᴘɢ {pg}/{total_pg}"
    pg_row = []
    if next_filtered_offset != "":
        pg_row.append(InlineKeyboardButton(pg_lbl, callback_data="buttons"))
        pg_row.append(InlineKeyboardButton("ɴᴇхᴛ »", callback_data=f"qual_next#{req}#{key}#{qual}#{next_filtered_offset}#{original_offset}"))
    elif total_filtered > 0:
        pg_row.append(InlineKeyboardButton(pg_lbl, callback_data="buttons"))
    if pg_row: btn.append(pg_row)
    btn.append([InlineKeyboardButton("⪻ ʙᴀᴄᴋ ᴛᴏ ᴀʟʟ", callback_data=f"next_{req}_{key}_{original_offset}")])

    try:
        await query.message.edit_text(cap + files_link + del_msg, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)
    except MessageNotModified:
        pass
    except Exception as e:
        logger.error(f"Error edit qual_search: {e}")

@Client.on_callback_query(filters.regex(r"^lang_next"))
async def lang_next_page(bot, query: CallbackQuery):
    await query.answer()
    _, req, key, lang, current_filtered_offset_str, original_offset_str = query.data.split("#")
    try:
        req_user_id = int(req)
        current_filtered_offset = int(current_filtered_offset_str)
        original_offset = int(original_offset_str)
    except ValueError:
        return
    if req_user_id != query.from_user.id:
        return await query.answer(f"ʜᴇʟʟᴏ {query.from_user.first_name},\nɴᴏᴛ ꜰᴏʀ ʏᴏᴜ!", show_alert=True)
    original_search = BUTTONS.get(key)
    cap = CAP.get(key)
    if not original_search or not cap:
        return await query.answer("ʀᴇǫᴜᴇꜱᴛ ᴇхᴘɪʀᴇᴅ.", show_alert=True)

    files, next_filtered_offset, total_filtered = await get_search_results(query=original_search, lang=lang, offset=current_filtered_offset)
    if not files:
        return 

    temp.FILES[key] = files
    settings = await get_settings(query.message.chat.id)
    del_msg = f"\n\n<b>⚠️ ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ɪɴ {get_readable_time(DELETE_TIME)}.</b>" if settings.get("auto_delete", False) else ''
    files_link = ''
    btn = []
    
    if settings.get('links', False): 
        for i, file in enumerate(files):
             files_link += f"<b>\n\n{current_filtered_offset + 1 + i}. <a href=https://t.me/{temp.U_NAME}?start=filep_{key}_{i}>[{get_size(file['file_size'])}] {file['file_name']}</a></b>"
    else: 
        btn = [[InlineKeyboardButton(f"[{get_size(file['file_size'])}] {file['file_name'][:60]}", callback_data=f"fileidx#{key}#{i}")] for i, file in enumerate(files)]

    btn.insert(0, [InlineKeyboardButton("• ᴜᴘᴅᴀᴛᴇꜱ •", url=UPDATES_LINK)])
    btn.insert(1, [ InlineKeyboardButton("⫸ ʟᴀɴɢᴜᴀɢᴇ", callback_data=f"languages#{key}#{req}#{original_offset}"),
                   InlineKeyboardButton("⫸ ǫᴜᴀʟɪᴛʏ", callback_data=f"quality#{key}#{req}#0") ])

    pg = math.ceil(current_filtered_offset / MAX_BTN) + 1; total_pg = math.ceil(total_filtered / MAX_BTN); pg_lbl = f"ᴘɢ {pg}/{total_pg}"
    pg_row = []
    prev_filtered_offset = max(0, current_filtered_offset - MAX_BTN)
    pg_row.append(InlineKeyboardButton("« ʙᴀᴄᴋ", callback_data=f"lang_next#{req}#{key}#{lang}#{prev_filtered_offset}#{original_offset}"))
    pg_row.append(InlineKeyboardButton(pg_lbl, callback_data="buttons"))
    if next_filtered_offset != "":
        pg_row.append(InlineKeyboardButton("ɴᴇхᴛ »", callback_data=f"lang_next#{req}#{key}#{lang}#{next_filtered_offset}#{original_offset}"))
    btn.append(pg_row)
    btn.append([InlineKeyboardButton("⪻ ʙᴀᴄᴋ ᴛᴏ ᴀʟʟ", callback_data=f"next_{req}_{key}_{original_offset}")])

    try:
        await query.message.edit_text(cap + files_link + del_msg, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)
    except MessageNotModified:
        pass
    except Exception as e:
        logger.error(f"Error edit lang_next: {e}")

@Client.on_callback_query(filters.regex(r"^qual_next"))
async def quality_next_page(bot, query: CallbackQuery):
    await query.answer()
    _, req, key, qual, current_filtered_offset_str, original_offset_str = query.data.split("#")
    try:
        req_user_id = int(req)
        current_filtered_offset = int(current_filtered_offset_str)
        original_offset = int(original_offset_str)
    except ValueError:
        return
    if req_user_id != query.from_user.id:
        return await query.answer(f"ʜᴇʟʟᴏ {query.from_user.first_name},\nɴᴏᴛ ꜰᴏʀ ʏᴏᴜ!", show_alert=True)
    original_search = BUTTONS.get(key)
    cap = CAP.get(key)
    if not original_search or not cap:
        return await query.answer("ʀᴇǫᴜᴇꜱᴛ ᴇхᴘɪʀᴇᴅ.", show_alert=True)

    files, next_filtered_offset, total_filtered = await get_search_results(query=original_search, lang=qual, offset=current_filtered_offset) 
    if not files:
        return 

    temp.FILES[key] = files
    settings = await get_settings(query.message.chat.id)
    del_msg = f"\n\n<b>⚠️ ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ɪɴ {get_readable_time(DELETE_TIME)}.</b>" if settings.get("auto_delete", False) else ''
    files_link = ''
    btn = []
    
    if settings.get('links', False): 
        for i, file in enumerate(files):
             files_link += f"<b>\n\n{current_filtered_offset + 1 + i}. <a href=https://t.me/{temp.U_NAME}?start=filep_{key}_{i}>[{get_size(file['file_size'])}] {file['file_name']}</a></b>"
    else: 
        btn = [[InlineKeyboardButton(f"[{get_size(file['file_size'])}] {file['file_name'][:60]}", callback_data=f"fileidx#{key}#{i}")] for i, file in enumerate(files)]

    btn.insert(0, [InlineKeyboardButton("• ᴜᴘᴅᴀᴛᴇꜱ •", url=UPDATES_LINK)])
    btn.insert(1, [ InlineKeyboardButton("⫸ ʟᴀɴɢᴜᴀɢᴇ", callback_data=f"languages#{key}#{req}#0"),
                   InlineKeyboardButton("⫸ ǫᴜᴀʟɪᴛʏ", callback_data=f"quality#{key}#{req}#{original_offset}") ])

    pg = math.ceil(current_filtered_offset / MAX_BTN) + 1; total_pg = math.ceil(total_filtered / MAX_BTN); pg_lbl = f"ᴘɢ {pg}/{total_pg}"
    pg_row = []
    prev_filtered_offset = max(0, current_filtered_offset - MAX_BTN)
    pg_row.append(InlineKeyboardButton("« ʙᴀᴄᴋ", callback_data=f"qual_next#{req}#{key}#{qual}#{prev_filtered_offset}#{original_offset}"))
    pg_row.append(InlineKeyboardButton(pg_lbl, callback_data="buttons"))
    if next_filtered_offset != "":
        pg_row.append(InlineKeyboardButton("ɴᴇхᴛ »", callback_data=f"qual_next#{req}#{key}#{qual}#{next_filtered_offset}#{original_offset}"))
    btn.append(pg_row)
    btn.append([InlineKeyboardButton("⪻ ʙᴀᴄᴋ ᴛᴏ ᴀʟʟ", callback_data=f"next_{req}_{key}_{original_offset}")])

    try:
        await query.message.edit_text(cap + files_link + del_msg, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)
    except MessageNotModified:
        pass
    except Exception as e:
        logger.error(f"Error edit qual_next: {e}")

@Client.on_callback_query(filters.regex(r"^spolling"))
async def advantage_spoll_choker(bot, query: CallbackQuery):
    _, id, user = query.data.split('#')
    try:
        req_user_id = int(user)
    except ValueError:
        return
    if req_user_id != 0 and query.from_user.id != req_user_id:
        return await query.answer(f"ʜᴇʟʟᴏ {query.from_user.first_name},\nɴᴏᴛ ꜰᴏʀ ʏᴏᴜ!", show_alert=True)
    await query.answer("ꜱᴇᴀʀᴄʜɪɴɢ ꜱᴜɢɢᴇꜱᴛɪᴏɴ...")
    try:
        movie = await get_poster(id, id=True)
        if not movie:
            raise ValueError("IMDb fail")
        search = movie.get('title', "N/A")
        year = movie.get('year')
        if search == "N/A":
            raise ValueError("No title")
        search_cleaned = re.sub(r"[:()]", "", search).strip()
        search_query = f"{search_cleaned} {year}" if year else search_cleaned
    except Exception as e:
        logger.error(f"Spell check poster error ID {id}: {e}")
        await query.message.edit("❌ ᴄᴏᴜʟᴅ ɴᴏᴛ ꜰᴇᴛᴄʜ ᴅᴇᴛᴀɪʟꜱ ꜰᴏʀ ᴛʜᴀᴛ ꜱᴜɢɢᴇꜱᴛɪᴏɴ.")
        return
    s = await query.message.edit(f"<b><i>✔️ `{search_query}` ᴄʜᴇᴄᴋɪɴɢ...</i></b>")
    files, offset, total_results = await get_search_results(query=search_query, offset=0)
    if files:
        k = (search_query, files, offset, total_results)
        await auto_filter(bot, query, s, spoll=k) 
    else:
        not_found_text = f"""👋 ʜᴇʟʟᴏ {query.from_user.mention},

ɪ ᴄᴏᴜʟᴅɴ'ᴛ ꜰɪɴᴅ `<b>{search_query}</b>` ɪɴ ᴍʏ ᴅᴀᴛᴀʙᴀꜱᴇ! 

♢ ᴅᴏᴜʙʟᴇ-ᴄʜᴇᴄᴋ ᴛʜᴇ ꜱᴘᴇʟʟɪɴɢ.
♢ ᴛʀʏ ᴜꜱɪɴɢ ᴍᴏʀᴇ ꜱᴘᴇᴄɪꜰɪᴄ ᴋᴇʏᴡᴏʀᴅꜱ.
♢ ᴛʜᴇ ꜰɪʟᴇ ᴍɪɢʜᴛ ɴᴏᴛ ʙᴇ ʀᴇʟᴇᴀꜱᴇᴅ ᴏʀ ᴀᴅᴅᴇᴅ ʏᴇᴛ."""
        k = await s.edit(not_found_text)
        try:
            await bot.send_message(LOG_CHANNEL, f"#ɴᴏ_ʀᴇꜱᴜʟᴛ_ᴀꜰᴛᴇʀ_ꜱᴘᴇʟʟ\n\n♢ ʀᴇǫ: {query.from_user.mention}\n♢ ᴏʀɪɢ: `{BUTTONS.get(query.message.reply_markup.inline_keyboard[0][0].callback_data.split('#')[1], 'Unknown')}`\n♢ ꜱᴜɢɢ: `{search_query}`")
        except:
            pass
        await asyncio.sleep(60)
        try: await k.delete()
        except: pass
        try: await query.message.reply_to_message.delete()
        except: pass

@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    data = query.data
    if data and data not in ["buttons"] and not data.startswith(("set_", "default_", "delete", "un", "kick_", "spolling", "send_all", "get_del_", "file")):
        try:
             await query.answer()
        except: 
             pass

    loop = asyncio.get_running_loop()

    if data == "close_data":
        try: user = query.message.reply_to_message.from_user.id
        except: user = query.from_user.id
        if int(user) != 0 and query.from_user.id != int(user): return await query.answer(f"ʜᴇʟʟᴏ {query.from_user.first_name},\nɴᴏᴛ ꜰᴏʀ ʏᴏᴜ!", show_alert=True)
        await query.message.delete()
        try:
            await query.message.reply_to_message.delete()
        except:
            pass
        return 

    elif data.startswith("fileidx"):
        _, key, idx_str = data.split("#")
        try: idx = int(idx_str)
        except ValueError: return await query.answer("Invalid file index.", show_alert=True)
        
        try: user = query.message.reply_to_message.from_user.id
        except: user = query.message.from_user.id
        if int(user) != 0 and query.from_user.id != int(user): return await query.answer(f"ʜᴇʟʟᴏ {query.from_user.first_name},\nɴᴏᴛ ꜰᴏʀ ʏᴏᴜ!", show_alert=True)
        
        await query.answer(url=f"https://t.me/{temp.U_NAME}?start=filep_{key}_{idx}")
        return

    elif data.startswith("file"): 
        ident, file_id = data.split("#")
        try: user = query.message.reply_to_message.from_user.id
        except: user = query.message.from_user.id
        if int(user) != 0 and query.from_user.id != int(user): return await query.answer(f"ʜᴇʟʟᴏ {query.from_user.first_name},\nɴᴏᴛ ꜰᴏʀ ʏᴏᴜ!", show_alert=True)
        await query.answer(url=f"https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file_id}")
        return

    elif data.startswith("get_del_file"):
        ident, group_id, file_id = data.split("#")
        await query.answer(url=f"https://t.me/{temp.U_NAME}?start=file_{group_id}_{file_id}")
        try: await query.message.delete()
        except: pass
        return

    elif data.startswith("get_del_send_all_files"):
        ident, group_id, key = data.split("#")
        await query.answer(url=f"https://t.me/{temp.U_NAME}?start=all_{group_id}_{key}")
        try: await query.message.delete()
        except: pass
        return

    elif data.startswith("stream"):
        file_id = data.split('#', 1)[1]
        try:
            msg = await client.send_cached_media(chat_id=BIN_CHANNEL, file_id=file_id)
            watch = f"{URL}watch/{msg.id}"; download = f"{URL}download/{msg.id}"
            btn=[[ InlineKeyboardButton("• ᴡᴀᴛᴄʜ •", url=watch), InlineKeyboardButton("• ᴅᴏᴡɴʟᴏᴀᴅ •", url=download)], [ InlineKeyboardButton('❌ ᴄʟᴏꜱᴇ', callback_data='close_data')]]
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
        except Exception as e: logger.error(f"Stream CB error: {e}"); await query.answer("ᴇʀʀᴏʀ ɢᴇɴᴇʀᴀᴛɪɴɢ ꜱᴛʀᴇᴀᴍ ʟɪɴᴋꜱ.", show_alert=True)
        return

    elif data.startswith("checksub"):
        ident, mc = data.split("#")
        btn = await is_subscribed(client, query)
        if btn:
            await query.answer("❗ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟꜱ ꜰɪʀꜱᴛ.", show_alert=True)
            btn.append([InlineKeyboardButton("🔁 ᴛʀʏ ᴀɢᴀɪɴ", callback_data=f"checksub#{mc}")])
            try: await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
            except MessageNotModified: pass
        else:
            await query.answer(url=f"https://t.me/{temp.U_NAME}?start={mc}")
            try: await query.message.delete()
            except: pass
        return

    elif data == "buttons":
        await query.answer() 
        return

    elif data == "instructions":
        await query.answer("♢ ᴍᴏᴠɪᴇ: `Name Year`\n♢ ꜱᴇʀɪᴇꜱ: `Name S01E01`", show_alert=True)
        return

    elif data == "start":
        buttons = [[ InlineKeyboardButton("➕ ᴀᴅᴅ ᴛᴏ ɢʀᴏᴜᴘ", url=f'http://t.me/{temp.U_NAME}?startgroup=start') ], [ InlineKeyboardButton('• ᴜᴘᴅᴀᴛᴇꜱ •', url=UPDATES_LINK), InlineKeyboardButton('• ꜱᴜᴘᴘᴏʀᴛ •', url=SUPPORT_LINK) ], [ InlineKeyboardButton('• ʜᴇʟᴘ •', callback_data='help'), InlineKeyboardButton('🔍 ɪɴʟɪɴᴇ', switch_inline_query_current_chat=''), InlineKeyboardButton('• ᴀʙᴏᴜᴛ •', callback_data='about') ]]
        try:
            start_caption = script.START_TXT.format(query.from_user.mention, get_wish()) 
            await query.edit_message_media(InputMediaPhoto(random.choice(PICS), caption=start_caption), reply_markup=InlineKeyboardMarkup(buttons))
        except MessageNotModified: pass
        except Exception as e: logger.error(f"Start CB Error: {e}")
        return

    elif data == "about":
        buttons = [[ InlineKeyboardButton('• ꜱᴛᴀᴛᴜꜱ •', callback_data='stats'), InlineKeyboardButton('• ꜱᴏᴜʀᴄᴇ •', callback_data='source') ], [ InlineKeyboardButton('• ᴏᴡɴᴇʀ •', callback_data='owner') ], [ InlineKeyboardButton('« ʙᴀᴄᴋ', callback_data='start') ]]
        try:
            about_caption = script.MY_ABOUT_TXT 
            await query.edit_message_media(InputMediaPhoto(random.choice(PICS), caption=about_caption), reply_markup=InlineKeyboardMarkup(buttons))
        except MessageNotModified: pass
        except Exception as e: logger.error(f"About CB Error: {e}")
        return

    elif data == "stats":
            if query.from_user.id not in ADMINS: return await query.answer("ᴀᴅᴍɪɴꜱ ᴏɴʟʏ!", show_alert=True)
            sts_msg = None
            try: sts_msg = await query.message.edit_media( media=InputMediaPhoto(random.choice(PICS), caption="ɢᴀᴛʜᴇʀɪɴɢ ꜱᴛᴀᴛꜱ..."), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⏳', callback_data='buttons')]]))
            except Exception:
                 try: sts_msg = await query.message.edit(" ɢᴀᴛʜᴇʀɪɴɢ ꜱᴛᴀᴛꜱ...")
                 except: return await query.answer("ᴇʀʀᴏʀ ɪɴɪᴛɪᴀᴛɪɴɢ ꜱᴛᴀᴛꜱ.", show_alert=True)
            
            async def get_stat_safe(func, *args):
                try: call_func = partial(func, *args) if args else func; return await loop.run_in_executor(None, call_func)
                except Exception as e: logger.error(f"Stat error {func.__name__ if hasattr(func, '__name__') else 'unknown'}: {e}"); return "ᴇʀʀ"
            
            total_files_task = get_stat_safe(get_total_files_count)
            users_task = get_stat_safe(db.total_users_count)
            chats_task = get_stat_safe(db.total_chat_count)
            data_db_size_task = get_stat_safe(db.get_data_db_size)
            all_files_db_stats_task = get_stat_safe(db.get_all_files_db_stats)

            total_files, users, chats, used_data_db_size_raw, all_files_db_stats = await asyncio.gather(
                total_files_task,
                users_task,
                chats_task,
                data_db_size_task,
                all_files_db_stats_task
            )
            
            used_data_db_size = get_size(used_data_db_size_raw) if isinstance(used_data_db_size_raw, (int, float)) else used_data_db_size_raw

            db_stats_str = ""
            if isinstance(all_files_db_stats, list):
                for stat in all_files_db_stats:
                    if stat.get('error'):
                        db_stats_str += f"│ 🗂️ {stat['name']}: <code>Error</code>\n"
                    else:
                        db_stats_str += f"│ 🗂️ {stat['name']} ({stat.get('coll_count', 'N/A')} ꜰɪʟᴇꜱ): <code>{get_size(stat['size'])}</code>\n"
            else:
                db_stats_str = "│ 🗂️ ꜰɪʟᴇ ᴅʙ ꜱᴛᴀᴛꜱ: <code>ᴇʀʀ</code>\n"

                
            uptime = get_readable_time(time_now() - temp.START_TIME)
            
            stg = await loop.run_in_executor(None, db.get_bot_sttgs) 
            current_db_index = stg.get('CURRENT_DB_INDEX', 0) 
            
            stats_text = script.STATUS_TXT.format(
                users, 
                chats, 
                used_data_db_size, 
                total_files,
                current_db_index + 1, 
                db_stats_str.rstrip('\n'), 
                uptime
            )
            
            buttons = [[ InlineKeyboardButton('« ʙᴀᴄᴋ', callback_data='about') ]]
            try: await sts_msg.edit_media( media=InputMediaPhoto(random.choice(PICS), caption=stats_text), reply_markup=InlineKeyboardMarkup(buttons) )
            except MessageNotModified: pass
            except Exception as e: logger.error(f"Final stats edit error: {e}"); await sts_msg.edit(stats_text, reply_markup=InlineKeyboardMarkup(buttons))
            return

    elif data == "owner":
        buttons = [[InlineKeyboardButton('« ʙᴀᴄᴋ', callback_data='about')]]
        try:
            owner_caption = script.MY_OWNER_TXT 
            await query.edit_message_media(InputMediaPhoto(random.choice(PICS), caption=owner_caption), reply_markup=InlineKeyboardMarkup(buttons))
        except MessageNotModified: 
            pass
        except Exception as e: 
            logger.error(f"Owner CB Error: {e}")
        return

    elif data == "help":
        buttons = [[ InlineKeyboardButton('• ᴜꜱᴇʀ •', callback_data='user_command'), InlineKeyboardButton('• ᴀᴅᴍɪɴ •', callback_data='admin_command') ], [ InlineKeyboardButton('« ʙᴀᴄᴋ', callback_data='start') ]]
        try:
            help_caption = script.HELP_TXT.format(query.from_user.mention) 
            await query.edit_message_media(InputMediaPhoto(random.choice(PICS), caption=help_caption), reply_markup=InlineKeyboardMarkup(buttons))
        except MessageNotModified: pass
        except Exception as e: logger.error(f"Help CB Error: {e}")
        return

    elif data == "user_command":
        buttons = [[ InlineKeyboardButton('« ʙᴀᴄᴋ', callback_data='help') ]]
        try:
            user_cmd_caption = script.USER_COMMAND_TXT 
            await query.edit_message_media(InputMediaPhoto(random.choice(PICS), caption=user_cmd_caption), reply_markup=InlineKeyboardMarkup(buttons))
        except MessageNotModified: pass
        except Exception as e: logger.error(f"User CMD CB Error: {e}")
        return

    elif data == "admin_command":
        if query.from_user.id not in ADMINS: return await query.answer("ᴀᴅᴍɪɴꜱ ᴏɴʟʏ!", show_alert=True)
        buttons = [[ InlineKeyboardButton('« ʙᴀᴄᴋ', callback_data='help') ]]
        try:
            admin_cmd_caption = script.ADMIN_COMMAND_TXT 
            await query.edit_message_media(InputMediaPhoto(random.choice(PICS), caption=admin_cmd_caption), reply_markup=InlineKeyboardMarkup(buttons))
        except MessageNotModified: pass
        except Exception as e: logger.error(f"Admin CMD CB Error: {e}")
        return

    elif data == "source":
        buttons = [[ InlineKeyboardButton('« ʙᴀᴄᴋ', callback_data='about') ]]
        try:
            source_caption = script.SOURCE_TXT 
            await query.edit_message_media(InputMediaPhoto(random.choice(PICS), caption=source_caption), reply_markup=InlineKeyboardMarkup(buttons))
        except MessageNotModified: pass
        except Exception as e: logger.error(f"Source CB Error: {e}")
        return

    elif data.startswith("bool_setgs"):
        ident, set_type, status, grp_id_str = data.split("#")
        try: grp_id = int(grp_id_str)
        except ValueError: return await query.answer("ɪɴᴠᴀʟɪᴅ ɪᴅ.", show_alert=True)
        userid = query.from_user.id
        if not await is_check_admin(client, grp_id, userid): return await query.answer("ɴᴏᴛ ᴀᴅᴍɪɴ.", show_alert=True)
        new_status = not (status == "True"); await save_group_settings(grp_id, set_type, new_status)
        btn = await get_grp_stg(grp_id);
        try: await query.message.edit_reply_markup(InlineKeyboardMarkup(btn))
        except MessageNotModified: pass
        await query.answer(f"{set_type.replace('_',' ').upper()} ꜱᴇᴛ ᴛᴏ {new_status}"); 
        return

    elif data.startswith(("imdb_setgs", "welcome_setgs", "tutorial_setgs", "shortlink_setgs", "caption_setgs")):
        setting_type = data.split("_")[0]; _, grp_id_str = data.split("#")
        try: grp_id = int(grp_id_str)
        except ValueError: return await query.answer("ɪɴᴠᴀʟɪᴅ ɪᴅ.", show_alert=True)
        userid = query.from_user.id
        if not await is_check_admin(client, grp_id, userid): return await query.answer("ɴᴏᴛ ᴀᴅᴍɪɴ.", show_alert=True)
        settings = await get_settings(grp_id);
        key_map = {'imdb': 'template', 'welcome': 'welcome_text', 'tutorial': 'tutorial', 'shortlink': 'url', 'caption': 'caption'}
        current_val = settings.get(key_map.get(setting_type), "N/A")
        if setting_type == 'shortlink': current_val = f"{settings.get('url', 'N/A')} - {settings.get('api', 'N/A')}"
        btn = [[ InlineKeyboardButton(f'ꜱᴇᴛ {setting_type.replace("_"," ").upper()}', callback_data=f'set_{setting_type}#{grp_id}') ],
               [ InlineKeyboardButton(f'ᴅᴇꜰᴀᴜʟᴛ {setting_type.replace("_"," ").upper()}', callback_data=f'default_{setting_type}#{grp_id}') ],
               [ InlineKeyboardButton('« ʙᴀᴄᴋ', callback_data=f'back_setgs#{grp_id}') ]]
        await query.message.edit(f'⚙️ {setting_type.replace("_"," ").upper()} ꜱᴇᴛᴛɪɴɢꜱ:\n\nᴄᴜʀʀᴇɴᴛ:\n`{current_val}`', reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
        return

    elif data.startswith(("set_imdb", "set_welcome", "set_tutorial", "set_shortlink", "set_caption")):
        setting_type = data.split("_")[1].split("#")[0]; _, grp_id_str = data.split("#")
        try: grp_id = int(grp_id_str)
        except ValueError: return await query.answer("ɪɴᴠᴀʟɪᴅ ɪᴅ.", show_alert=True)
        userid = query.from_user.id
        if not await is_check_admin(client, grp_id, userid): return await query.answer("ɴᴏᴛ ᴀᴅᴍɪɴ.", show_alert=True)
        key_map = {'imdb': 'template', 'welcome': 'welcome_text', 'tutorial': 'tutorial', 'shortlink': 'url', 'caption': 'caption'}
        value_key = key_map.get(setting_type); api_key = 'api' if setting_type == 'shortlink' else None
        prompt_base = f"➡️ ꜱᴇɴᴅ ɴᴇᴡ {setting_type.replace('_',' ').upper()}"
        prompt_suffix = " ᴜʀʟ." if setting_type == 'shortlink' else (" (ᴜꜱᴇ ꜰᴏʀᴍᴀᴛ ᴋᴇʏꜱ)." if setting_type in ['imdb', 'welcome', 'caption'] else ".")
        prompt = prompt_base + prompt_suffix
        ask_msg = None
        try:
            ask_msg = await query.message.edit(prompt)
            r1 = await client.listen(chat_id=query.message.chat.id, user_id=userid, timeout=300)
            if not r1 or not r1.text: raise asyncio.TimeoutError
            v1 = r1.text.strip(); await r1.delete()
            v2 = None
            if api_key:
                 await ask_msg.edit("➡️ ꜱᴇɴᴅ ᴀᴘɪ ᴋᴇʏ."); r2 = await client.listen(chat_id=query.message.chat.id, user_id=userid, timeout=300)
                 if not r2 or not r2.text: raise asyncio.TimeoutError
                 v2 = r2.text.strip(); await r2.delete()
            await save_group_settings(grp_id, value_key, v1)
            if api_key and v2: await save_group_settings(grp_id, api_key, v2)
            back_btn = [[ InlineKeyboardButton('« ʙᴀᴄᴋ', callback_data=f'{setting_type}_setgs#{grp_id}') ]]
            success_base = f"✔️ ᴜᴘᴅᴀᴛᴇᴅ {setting_type.replace('_',' ').upper()}!\n\n"
            success_detail = (f"ᴜʀʟ: `{v1}`\nᴀᴘɪ: `{v2}`" if setting_type == 'shortlink' else "ɴᴇᴡ:\n" + f"`{v1}`")
            success = success_base + success_detail
            if ask_msg: await ask_msg.edit(success, reply_markup=InlineKeyboardMarkup(back_btn))
            else: await query.message.reply(success, reply_markup=InlineKeyboardMarkup(back_btn))
        except asyncio.TimeoutError: await ask_msg.edit("⏰ ᴛɪᴍᴇᴏᴜᴛ.") if ask_msg else None
        except Exception as e: logger.error(f"Listen error set_{setting_type}: {e}"); await ask_msg.edit("ᴇʀʀᴏʀ ᴘʀᴏᴄᴇꜱꜱɪɴɢ ɪɴᴘᴜᴛ.") if ask_msg else None
        return

    elif data.startswith(("default_imdb", "default_welcome", "default_tutorial", "default_shortlink", "default_caption")):
        setting_type = data.split("_")[1].split("#")[0]; _, grp_id_str = data.split("#")
        try: grp_id = int(grp_id_str)
        except ValueError: return await query.answer("ɪɴᴠᴀʟɪᴅ ɪᴅ.", show_alert=True)
        userid = query.from_user.id
        if not await is_check_admin(client, grp_id, userid): return await query.answer("ɴᴏᴛ ᴀᴅᴍɪɴ.", show_alert=True)
        default_map = {'imdb': ('template', script.IMDB_TEMPLATE), 'welcome': ('welcome_text', script.WELCOME_TEXT), 'tutorial': ('tutorial', TUTORIAL), 'shortlink': [('url', SHORTLINK_URL), ('api', SHORTLINK_API)], 'caption': ('caption', script.FILE_CAPTION)}
        setting_info = default_map.get(setting_type);
        if not setting_info: return await query.answer("ɪɴᴠᴀʟɪᴅ ꜱᴇᴛᴛɪɴɢ.", show_alert=True)
        if isinstance(setting_info, list): [await save_group_settings(grp_id, k, dv) for k, dv in setting_info]
        else: k, dv = setting_info; await save_group_settings(grp_id, k, dv)
        back_btn = [[ InlineKeyboardButton('« ʙᴀᴄᴋ', callback_data=f'{setting_type}_setgs#{grp_id}') ]]
        await query.message.edit(f"✔️ ʀᴇꜱᴇᴛ {setting_type.replace('_',' ').upper()} ᴛᴏ ᴅᴇꜰᴀᴜʟᴛ.", reply_markup=InlineKeyboardMarkup(back_btn))
        return

    elif data.startswith("back_setgs"):
        _, grp_id_str = data.split("#")
        try: grp_id = int(grp_id_str)
        except ValueError: return await query.answer("ɪɴᴠᴀʟɪᴅ ɪᴅ.", show_alert=True)
        userid = query.from_user.id
        if not await is_check_admin(client, grp_id, userid): return await query.answer("ɴᴏᴛ ᴀᴅᴍɪɴ.", show_alert=True)
        btn = await get_grp_stg(grp_id); 
        chat = await client.get_chat(grp_id)
        await query.message.edit(f"⚙️ ꜱᴇᴛᴛɪɴɢꜱ ꜰᴏʀ <b>'{chat.title}'</b>:", reply_markup=InlineKeyboardMarkup(btn))
        return

    elif data == "open_group_settings":
        userid = query.from_user.id; grp_id = query.message.chat.id
        if not await is_check_admin(client, grp_id, userid): return await query.answer("ɴᴏᴛ ᴀᴅᴍɪɴ.", show_alert=True)
        btn = await get_grp_stg(grp_id);
        await query.message.edit(f"⚙️ ꜱᴇᴛᴛɪɴɢꜱ ꜰᴏʀ <b>'{query.message.chat.title}'</b>:", reply_markup=InlineKeyboardMarkup(btn))
        return

    elif data == "open_pm_settings":
        userid = query.from_user.id; grp_id = query.message.chat.id
        if not await is_check_admin(client, grp_id, userid): return await query.answer("ɴᴏᴛ ᴀᴅᴍɪɴ.", show_alert=True)
        btn = await get_grp_stg(grp_id);
        pm_btn = [[ InlineKeyboardButton('ɢᴏ ᴛᴏ ᴘᴍ ➔', url=f"https://t.me/{temp.U_NAME}?start=settings_{grp_id}") ]]
        try: await client.send_message(userid, f"⚙️ ꜱᴇᴛᴛɪɴɢꜱ ꜰᴏʀ <b>'{query.message.chat.title}'</b>:", reply_markup=InlineKeyboardMarkup(btn)); await query.message.edit("✔️ ꜱᴇɴᴛ ᴛᴏ ᴘᴍ.", reply_markup=InlineKeyboardMarkup(pm_btn))
        except Exception as e: logger.warning(f"PM settings error {userid}: {e}"); await query.answer(url=f"https.me/{temp.U_NAME}?start=settings_{grp_id}"); await query.message.edit("⚠️ ᴄʟɪᴄᴋ ʙᴜᴛᴛᴏɴ ᴛᴏ ᴏᴘᴇɴ ɪɴ ᴘᴍ.", reply_markup=InlineKeyboardMarkup(pm_btn))
        return

    elif data.startswith("delete"):
        if query.from_user.id not in ADMINS: return await query.answer("ᴀᴅᴍɪɴꜱ ᴏɴʟʏ.", show_alert=True)
        _, query_text = data.split("_", 1); await query.message.edit('⏳ ᴅᴇʟᴇᴛɪɴɢ...')
        deleted_count = await delete_files(query_text);
        await query.message.edit(f'✔️ ᴅᴇʟᴇᴛᴇᴅ {deleted_count} ꜰɪʟᴇꜱ ꜰᴏʀ `{query_text}`.')
        return

    elif data.startswith("send_all"):
        ident, key, req = data.split("#");
        try: req_user_id = int(req)
        except ValueError: return
        if req_user_id != query.from_user.id: return await query.answer(f"ʜᴇʟʟᴏ {query.from_user.first_name},\nɴᴏᴛ ꜰᴏʀ ʏᴏᴜ!", show_alert=True)
        files = temp.FILES.get(key);
        if not files: return await query.answer("ʀᴇǫᴜᴇꜱᴛ ᴇхᴘɪʀᴇᴅ.", show_alert=True)
        await query.answer(url=f"https://t.me/{temp.U_NAME}?start=all_{query.message.chat.id}_{key}")
        return

    elif data in ["unmute_all_members", "unban_all_members", "kick_muted_members", "kick_deleted_accounts_members"]:
        if not await is_check_admin(client, query.message.chat.id, query.from_user.id): return await query.answer("ɴᴏᴛ ᴀᴅᴍɪɴ.", show_alert=True)
        action = data.split("_")[0]; target = data.split("_")[1]; filter_type = None
        success = 0; errors = 0; start = time_now()
        await query.message.edit(f"⏳ `{action.upper()} {target.upper()}`...")
        try:
            if target == "muted": filter_type = enums.ChatMembersFilter.RESTRICTED
            elif target == "all" and action == "unmute": filter_type = enums.ChatMembersFilter.RESTRICTED
            elif target == "all" and action == "unban": filter_type = enums.ChatMembersFilter.BANNED
            elif target == "deleted": filter_type = enums.ChatMembersFilter.SEARCH 
            async for m in client.get_chat_members(query.message.chat.id, filter=filter_type):
                 u = m.user;
                 if not u or u.is_bot or u.id == temp.ME or m.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]: continue
                 act = False
                 try:
                      if action == "unmute" and target == "all" and m.status == enums.ChatMemberStatus.RESTRICTED: await client.unban_chat_member(query.message.chat.id, u.id); act = True
                      elif action == "unban" and target == "all" and m.status == enums.ChatMemberStatus.BANNED: await client.unban_chat_member(query.message.chat.id, u.id); act = True
                      elif action == "kick" and target == "muted" and m.status == enums.ChatMemberStatus.RESTRICTED: await client.ban_chat_member(query.message.chat.id, u.id, until_date=datetime.now(timezone.utc) + timedelta(seconds=35)); act = True
                      elif action == "kick" and target == "deleted" and filter_type == enums.ChatMembersFilter.SEARCH and u.is_deleted:
                          await client.ban_chat_member(query.message.chat.id, u.id, until_date=datetime.now(timezone.utc) + timedelta(seconds=35)); act = True
                      if act: success += 1; await asyncio.sleep(0.1) 
                 except FloodWait as e: logger.warning(f"FloodWait {action}: {e.value}"); await asyncio.sleep(e.value); errors += 1
                 except Exception as e: logger.error(f"Error {action} user {u.id}: {e}"); errors += 1
        except Exception as outer_e: logger.error(f"Error {action} {target} loop: {outer_e}"); await query.message.edit(f"❌ ᴇʀʀᴏʀ:\n`{outer_e}`"); return
        elapsed = get_readable_time(time_now() - start)
        final_base = f"✔️ ᴏᴘᴇʀᴀᴛɪᴏɴ `{action.upper()} {target.upper()}` ᴄᴏᴍᴘʟᴇᴛᴇᴅ ɪɴ {elapsed}.\n\n♢ ꜱᴜᴄᴄᴇꜱꜱ:"
        final_detail = f" <code>{success}</code>\n♢ ᴇʀʀᴏʀꜱ: <code>{errors}</code>"
        final = final_base + final_detail
        if success == 0 and errors == 0: final = f"ɴᴏ {target.upper()} ᴜꜱᴇʀꜱ ꜰᴏᴜɴᴅ ᴛᴏ {action.upper()}."
        try: await query.message.edit(final)
        except: await query.message.reply(final); await query.message.delete() 
        return


async def auto_filter(client, msg, s, spoll=False):
    if not spoll:
        message = msg; settings = await get_settings(message.chat.id)
        search = re.sub(r"\s+", " ", re.sub(r"[-:\"';!]", " ", message.text)).strip()
        if not search: return await s.edit("ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ᴛᴇхᴛ ᴛᴏ ꜱᴇᴀʀᴄʜ.")
        files, offset, total_results = await get_search_results(query=search, offset=0)
        if not files:
            if settings.get("spell_check", True): return await advantage_spell_chok(message, s)
            else:
                 not_found_text = f"""👋 ʜᴇʟʟᴏ {message.from_user.mention},

ɪ ᴄᴏᴜʟᴅɴ'ᴛ ꜰɪɴᴅ `<b>{search}</b>` ɪɴ ᴍʏ ᴅᴀᴛᴀʙᴀꜱᴇ! 

♢ ᴅᴏᴜʙʟᴇ-ᴄʜᴇᴄᴋ ᴛʜᴇ ꜱᴘᴇʟʟɪɴɢ.
♢ ᴛʀʏ ᴜꜱɪɴɢ ᴍᴏʀᴇ ꜱᴘᴇᴄɪꜰɪᴄ ᴋᴇʏᴡᴏʀᴅꜱ.
♢ ᴛʜᴇ ꜰɪʟᴇ ᴍɪɢʜᴛ ɴᴏᴛ ʙᴇ ʀᴇʟᴇᴀꜱᴇᴅ ᴏʀ ᴀᴅᴅᴇD ʏᴇᴛ."""
                 return await s.edit(not_found_text)
    else:
        settings = await get_settings(msg.message.chat.id)
        message = msg.message.reply_to_message 
        search, files, offset, total_results = spoll
    req = message.from_user.id if message and message.from_user else 0
    key = f"{message.chat.id}-{message.id}"; temp.FILES[key] = files; BUTTONS[key] = search
    files_link = ""; btn = []

    if settings.get('links', False): 
        for i, file in enumerate(files):
             files_link += f"<b>\n\n{i+1}. <a href=https://t.me/{temp.U_NAME}?start=filep_{key}_{i}>[{get_size(file['file_size'])}] {file['file_name']}</a></b>"
    else: 
        btn = [[InlineKeyboardButton(f"[{get_size(file['file_size'])}] {file['file_name'][:60]}", callback_data=f'fileidx#{key}#{i}')] for i, file in enumerate(files)]

    btn.insert(0, [InlineKeyboardButton("• ᴜᴘᴅᴀᴛᴇꜱ •", url=UPDATES_LINK)])
    btn.insert(1, [ InlineKeyboardButton("⫸ ʟᴀɴɢᴜᴀɢᴇ", callback_data=f"languages#{key}#{req}#0"),
                   InlineKeyboardButton("⫸ ǫᴜᴀʟɪᴛʏ", callback_data=f"quality#{key}#{req}#0") ])

    if offset != "": 
        pg = 1; total_pg = math.ceil(total_results / MAX_BTN); pg_lbl = f"ᴘɢ {pg}/{total_pg}"
        pg_row = [ InlineKeyboardButton(pg_lbl, callback_data="buttons"), InlineKeyboardButton("ɴᴇхᴛ »", callback_data=f"next_{req}_{key}_{offset}") ]; btn.append(pg_row)

    imdb = await get_poster(search, file=(files[0])['file_name']) if settings.get("imdb", True) else None
    TEMPLATE = settings.get('template', script.IMDB_TEMPLATE) 

    if imdb:
        try:
            cap = TEMPLATE.format( query=search, **imdb, message=message )
        except Exception as e:
            logger.error(f"IMDb template formatting error: {e}")
            cap = f"🎬 {imdb.get('title', search)}" 
    else:
        cap = f"<b>👋 {message.from_user.mention},\n\n🔎 ʀᴇꜱᴜʟᴛꜱ ꜰᴏʀ: {search}</b>"
    CAP[key] = cap 

    del_msg = f"\n\n<b>⚠️ ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ɪɴ {get_readable_time(DELETE_TIME)}.</b>" if settings.get("auto_delete", False) else ''
    final_caption = cap[:1024] + files_link + del_msg 
    reply_markup = InlineKeyboardMarkup(btn); k = None

    try:
        if imdb and imdb.get('poster'):
             try:
                 await s.delete(); 
                 k = await message.reply_photo(photo=imdb['poster'], caption=final_caption, reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML, quote=True)
             except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty) as e:
                 logger.warning(f"IMDb poster fail {search}: {e}")
                 k = await message.reply_text(final_caption, reply_markup=reply_markup, disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML, quote=True)
             except FloodWait as e:
                 logger.warning(f"FloodWait sending photo: {e.value}"); await asyncio.sleep(e.value);
                 k = await message.reply_text(final_caption, reply_markup=reply_markup, disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML, quote=True) 
             except Exception as e:
                 logger.error(f"Error sending photo result: {e}")
                 k = await message.reply_text(final_caption, reply_markup=reply_markup, disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML, quote=True) 
        else: 
            await s.delete();
            k = await message.reply_text(final_caption, reply_markup=reply_markup, disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML, quote=True)

        if settings.get("auto_delete", False) and k:
            await asyncio.sleep(DELETE_TIME);
            try: await k.delete()
            except: pass
            try: await message.delete() 
            except: pass
    except FloodWait as e: logger.warning(f"FloodWait in auto_filter main reply: {e.value}"); await asyncio.sleep(e.value)
    except Exception as e: logger.error(f"Final auto_filter error: {e}", exc_info=True); await s.edit("❌ ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ.")


async def advantage_spell_chok(message, s):
    search = message.text
    safe_search = urllib.parse.quote_plus(search)
    google_url = f"https://www.google.com/search?q={safe_search}"
    btn = [[ InlineKeyboardButton("❓ ʜᴏᴡ ᴛᴏ", callback_data='instructions'), InlineKeyboardButton("🔎 ɢᴏᴏɢʟᴇ", url=google_url) ]]
    try: movies = await get_poster(search, bulk=True)
    except Exception as e: logger.error(f"Spell check poster error: {e}"); movies = None

    no_results_text = f"""👋 ʜᴇʟʟᴏ {message.from_user.mention},

ɪ ᴄᴏᴜʟᴅɴ'ᴛ ꜰɪɴᴅ `<b>{search}</b>` ɪɴ ᴍʏ ᴅᴀᴛᴀʙᴀꜱᴇ! 

♢ ᴅᴏᴜʙʟᴇ-ᴄʜᴇᴄᴋ ᴛʜᴇ ꜱᴘᴇʟʟɪɴɢ.
♢ ᴛʀʏ ᴜꜱɪɴɢ ᴍᴏʀᴇ ꜱᴘᴇᴄɪꜰɪᴄ ᴋᴇʏᴡᴏʀᴅꜱ.
♢ ᴛʜᴇ ꜰɪʟᴇ ᴍɪɢʜᴛ ɴᴏᴛ ʙᴇ ʀᴇʟᴇᴀꜱᴇᴅ ᴏʀ ᴀᴅᴅᴇᴅ ʏᴇᴛ."""

    if not movies:
        n = await s.edit(no_results_text, reply_markup=InlineKeyboardMarkup(btn))
        try: await message._client.send_message(LOG_CHANNEL, f"#ɴᴏ_ʀᴇꜱᴜʟᴛ\n\n♢ ʀᴇǫ: {message.from_user.mention}\n♢ ǫᴜᴇʀʏ: `{search}`")
        except: pass
        return

    seen = set(); unique = []; [unique.append(m) for m in movies if m.movieID not in seen and not seen.add(m.movieID)]; unique = unique[:7] 
    user = message.from_user.id if message.from_user else 0
    buttons = [[InlineKeyboardButton(f"{m.get('title','?')[:50]} ({m.get('year','?')})", callback_data=f"spolling#{m.movieID}#{user}")] for m in unique]
    buttons.append([InlineKeyboardButton("🚫 ᴄʟᴏꜱᴇ", callback_data="close_data")])

    suggestion_text = f"👋 {message.from_user.mention},\n\nɪ ᴄᴏᴜʟᴅɴ'ᴛ ꜰɪɴᴅ `<b>{search}</b>`.\nᴅɪᴅ ʏᴏᴜ ᴍᴇᴀɴ...? "
    await s.edit(suggestion_text, reply_markup=InlineKeyboardMarkup(buttons))
