import random
import os
import sys
from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ChatJoinRequest
from hydrogram.errors.exceptions.bad_request_400 import MessageTooLong
from info import ADMINS, LOG_CHANNEL, PICS, SUPPORT_LINK, UPDATES_LINK
from database.users_chats_db import db
from utils import temp, get_settings
from Script import script # Assuming script texts are modified


@Client.on_chat_member_updated()
async def welcome(bot, message):
    if message.chat.type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        return

    # Bot added to group
    if message.new_chat_member and message.new_chat_member.user.id == temp.ME:
        buttons = [[
            InlineKeyboardButton('ᴜᴘᴅᴀᴛᴇꜱ', url=UPDATES_LINK), # Font applied
            InlineKeyboardButton('ꜱᴜᴘᴘᴏʀᴛ', url=SUPPORT_LINK) # Font applied
        ]]
        reply_markup=InlineKeyboardMarkup(buttons)
        user = message.from_user.mention if message.from_user else "Dear"
        # Font applied
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=random.choice(PICS),
            caption=f" ʜᴇʟʟᴏ {user},\n\nᴛʜᴀɴᴋ ʏᴏᴜ ꜰᴏʀ ᴀᴅᴅɪɴɢ ᴍᴇ ᴛᴏ ᴛʜᴇ <b>'{message.chat.title}'</b> ɢʀᴏᴜᴘ! ᴅᴏɴ'ᴛ ꜰᴏʀɢᴇᴛ ᴛᴏ ᴍᴀᴋᴇ ᴍᴇ ᴀᴅᴍɪɴ.\nɪꜰ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴋɴᴏᴡ ᴍᴏʀᴇ, ᴘʟᴇᴀꜱᴇ ᴀꜱᴋ @ActualHomie ",
            reply_markup=reply_markup
        )
        # Add chat to DB if not already present
        if not await db.get_chat(message.chat.id):
            total = await bot.get_chat_members_count(message.chat.id)
            username = f'@{message.chat.username}' if message.chat.username else 'Private'
            # Log new group (assuming script.NEW_GROUP_TXT uses the font)
            await bot.send_message(LOG_CHANNEL, script.NEW_GROUP_TXT.format(message.chat.title, message.chat.id, username, total))
            await db.add_chat(message.chat.id, message.chat.title)
        return

    # New user joined (and welcome message enabled)
    if message.new_chat_member and not message.old_chat_member:
        settings = await get_settings(message.chat.id)
        if settings["welcome"]:
            WELCOME = settings.get('welcome_text', script.WELCOME_TEXT) # Get group-specific or default text
            try:
                # Format welcome message (assuming WELCOME template uses the font)
                welcome_msg = WELCOME.format(
                    mention=message.new_chat_member.user.mention,
                    title=message.chat.title
                )
                await bot.send_message(chat_id=message.chat.id, text=welcome_msg)
            except KeyError as e:
                logger.error(f"Welcome message format error in chat {message.chat.id}: Missing key {e}")
                # Fallback to a simpler message
                await bot.send_message(chat_id=message.chat.id, text=f" ᴡᴇʟᴄᴏᴍᴇ, {message.new_chat_member.user.mention}!")


@Client.on_message(filters.command('restart') & filters.user(ADMINS))
async def restart_bot(bot, message):
    msg = await message.reply("ʀᴇꜱᴛᴀʀᴛɪɴɢ...") # Font applied
    with open('restart.txt', 'w+') as file:
        file.write(f"{msg.chat.id}\n{msg.id}")
    os.execl(sys.executable, sys.executable, "bot.py")

@Client.on_message(filters.command('leave') & filters.user(ADMINS))
async def leave_a_chat(bot, message):
    if len(message.command) == 1:
        return await message.reply('ɢɪᴠᴇ ᴍᴇ ᴀ ᴄʜᴀᴛ ɪᴅ ᴛᴏ ʟᴇᴀᴠᴇ.') # Font applied
    r = message.text.split(None)
    if len(r) > 2:
        reason = message.text.split(None, 2)[2]
        chat = message.text.split(None, 2)[1]
    else:
        chat = message.command[1]
        reason = "ɴᴏ ʀᴇᴀꜱᴏɴ ᴘʀᴏᴠɪᴅᴇᴅ." # Font applied
    try:
        chat_id = int(chat)
    except ValueError:
        chat_id = chat # Assume username
    try:
        buttons = [[
            InlineKeyboardButton('ꜱᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ', url=SUPPORT_LINK) # Font applied
        ]]
        reply_markup=InlineKeyboardMarkup(buttons)
        await bot.send_message(
            chat_id=chat_id,
            # Font applied
            text=f'ʜᴇʟʟᴏ ꜰʀɪᴇɴᴅꜱ,\nᴍʏ ᴏᴡɴᴇʀ ʜᴀꜱ ᴛᴏʟᴅ ᴍᴇ ᴛᴏ ʟᴇᴀᴠᴇ ᴛʜɪꜱ ɢʀᴏᴜᴘ, ꜱᴏ ɪ ᴍᴜꜱᴛ ɢᴏ! ɪꜰ ʏᴏᴜ ɴᴇᴇᴅ ᴛᴏ ᴀᴅᴅ ᴍᴇ ᴀɢᴀɪɴ, ᴘʟᴇᴀꜱᴇ ᴄᴏɴᴛᴀᴄᴛ ᴍʏ ꜱᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ.\nʀᴇᴀꜱᴏɴ - <code>{reason}</code>',
            reply_markup=reply_markup,
        )
        await bot.leave_chat(chat_id)
        await message.reply(f"✔️ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ʟᴇꜰᴛ ɢʀᴏᴜᴘ: `{chat_id}`") # Font applied
    except Exception as e:
        await message.reply(f'ᴇʀʀᴏʀ ʟᴇᴀᴠɪɴɢ ᴄʜᴀᴛ `{chat_id}`: {e}') # Font applied

@Client.on_message(filters.command('ban_grp') & filters.user(ADMINS))
async def disable_chat(bot, message):
    if len(message.command) == 1:
        return await message.reply('ɢɪᴠᴇ ᴍᴇ ᴀ ᴄʜᴀᴛ ɪᴅ ᴛᴏ ʙᴀɴ.') # Font applied
    r = message.text.split(None)
    if len(r) > 2:
        reason = message.text.split(None, 2)[2]
        chat = message.text.split(None, 2)[1]
    else:
        chat = message.command[1]
        reason = "ɴᴏ ʀᴇᴀꜱᴏɴ ᴘʀᴏᴠɪᴅᴇᴅ." # Font applied
    try:
        chat_id = int(chat)
    except ValueError:
        return await message.reply('ɢɪᴠᴇ ᴍᴇ ᴀ ᴠᴀʟɪᴅ ᴄʜᴀᴛ ɪᴅ (ɴᴜᴍʙᴇʀ).') # Font applied
    cha_t = await db.get_chat(chat_id) # Use await here
    if not cha_t:
        return await message.reply("ᴄʜᴀᴛ ɴᴏᴛ ꜰᴏᴜɴᴅ ɪɴ ᴅᴀᴛᴀʙᴀꜱᴇ.") # Font applied
    if cha_t.get('is_disabled', False): # Use .get() for safety
        return await message.reply(f"ᴛʜɪꜱ ᴄʜᴀᴛ ɪꜱ ᴀʟʀᴇᴀᴅʏ ᴅɪꜱᴀʙʟᴇᴅ.\nʀᴇᴀꜱᴏɴ - <code>{cha_t.get('reason','N/A')}</code>") # Font applied
    await db.disable_chat(chat_id, reason) # Use await
    if chat_id not in temp.BANNED_CHATS: # Add to runtime list
        temp.BANNED_CHATS.append(chat_id)
    await message.reply(f'ᴄʜᴀᴛ `{chat_id}` ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴅɪꜱᴀʙʟᴇᴅ.') # Font applied
    try:
        buttons = [[
            InlineKeyboardButton('ꜱᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ', url=SUPPORT_LINK) # Font applied
        ]]
        reply_markup=InlineKeyboardMarkup(buttons)
        # Font applied
        await bot.send_message(
            chat_id=chat_id,
            text=f'ʜᴇʟʟᴏ ꜰʀɪᴇɴᴅꜱ,\nᴛʜɪꜱ ɢʀᴏᴜᴘ ʜᴀꜱ ʙᴇᴇɴ ʙᴀɴɴᴇᴅ ꜰʀᴏᴍ ᴜꜱɪɴɢ ᴍᴇ ʙʏ ᴍʏ ᴏᴡɴᴇʀ. ɪ ʜᴀᴠᴇ ᴛᴏ ʟᴇᴀᴠᴇ ɴᴏᴡ. ᴄᴏɴᴛᴀᴄᴛ ꜱᴜᴘᴘᴏʀᴛ ɪꜰ ʏᴏᴜ ᴛʜɪɴᴋ ᴛʜɪꜱ ɪꜱ ᴀ ᴍɪꜱᴛᴀᴋᴇ.\nʀᴇᴀꜱᴏɴ - <code>{reason}</code>',
            reply_markup=reply_markup)
        await bot.leave_chat(chat_id)
    except Exception as e:
        await message.reply(f"ɴᴏᴛᴇ: ᴄᴏᴜʟᴅ ɴᴏᴛ ꜱᴇɴᴅ ᴍᴇꜱꜱᴀɢᴇ ᴛᴏ ᴏʀ ʟᴇᴀᴠᴇ ᴛʜᴇ ʙᴀɴɴᴇᴅ ɢʀᴏᴜᴘ `{chat_id}`.\nᴇʀʀᴏʀ - {e}") # Font applied

@Client.on_message(filters.command('unban_grp') & filters.user(ADMINS))
async def re_enable_chat(bot, message):
    if len(message.command) == 1:
        return await message.reply('ɢɪᴠᴇ ᴍᴇ ᴀ ᴄʜᴀᴛ ɪᴅ ᴛᴏ ᴜɴʙᴀɴ.') # Font applied
    chat = message.command[1]
    try:
        chat_id = int(chat)
    except ValueError:
        return await message.reply('ɢɪᴠᴇ ᴍᴇ ᴀ ᴠᴀʟɪᴅ ᴄʜᴀᴛ ɪᴅ (ɴᴜᴍʙᴇʀ).') # Font applied
    sts = await db.get_chat(chat_id) # Use await
    if not sts:
        return await message.reply("ᴄʜᴀᴛ ɴᴏᴛ ꜰᴏᴜɴᴅ ɪɴ ᴅᴀᴛᴀʙᴀꜱᴇ.") # Font applied
    if not sts.get('is_disabled', False): # Use .get()
        return await message.reply('ᴛʜɪꜱ ᴄʜᴀᴛ ɪꜱ ɴᴏᴛ ᴄᴜʀʀᴇɴᴛʟʏ ᴅɪꜱᴀʙʟᴇᴅ.') # Font applied
    await db.re_enable_chat(chat_id) # Use await
    if chat_id in temp.BANNED_CHATS: # Remove from runtime list
        temp.BANNED_CHATS.remove(chat_id)
    await message.reply(f"ᴄʜᴀᴛ `{chat_id}` ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ʀᴇ-ᴇɴᴀʙʟᴇᴅ.") # Font applied

@Client.on_message(filters.command('invite_link') & filters.user(ADMINS))
async def gen_invite_link(bot, message):
    if len(message.command) == 1:
        return await message.reply('ɢɪᴠᴇ ᴍᴇ ᴀ ᴄʜᴀᴛ ɪᴅ ᴛᴏ ɢᴇɴᴇʀᴀᴛᴇ ᴀɴ ɪɴᴠɪᴛᴇ ʟɪɴᴋ.') # Font applied
    chat = message.command[1]
    try:
        chat_id = int(chat)
    except ValueError:
        return await message.reply('ɢɪᴠᴇ ᴍᴇ ᴀ ᴠᴀʟɪᴅ ᴄʜᴀᴛ ɪᴅ (ɴᴜᴍʙᴇʀ).') # Font applied
    try:
        link = await bot.create_chat_invite_link(chat_id)
    except Exception as e:
        return await message.reply(f'ᴇʀʀᴏʀ ɢᴇɴᴇʀᴀᴛɪɴɢ ʟɪɴᴋ ꜰᴏʀ `{chat_id}`: {e}') # Font applied
    await message.reply(f'ʜᴇʀᴇ ɪꜱ ᴛʜᴇ ɪɴᴠɪᴛᴇ ʟɪɴᴋ: {link.invite_link}') # Font applied

@Client.on_message(filters.command('ban_user') & filters.user(ADMINS))
async def ban_a_user(bot, message):
    if len(message.command) == 1:
        return await message.reply('ɢɪᴠᴇ ᴍᴇ ᴀ ᴜꜱᴇʀ ɪᴅ ᴏʀ ᴜꜱᴇʀɴᴀᴍᴇ ᴛᴏ ʙᴀɴ.') # Font applied
    r = message.text.split(None)
    if len(r) > 2:
        reason = message.text.split(None, 2)[2]
        user_arg = message.text.split(None, 2)[1]
    else:
        user_arg = message.command[1]
        reason = "ɴᴏ ʀᴇᴀꜱᴏɴ ᴘʀᴏᴠɪᴅᴇᴅ." # Font applied
    try:
        if user_arg.startswith('@'):
            user = await bot.get_users(user_arg)
        else:
            user = await bot.get_users(int(user_arg))
    except Exception as e:
        return await message.reply(f'ᴇʀʀᴏʀ ꜰɪɴᴅɪɴɢ ᴜꜱᴇʀ: {e}') # Font applied

    if user.id in ADMINS:
        return await message.reply('ʏᴏᴜ ᴄᴀɴɴᴏᴛ ʙᴀɴ ᴀɴ ᴀᴅᴍɪɴ!') # Font applied
    jar = await db.get_ban_status(user.id) # Use await
    if jar['is_banned']:
        return await message.reply(f"{user.mention} ɪꜱ ᴀʟʀᴇᴀᴅʏ ʙᴀɴɴᴇᴅ.\nʀᴇᴀꜱᴏɴ - <code>{jar['ban_reason']}</code>") # Font applied
    await db.ban_user(user.id, reason) # Use await
    if user.id not in temp.BANNED_USERS:
        temp.BANNED_USERS.append(user.id)
    await message.reply(f"✔️ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ʙᴀɴɴᴇᴅ {user.mention}.") # Font applied

@Client.on_message(filters.command('unban_user') & filters.user(ADMINS))
async def unban_a_user(bot, message):
    if len(message.command) == 1:
        return await message.reply('ɢɪᴠᴇ ᴍᴇ ᴀ ᴜꜱᴇʀ ɪᴅ ᴏʀ ᴜꜱᴇʀɴᴀᴍᴇ ᴛᴏ ᴜɴʙᴀɴ.') # Font applied
    r = message.text.split(None)
    user_arg = message.command[1] # Reason not needed for unban
    try:
        if user_arg.startswith('@'):
            user = await bot.get_users(user_arg)
        else:
            user = await bot.get_users(int(user_arg))
    except Exception as e:
        return await message.reply(f'ᴇʀʀᴏʀ ꜰɪɴᴅɪɴɢ ᴜꜱᴇʀ: {e}') # Font applied

    jar = await db.get_ban_status(user.id) # Use await
    if not jar['is_banned']:
        return await message.reply(f"{user.mention} ɪꜱ ɴᴏᴛ ᴄᴜʀʀᴇɴᴛʟʏ ʙᴀɴɴED.") # Font applied
    await db.remove_ban(user.id) # Use await
    if user.id in temp.BANNED_USERS:
        temp.BANNED_USERS.remove(user.id)
    await message.reply(f"✔️ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴜɴʙᴀɴɴᴇᴅ {user.mention}.") # Font applied

@Client.on_message(filters.command('users') & filters.user(ADMINS))
async def list_users(bot, message):
    raju = await message.reply('ɢᴇᴛᴛɪɴɢ ʟɪꜱᴛ ᴏꜰ ᴜꜱᴇʀꜱ...') # Font applied
    users = db.get_all_users() # Dont Use await
    out = "ᴜꜱᴇʀꜱ ꜱᴀᴠᴇᴅ ɪɴ ᴅᴀᴛᴀʙᴀꜱᴇ ᴀʀᴇ:\n\n" # Font applied
    count = 0
    for user in users:
        count += 1
        out += f"**ɴᴀᴍᴇ:** {user['name']}\n**ɪᴅ:** `{user['id']}`"
        if user.get('ban_status', {}).get('is_banned', False): # Safer access
            out += ' (ʙᴀɴɴᴇᴅ ᴜꜱᴇʀ)' # Font applied
        if user.get('verify_status', {}).get('is_verified', False): # Safer access
             out += ' (ᴠᴇʀɪꜰɪᴇᴅ ᴜꜱᴇʀ)' # Font applied
        out += '\n\n'
        # Send in chunks if too long
        if len(out) > 3800:
             try:
                 await message.reply_text(out)
                 out = "" # Reset for next chunk
             except MessageTooLong: # Should not happen often with 3800 limit but safety
                  with open('users_chunk.txt', 'w+') as outfile: outfile.write(out)
                  await message.reply_document('users_chunk.txt', caption=f"ᴜꜱᴇʀꜱ ʟɪꜱᴛ (ᴘᴀʀᴛ)")
                  os.remove('users_chunk.txt')
                  out = ""

    # Send the remaining part or the full list if short
    if out:
        try:
            await raju.edit_text(out + f"\nᴛᴏᴛᴀʟ ᴜꜱᴇʀꜱ: {count}") # Edit original message
        except MessageTooLong:
            with open('users.txt', 'w+') as outfile: outfile.write(out + f"\nᴛᴏᴛᴀʟ ᴜꜱᴇʀꜱ: {count}")
            await message.reply_document('users.txt', caption="ʟɪꜱᴛ ᴏꜰ ᴀʟʟ ᴜꜱᴇʀꜱ") # Font applied
            await raju.delete()
            os.remove('users.txt')
        except Exception as e: # Handle potential edit errors
             await raju.edit_text(f"ᴇʀʀᴏʀ ᴅɪꜱᴘʟᴀʏɪɴɢ ᴜꜱᴇʀꜱ: {e}")
    elif count == 0:
         await raju.edit_text("ɴᴏ ᴜꜱᴇʀꜱ ꜰᴏᴜɴᴅ ɪɴ ᴛʜᴇ ᴅᴀᴛᴀʙᴀꜱᴇ.")
    else: # If message was split, delete the "Getting list..." message
        try: await raju.delete()
        except: pass


@Client.on_message(filters.command('chats') & filters.user(ADMINS))
async def list_chats(bot, message):
    raju = await message.reply('ɢᴇᴛᴛɪɴɢ ʟɪꜱᴛ ᴏꜰ ᴄʜᴀᴛꜱ...') # Font applied
    chats = db.get_all_chats() # No Use await
    out = "ᴄʜᴀᴛꜱ ꜱᴀᴠᴇᴅ ɪɴ ᴅᴀᴛᴀʙᴀꜱᴇ ᴀʀᴇ:\n\n" # Font applied
    count = 0
    for chat in chats:
        count += 1
        out += f"**ᴛɪᴛʟᴇ:** {chat['title']}\n**ɪᴅ:** `{chat['id']}`"
        if chat.get('chat_status', {}).get('is_disabled', False): # Safer access
            out += ' (ᴅɪꜱᴀʙʟᴇᴅ ᴄʜᴀᴛ)' # Font applied
        out += '\n\n'
        # Send in chunks if too long
        if len(out) > 3800:
             try:
                 await message.reply_text(out)
                 out = "" # Reset for next chunk
             except MessageTooLong:
                  with open('chats_chunk.txt', 'w+') as outfile: outfile.write(out)
                  await message.reply_document('chats_chunk.txt', caption=f"ᴄʜᴀᴛꜱ ʟɪꜱᴛ (ᴘᴀʀᴛ)")
                  os.remove('chats_chunk.txt')
                  out = ""

    # Send the remaining part or the full list if short
    if out:
        try:
            await raju.edit_text(out + f"\nᴛᴏᴛᴀʟ ᴄʜᴀᴛꜱ: {count}") # Edit original message
        except MessageTooLong:
            with open('chats.txt', 'w+') as outfile: outfile.write(out + f"\nᴛᴏᴛᴀʟ ᴄʜᴀᴛꜱ: {count}")
            await message.reply_document('chats.txt', caption="ʟɪꜱᴛ ᴏꜰ ᴀʟʟ ᴄʜᴀᴛꜱ") # Font applied
            await raju.delete()
            os.remove('chats.txt')
        except Exception as e: # Handle potential edit errors
            await raju.edit_text(f"ᴇʀʀᴏʀ ᴅɪꜱᴘʟᴀʏɪɴɢ ᴄʜᴀᴛꜱ: {e}")
    elif count == 0:
        await raju.edit_text("ɴᴏ ᴄʜᴀᴛꜱ ꜰᴏᴜɴᴅ ɪɴ ᴛʜᴇ ᴅᴀᴛᴀʙᴀꜱᴇ.")
    else: # If message was split, delete the "Getting list..." message
        try: await raju.delete()
        except: pass


@Client.on_chat_join_request()
async def join_reqs(client, message: ChatJoinRequest):
    stg = await db.get_bot_sttgs() # Use await
    req_channel = stg.get('REQUEST_FORCE_SUB_CHANNELS')
    if req_channel and message.chat.id == int(req_channel):
        user_id = message.from_user.id
        if not await db.find_join_req(user_id): # Use await
            await db.add_join_req(user_id) # Use await


@Client.on_message(filters.command("delreq") & filters.private & filters.user(ADMINS))
async def del_requests(client, message):
    await db.del_join_req() # Use await
    await message.reply('ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ ᴀʟʟ ᴘᴇɴᴅɪɴɢ ᴊᴏɪɴ ʀᴇǫᴜᴇꜱᴛꜱ ꜰʀᴏᴍ ᴅᴀᴛᴀʙᴀꜱᴇ.') # Font applied

