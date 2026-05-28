import os
import json
import asyncio
import aiosqlite
from time import time as time_now
from time import monotonic
from Script import script 
from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from database.ia_filterdb import get_total_files_count, get_file_details
from database.users_chats_db import db
from info import (INDEX_CHANNELS, ADMINS, DATABASE_FILE,
                  SUPPORT_LINK, UPDATES_LINK, LOG_CHANNEL,
                  PM_FILE_DELETE_TIME, PROTECT_CONTENT, 
                  AUTO_DELETE, LINK_MODE)
from utils import (get_settings, get_size, is_subscribed, is_check_admin,
                   temp, get_readable_time, get_wish)
from hydrogram.errors import FloodWait
import logging

logger = logging.getLogger(__name__)

@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        chat_exists = await db.is_user_exist(message.chat.id)
        if not chat_exists:
            try:
                total = await client.get_chat_members_count(message.chat.id)
                username = f'@{message.chat.username}' if message.chat.username else 'Private'
                await client.send_message(LOG_CHANNEL, script.NEW_GROUP_TXT.format(message.chat.title, message.chat.id, username, total))
                await db.add_chat(message.chat.id, message.chat.title)
            except Exception as e: pass
        wish = get_wish(); user = message.from_user.mention if message.from_user else "User"
        btn = [[ InlineKeyboardButton('Updates', url=UPDATES_LINK), InlineKeyboardButton('Support', url=SUPPORT_LINK) ]]
        await message.reply(f"<b>Hello {user}, {wish}\nHow can I help you?</b>", reply_markup=InlineKeyboardMarkup(btn)); return

    user_id = message.from_user.id
    user_exists = await db.is_user_exist(user_id)
    if not user_exists:
        try:
            await db.add_user(user_id, message.from_user.first_name)
            await client.send_message(LOG_CHANNEL, script.NEW_USER_TXT.format(message.from_user.mention, user_id))
        except: pass

    if len(message.command) == 1 or message.command[1] == 'start':
        buttons = [[ InlineKeyboardButton("➕ Add to Group", url=f'http://t.me/{temp.U_NAME}?startgroup=start') ], 
                   [ InlineKeyboardButton('🔍 Inline Search', switch_inline_query_current_chat='') ]]
        await message.reply(script.START_TXT.format(message.from_user.mention), reply_markup=InlineKeyboardMarkup(buttons)); return

    mc = message.command[1]
    
    if mc.startswith('settings'):
        try: _, group_id_str = mc.split("_", 1); group_id = int(group_id_str)
        except ValueError: return await message.reply("Invalid settings link.")
        if not await is_check_admin(client, group_id, user_id): return await message.reply("You are not an admin in that group.")
        try:
            btn = await get_grp_stg(group_id)
            chat = await client.get_chat(group_id)
            await message.reply(f"⚙️ Settings for <b>'{chat.title}'</b>:", reply_markup=InlineKeyboardMarkup(btn))
        except: return await message.reply("Error fetching settings.")

    btn_fsub = await is_subscribed(client, message)
    if btn_fsub:
        btn_fsub.append([InlineKeyboardButton("🔁 Try Again", callback_data=f"checksub#{mc}")])
        return await message.reply("👋 Please join the channel(s) below to get files.", reply_markup=InlineKeyboardMarkup(btn_fsub))

    try:
        if mc.startswith('all'):
            _, grp_id, key = mc.split("_", 2); grp_id = int(grp_id)
            files = temp.FILES.get(key)
            if not files: return await message.reply('❌ Link expired or invalid.')
            settings = await get_settings(grp_id)
            sent = []; total_msg = await message.reply(f"<b><i>🗂️ Sending <code>{len(files)}</code> files... Please wait.</i></b>")
            for file in files:
                fid = file['_id']; cap = file.get('caption', '')
                CAPTION = settings.get('caption', script.FILE_CAPTION)
                try: f_cap = CAPTION.format(file_name=file.get('file_name','N/A'), file_size=get_size(file.get('file_size',0)), file_caption=cap)
                except: f_cap = file.get('file_name','N/A')
                
                try:
                    msg = await client.send_cached_media(user_id, fid, caption=f_cap[:1024], protect_content=settings.get('file_secure', PROTECT_CONTENT))
                    sent.append(msg.id); await asyncio.sleep(0.5)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    msg = await client.send_cached_media(user_id, fid, caption=f_cap[:1024], protect_content=settings.get('file_secure', PROTECT_CONTENT))
                    sent.append(msg.id)
            
            pm_del = PM_FILE_DELETE_TIME; time_r = get_readable_time(pm_del)
            info = await message.reply(f"⚠️ Files will be deleted after <b>{time_r}</b>.", quote=True)
            await asyncio.sleep(pm_del)
            try: await client.delete_messages(user_id, sent + [total_msg.id]) 
            except: pass
            try: await info.edit(f"❗️ Files deleted. Click below to get them again.", reply_markup=InlineKeyboardMarkup([[ InlineKeyboardButton('🔄 Get Again', callback_data=f"get_del_send_all_files#{grp_id}#{key}") ]]))
            except: pass

        elif mc.startswith(('file_', 'filep_')):
            if mc.startswith('filep_'):
                _, key, idx_str = mc.split("_", 2)
                grp_id = int(key.split('-')[0])
                idx = int(idx_str)
                files_list = temp.FILES.get(key)
                if not files_list or idx >= len(files_list): return await message.reply('❌ Link expired.')
                file_doc = files_list[idx]
                file_id = file_doc['_id']
            else:
                _, grp_id, file_id = mc.split("_", 2) 
                grp_id = int(grp_id)
                files_ = await get_file_details(file_id)
                if not files_: return await message.reply('❌ No file found.')
                file_doc = files_[0] if isinstance(files_, list) and files_ else None
            
            if not file_doc: return await message.reply('❌ Error retrieving file details.')
            settings = await get_settings(grp_id)

            CAPTION = settings.get('caption', script.FILE_CAPTION); cap_txt = file_doc.get('caption', '')
            try: f_cap = CAPTION.format(file_name=file_doc.get('file_name','N/A'), file_size=get_size(file_doc.get('file_size',0)), file_caption=cap_txt)
            except: f_cap = file_doc.get('file_name','N/A')
            
            try: vp = await client.send_cached_media(user_id, file_id, caption=f_cap[:1024], protect_content=settings.get('file_secure', PROTECT_CONTENT))
            except FloodWait as e:
                await asyncio.sleep(e.value)
                vp = await client.send_cached_media(user_id, file_id, caption=f_cap[:1024], protect_content=settings.get('file_secure', PROTECT_CONTENT))

            pm_del = PM_FILE_DELETE_TIME; time_r = get_readable_time(pm_del)
            msg_timer = await vp.reply(f"⚠️ File will be deleted after <b>{time_r}</b>.", quote=True) if vp else None
            await asyncio.sleep(pm_del)
            try: await msg_timer.delete() 
            except: pass
            if vp:
                try: await vp.delete() 
                except: pass
            try: await message.reply("❗️ File deleted. Click below to get it again.", reply_markup=InlineKeyboardMarkup([[ InlineKeyboardButton('🔄 Get Again', callback_data=f"get_del_file#{grp_id}#{file_id}") ]]))
            except: pass
    except Exception as e:
        logger.error(f"Error processing start cmd: {e}")

# ==========================================
# IMPORT / EXPORT COMMANDS (SQLITE -> JSON)
# ==========================================
@Client.on_message(filters.command('export') & filters.user(ADMINS))
async def export_db_cmd(bot, message):
    msg = await message.reply("⏳ Querying Database... This may take a moment.")
    try:
        async with aiosqlite.connect(DATABASE_FILE) as sql_db:
            sql_db.row_factory = aiosqlite.Row
            async with sql_db.execute('SELECT file_id as _id, file_name, file_size, caption FROM files') as cursor:
                rows = await cursor.fetchall()
                docs = [dict(row) for row in rows]
        
        filepath = "database_export.json"
        with open(filepath, "w") as f:
            json.dump(docs, f, indent=4) 
            
        await message.reply_document(
            document=filepath, 
            caption=f"📦 Database Export Complete.\nTotal Files: {len(docs)}"
        )
        os.remove(filepath)
        await msg.delete()
        
    except Exception as e:
        logger.error(f"Export Error: {e}", exc_info=True)
        await msg.edit(f"❌ Error during export: {e}")


@Client.on_message(filters.command('import') & filters.user(ADMINS))
async def import_db_cmd(bot, message):
    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply("Usage: Reply to a JSON export file with `/import`")
        
    msg = await message.reply("⏳ Downloading JSON file...")
    
    try:
        file_path = await message.reply_to_message.download()
        await msg.edit("⏳ Parsing JSON and importing to database. Please wait...")
        
        with open(file_path, "r") as f:
            docs = json.load(f)
            
        if not isinstance(docs, list):
            raise ValueError("JSON file must contain a list of documents.")
            
        success = 0; duplicate = 0; errors = 0
        
        async with aiosqlite.connect(DATABASE_FILE) as sql_db:
            for doc in docs:
                try:
                    file_id = doc.get('_id') or doc.get('file_id')
                    file_name = doc.get('file_name', '')
                    file_size = doc.get('file_size', 0)
                    caption = doc.get('caption', '')
                    
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
                except Exception as e:
                    errors += 1
            await sql_db.commit()

        os.remove(file_path)
        await msg.edit(
            f"✔️ **Import Complete**\n\n"
            f"Total Processed: {len(docs)}\n"
            f"Successfully Inserted: {success}\n"
            f"Skipped (Duplicates): {duplicate}\n"
            f"Errors: {errors}"
        )
        
    except Exception as e:
        logger.error(f"Import Error: {e}", exc_info=True)
        await msg.edit(f"❌ Error during import: {e}")
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)

# ==========================================
# OTHER BOT COMMANDS
# ==========================================
@Client.on_message(filters.command('index_channels') & filters.user(ADMINS))
async def channels_info_cmd(bot, message):
    ids = INDEX_CHANNELS; text = '**Indexed Channels:**\n\n'
    if not ids: return await message.reply("⚠️ No channels configured for indexing.")
    for id_ in ids:
        try: chat = await bot.get_chat(id_); text += f' • {chat.title} (`{id_}`)\n'
        except: text += f' • Unknown (`{id_}`)\n'
    await message.reply(text)

@Client.on_message(filters.command('stats') & filters.user(ADMINS))
async def stats_cmd(bot, message):
    sts_msg = await message.reply("Gathering bot statistics...")
    total_files = await get_total_files_count()
    users = await db.total_users_count()
    chats = await db.total_chat_count()
    uptime = get_readable_time(time_now() - temp.START_TIME)
    await sts_msg.edit(script.STATUS_TXT.format(users, chats, total_files, uptime))

async def get_grp_stg(group_id):
    settings = await get_settings(group_id)
    btn = [
        [InlineKeyboardButton('File Caption', callback_data=f'caption_setgs#{group_id}')],
        [InlineKeyboardButton(f'Auto Delete {"✔️" if settings.get("auto_delete", AUTO_DELETE) else "❌"}', callback_data=f'bool_setgs#auto_delete#{settings.get("auto_delete", AUTO_DELETE)}#{group_id}')],
        [InlineKeyboardButton(f'Result Page {"🔗 Links" if settings.get("links", LINK_MODE) else "🔘 Buttons"}', callback_data=f'bool_setgs#links#{settings.get("links", LINK_MODE)}#{group_id}')]
    ]
    return btn

@Client.on_message(filters.command('settings'))
async def settings_cmd(client, message):
    group_id = message.chat.id; user_id = message.from_user.id
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        if not await is_check_admin(client, group_id, user_id): return await message.reply('❌ Admins only.')
        btn = [[ InlineKeyboardButton("🔧 Open Here", callback_data='open_group_settings') ], [ InlineKeyboardButton("🔒 Open in PM", callback_data='open_pm_settings') ]]
        await message.reply('Choose where to open settings:', reply_markup=InlineKeyboardMarkup(btn))
    elif message.chat.type == enums.ChatType.PRIVATE:
        cons = await db.get_connections(user_id)
        if not cons: return await message.reply("You haven't connected any groups yet.")
        buttons = []
        for con_id in cons:
            try:
                chat = await client.get_chat(con_id)
                if await is_check_admin(client, con_id, user_id): buttons.append([InlineKeyboardButton(text=chat.title, callback_data=f'back_setgs#{chat.id}')])
                else: await db.del_connect(con_id, user_id)
            except: await db.del_connect(con_id, user_id) 
        if not buttons: return await message.reply("No valid groups connected.")
        await message.reply('Select a group to manage:', reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_message(filters.command('connect'))
async def connect_cmd(client, message):
    user_id = message.from_user.id
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        if not await is_check_admin(client, message.chat.id, user_id): return await message.reply("❌ Admins only.")
        await db.add_connect(message.chat.id, user_id)
        await message.reply('✔️ Connected group to PM.')
    elif message.chat.type == enums.ChatType.PRIVATE:
        if len(message.command) > 1:
            try: grp_id = int(message.command[1])
            except ValueError: return await message.reply("⚠️ Invalid ID.")
            try:
                 if not await is_check_admin(client, grp_id, user_id): return await message.reply('❌ You are not an admin.')
                 chat = await client.get_chat(grp_id)
                 await db.add_connect(grp_id, user_id)
                 await message.reply(f'✔️ Connected: {chat.title}.')
            except: await message.reply("❌ Could not connect.")
        else: await message.reply('Usage: /connect <group_id>')

@Client.on_message(filters.command('delete') & filters.user(ADMINS))
async def delete_cmd(bot, message):
    try: query = message.text.split(" ", 1)[1]
    except IndexError: return await message.reply("Usage: /delete <query>")
    btn = [[ InlineKeyboardButton("⚠️ Delete", callback_data=f"delete_{query}") ], [ InlineKeyboardButton("❌ Cancel", callback_data="close_data") ]]
    await message.reply(f"❓ Delete files matching `{query}`?", reply_markup=InlineKeyboardMarkup(btn))

@Client.on_message(filters.command('ping') & filters.user(ADMINS))
async def ping_cmd(client, message):
    start = monotonic(); msg = await message.reply("👀 Pinging..."); end = monotonic()
    await msg.edit(f'<b>Pong!\n⏱️ {round((end - start) * 1000)} ms</b>')

@Client.on_message(filters.command('set_fsub') & filters.user(ADMINS))
async def set_fsub_cmd(bot, message):
    try: _, ids_text = message.text.split(' ', 1)
    except: return await message.reply('Usage: /set_fsub -100xxx -100xxx')
    valid_ids = []
    for id_str in ids_text.split():
        try: chat_id = int(id_str); valid_ids.append(str(chat_id))
        except: return await message.reply(f'⚠️ Invalid ID: `{id_str}`.')
    await db.update_bot_sttgs('FORCE_SUB_CHANNELS', " ".join(valid_ids))
    await message.reply('✔️ Force subscribe channels updated.')