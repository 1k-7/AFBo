from hydrogram import Client, filters
from utils import is_check_admin
from hydrogram.types import ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton


@Client.on_message(filters.command('manage') & filters.group)
async def members_management(client, message):
    if not await is_check_admin(client, message.chat.id, message.from_user.id):
        return await message.reply_text('ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀɴ ᴀᴅᴍɪɴ ɪɴ ᴛʜɪꜱ ɢʀᴏᴜᴘ.') # Font applied
    # Font applied to button text
    btn = [[
        InlineKeyboardButton('ᴜɴᴍᴜᴛᴇ ᴀʟʟ', callback_data='unmute_all_members'),
        InlineKeyboardButton('ᴜɴʙᴀɴ ᴀʟʟ', callback_data='unban_all_members')
    ],[
        InlineKeyboardButton('ᴋɪᴄᴋ ᴍᴜᴛᴇᴅ ᴜꜱᴇʀꜱ', callback_data='kick_muted_members'),
        InlineKeyboardButton('ᴋɪᴄᴋ ᴅᴇʟᴇᴛᴇᴅ ᴀᴄᴄᴏᴜɴᴛꜱ', callback_data='kick_deleted_accounts_members')
    ]]
    await message.reply_text("ꜱᴇʟᴇᴄᴛ ᴀɴ ᴏᴘᴛɪᴏɴ ᴛᴏ ᴍᴀɴᴀɢᴇ ᴍᴇᴍʙᴇʀꜱ:", reply_markup=InlineKeyboardMarkup(btn)) # Font applied


@Client.on_message(filters.command('ban') & filters.group)
async def ban_chat_user(client, message):
    if not await is_check_admin(client, message.chat.id, message.from_user.id):
        return await message.reply_text('ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀɴ ᴀᴅᴍɪɴ ɪɴ ᴛʜɪꜱ ɢʀᴏᴜᴘ.') # Font applied
    if message.reply_to_message and message.reply_to_message.from_user:
        user_id = message.reply_to_message.from_user.username or message.reply_to_message.from_user.id
    else:
        try:
            user_id = message.text.split(" ", 1)[1]
        except IndexError:
            return await message.reply_text("ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴜꜱᴇʀ'ꜱ ᴍᴇꜱꜱᴀɢᴇ ᴏʀ ᴘʀᴏᴠɪᴅᴇ ᴜꜱᴇʀ ɪᴅ/ᴜꜱᴇʀɴᴀᴍᴇ.") # Font applied
    try:
        user_id = int(user_id)
    except ValueError:
        pass # Allow usernames
    try:
        user = (await client.get_chat_member(message.chat.id, user_id)).user
    except Exception as e:
        return await message.reply_text(f"ᴄᴀɴ'ᴛ ꜰɪɴᴅ ᴛʜᴀᴛ ᴜꜱᴇʀ ɪɴ ᴛʜɪꜱ ɢʀᴏᴜᴘ.\nᴇʀʀᴏʀ: {e}") # Font applied
    try:
        await client.ban_chat_member(message.chat.id, user.id) # Use user.id for banning
    except Exception as e:
        return await message.reply_text(f"ɪ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪꜱꜱɪᴏɴ ᴛᴏ ʙᴀɴ ᴜꜱᴇʀꜱ.\nᴇʀʀᴏʀ: {e}") # Font applied
    await message.reply_text(f'✔️ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ʙᴀɴɴᴇᴅ {user.mention} ꜰʀᴏᴍ {message.chat.title}!') # Font applied


@Client.on_message(filters.command('mute') & filters.group)
async def mute_chat_user(client, message):
    if not await is_check_admin(client, message.chat.id, message.from_user.id):
        return await message.reply_text('ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀɴ ᴀᴅᴍɪɴ ɪɴ ᴛʜɪꜱ ɢʀᴏᴜᴘ.') # Font applied
    if message.reply_to_message and message.reply_to_message.from_user:
        user_id = message.reply_to_message.from_user.username or message.reply_to_message.from_user.id
    else:
        try:
            user_id = message.text.split(" ", 1)[1]
        except IndexError:
            return await message.reply_text("ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴜꜱᴇʀ'ꜱ ᴍᴇꜱꜱᴀɢᴇ ᴏʀ ᴘʀᴏᴠɪᴅᴇ ᴜꜱᴇʀ ɪᴅ/ᴜꜱᴇʀɴᴀᴍᴇ.") # Font applied
    try:
        user_id = int(user_id)
    except ValueError:
        pass # Allow usernames
    try:
        user = (await client.get_chat_member(message.chat.id, user_id)).user
    except Exception as e:
        return await message.reply_text(f"ᴄᴀɴ'ᴛ ꜰɪɴᴅ ᴛʜᴀᴛ ᴜꜱᴇʀ ɪɴ ᴛʜɪꜱ ɢʀᴏᴜᴘ.\nᴇʀʀᴏʀ: {e}") # Font applied
    try:
        await client.restrict_chat_member(message.chat.id, user.id, ChatPermissions()) # Use user.id
    except Exception as e:
        return await message.reply_text(f"ɪ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪꜱꜱɪᴏɴ ᴛᴏ ᴍᴜᴛᴇ ᴜꜱᴇʀꜱ.\nᴇʀʀᴏʀ: {e}") # Font applied
    await message.reply_text(f'✔️ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴍᴜᴛᴇᴅ {user.mention} ɪɴ {message.chat.title}.') # Font applied


@Client.on_message(filters.command(["unban", "unmute"]) & filters.group)
async def unban_chat_user(client, message):
    if not await is_check_admin(client, message.chat.id, message.from_user.id):
        return await message.reply_text('ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀɴ ᴀᴅᴍɪɴ ɪɴ ᴛʜɪꜱ ɢʀᴏᴜᴘ.') # Font applied
    if message.reply_to_message and message.reply_to_message.from_user:
        user_id = message.reply_to_message.from_user.username or message.reply_to_message.from_user.id
    else:
        try:
            user_id = message.text.split(" ", 1)[1]
        except IndexError:
            return await message.reply_text("ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴜꜱᴇʀ'ꜱ ᴍᴇꜱꜱᴀɢᴇ ᴏʀ ᴘʀᴏᴠɪᴅᴇ ᴜꜱᴇʀ ɪᴅ/ᴜꜱᴇʀɴᴀᴍᴇ.") # Font applied
    try:
        user_id = int(user_id)
    except ValueError:
        pass # Allow usernames
    # Check if user exists (get_users works better for this than get_chat_member if they might be banned)
    try:
        user = await client.get_users(user_id)
    except Exception as e:
         return await message.reply_text(f"ᴄᴏᴜʟᴅ ɴᴏᴛ ꜰɪɴᴅ ᴜꜱᴇʀ.\nᴇʀʀᴏʀ: {e}") # Font applied
    try:
        await client.unban_chat_member(message.chat.id, user.id) # Use user.id
    except Exception as e:
        return await message.reply_text(f"ɪ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪꜱꜱɪᴏɴ ᴛᴏ {message.command[0]} ᴜꜱᴇʀꜱ, ᴏʀ ᴛʜᴇ ᴜꜱᴇʀ ɪꜱ ɴᴏᴛ ʀᴇꜱᴛʀɪᴄᴛᴇᴅ.\nᴇʀʀᴏʀ: {e}") # Font applied
    await message.reply_text(f'✔️ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ {message.command[0].upper()}ED {user.mention} ɪɴ {message.chat.title}.') # Font applied