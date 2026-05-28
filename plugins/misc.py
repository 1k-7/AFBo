from info import ADMINS
from speedtest import Speedtest, ConfigRetrievalError, SpeedtestBestServerFailure
from hydrogram import Client, filters, enums
from hydrogram.errors import UserNotParticipant
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils import get_size
from datetime import datetime
import os


@Client.on_message(filters.command('id'))
async def showid(client, message):
    chat_type = message.chat.type
    replied_to_msg = message.reply_to_message # Use directly

    if replied_to_msg and replied_to_msg.forward_from_chat: # Check specifically for forwarded from channel
        return await message.reply_text(f"ᴛʜᴇ ꜰᴏʀᴡᴀʀᴅᴇᴅ ᴍᴇꜱꜱᴀɢᴇ'ꜱ ᴏʀɪɢɪɴᴀʟ ᴄʜᴀɴɴᴇʟ, {replied_to_msg.forward_from_chat.title}, ʜᴀꜱ ɪᴅ: <code>{replied_to_msg.forward_from_chat.id}</code>.") # Font applied
    elif replied_to_msg and replied_to_msg.from_user: # Check for replied to user
        return await message.reply_text(f"ʀᴇᴘʟɪᴇᴅ ᴛᴏ ᴜꜱᴇʀ ɪᴅ: <code>{replied_to_msg.from_user.id}</code>.") # Font applied
    elif chat_type == enums.ChatType.PRIVATE:
        await message.reply_text(f'ʏᴏᴜʀ ᴜꜱᴇʀ ɪᴅ: <code>{message.from_user.id}</code>') # Font applied
    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        await message.reply_text(f'ᴛʜɪꜱ ɢʀᴏᴜᴘ ɪᴅ: <code>{message.chat.id}</code>') # Font applied
    elif chat_type == enums.ChatType.CHANNEL:
        await message.reply_text(f'ᴛʜɪꜱ ᴄʜᴀɴɴᴇʟ ɪᴅ: <code>{message.chat.id}</code>') # Font applied


@Client.on_message(filters.command('speedtest') & filters.user(ADMINS))
async def speedtest(client, message):
    #from - https://github.com/weebzone/WZML-X/blob/master/bot/modules/speedtest.py
    msg = await message.reply_text("ɪɴɪᴛɪᴀᴛɪɴɢ ꜱᴘᴇᴇᴅᴛᴇꜱᴛ...") # Font applied
    try:
        speed = Speedtest()
        speed.get_best_server()
        speed.download()
        speed.upload()
        speed.results.share()
        result = speed.results.dict()
    except (ConfigRetrievalError, SpeedtestBestServerFailure):
        await msg.edit("ᴄᴀɴ'ᴛ ᴄᴏɴɴᴇᴄᴛ ᴛᴏ ꜱᴇʀᴠᴇʀ ᴀᴛ ᴛʜᴇ ᴍᴏᴍᴇɴᴛ, ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ!") # Font applied
        return
    except Exception as e:
        await msg.edit(f"ꜱᴘᴇᴇᴅᴛᴇꜱᴛ ꜰᴀɪʟᴇᴅ: {e}") # Font applied
        return

    photo = result.get('share')
    # Font applied to labels
    text = f'''
➲ <b>ꜱᴘᴇᴇᴅᴛᴇꜱᴛ ɪɴꜰᴏ</b>
┠ <b>ᴜᴘʟᴏᴀᴅ:</b> <code>{get_size(result.get('upload', 0))}/s</code>
┠ <b>ᴅᴏᴡɴʟᴏᴀᴅ:</b>  <code>{get_size(result.get('download', 0))}/s</code>
┠ <b>ᴘɪɴɢ:</b> <code>{result.get('ping', 'N/A')} ms</code>
┠ <b>ᴛɪᴍᴇ:</b> <code>{result.get('timestamp', 'N/A')}</code>
┠ <b>ᴅᴀᴛᴀ ꜱᴇɴᴛ:</b> <code>{get_size(int(result.get('bytes_sent', 0)))}</code>
┖ <b>ᴅᴀᴛᴀ ʀᴇᴄᴇɪᴠᴇᴅ:</b> <code>{get_size(int(result.get('bytes_received', 0)))}</code>

➲ <b>ꜱᴘᴇᴇᴅᴛᴇꜱᴛ ꜱᴇʀᴠᴇʀ</b>
┠ <b>ɴᴀᴍᴇ:</b> <code>{result.get('server', {}).get('name', 'N/A')}</code>
┠ <b>ᴄᴏᴜɴᴛʀʏ:</b> <code>{result.get('server', {}).get('country', 'N/A')}, {result.get('server', {}).get('cc', 'N/A')}</code>
┠ <b>ꜱᴘᴏɴꜱᴏʀ:</b> <code>{result.get('server', {}).get('sponsor', 'N/A')}</code>
┠ <b>ʟᴀᴛᴇɴᴄʏ:</b> <code>{result.get('server', {}).get('latency', 'N/A')}</code>
┠ <b>ʟᴀᴛɪᴛᴜᴅᴇ:</b> <code>{result.get('server', {}).get('lat', 'N/A')}</code>
┖ <b>ʟᴏɴɢɪᴛᴜᴅᴇ:</b> <code>{result.get('server', {}).get('lon', 'N/A')}</code>

➲ <b>ᴄʟɪᴇɴᴛ ᴅᴇᴛᴀɪʟꜱ</b>
┠ <b>ɪᴘ ᴀᴅᴅʀᴇꜱꜱ:</b> <code>{result.get('client', {}).get('ip', 'N/A')}</code>
┠ <b>ʟᴀᴛɪᴛᴜᴅᴇ:</b> <code>{result.get('client', {}).get('lat', 'N/A')}</code>
┠ <b>ʟᴏɴɢɪᴛᴜᴅᴇ:</b> <code>{result.get('client', {}).get('lon', 'N/A')}</code>
┠ <b>ᴄᴏᴜɴᴛʀʏ:</b> <code>{result.get('client', {}).get('country', 'N/A')}</code>
┠ <b>ɪꜱᴘ:</b> <code>{result.get('client', {}).get('isp', 'N/A')}</code>
┖ <b>ɪꜱᴘ ʀᴀᴛɪɴɢ:</b> <code>{result.get('client', {}).get('isprating', 'N/A')}</code>
'''
    if photo:
        await message.reply_photo(photo=photo, caption=text)
        await msg.delete()
    else:
        await msg.edit(text)


@Client.on_message(filters.command("info"))
async def who_is(client, message):
    status_message = await message.reply_text(
        "ꜰᴇᴛᴄʜɪɴɢ ᴜꜱᴇʀ ɪɴꜰᴏ..." # Font applied
    )
    from_user = None
    if message.reply_to_message and message.reply_to_message.from_user:
        from_user = message.reply_to_message.from_user
    elif len(message.command) > 1:
        try:
            user_arg = message.command[1]
            if user_arg.startswith('@'):
                from_user = await client.get_users(user_arg)
            else:
                from_user = await client.get_users(int(user_arg))
        except Exception as error:
            await status_message.edit(f'ᴇʀʀᴏʀ: {error}') # Font applied
            return
    else:
        from_user = message.from_user

    if not from_user:
         await status_message.edit("ᴄᴏᴜʟᴅ ɴᴏᴛ ꜰɪɴᴅ ᴛʜᴇ ᴜꜱᴇʀ.") # Font applied
         return

    # Font applied to labels
    message_out_str = ""
    message_out_str += f"<b>➲ꜰɪʀꜱᴛ ɴᴀᴍᴇ:</b> {from_user.first_name}\n"
    last_name = from_user.last_name or 'ɴᴏᴛ ʜᴀᴠᴇ'
    message_out_str += f"<b>➲ʟᴀꜱᴛ ɴᴀᴍᴇ:</b> {last_name}\n"
    message_out_str += f"<b>➲ᴛᴇʟᴇɢʀᴀᴍ ɪᴅ:</b> <code>{from_user.id}</code>\n"
    username = f'@{from_user.username}' if from_user.username else 'ɴᴏᴛ ʜᴀᴠᴇ'
    dc_id = from_user.dc_id or "ɴᴏᴛ ꜰᴏᴜɴᴅ"
    message_out_str += f"<b>➲ᴅᴀᴛᴀ ᴄᴇɴᴛʀᴇ:</b> <code>{dc_id}</code>\n"
    message_out_str += f"<b>➲ᴜꜱᴇʀɴᴀᴍᴇ:</b> {username}\n"
    message_out_str += f"<b>➲ʟᴀꜱᴛ ᴏɴʟɪɴᴇ:</b> {last_online(from_user)}\n"
    message_out_str += f"<b>➲ᴜꜱᴇʀ ʟɪɴᴋ:</b> <a href='tg://user?id={from_user.id}'><b>ᴄʟɪᴄᴋ ʜᴇʀᴇ</b></a>\n"
    if message.chat.type in [enums.ChatType.SUPERGROUP, enums.ChatType.GROUP]:
        try:
            chat_member_p = await message.chat.get_member(from_user.id)
            joined_date = chat_member_p.joined_date.strftime('%Y.%m.%d %H:%M:%S') if chat_member_p.joined_date else 'ɴᴏᴛ ꜰᴏᴜɴᴅ'
            message_out_str += (
                f"<b>➲ᴊᴏɪɴᴇᴅ ᴛʜɪꜱ ᴄʜᴀᴛ ᴏɴ:</b> <code>"
                f"{joined_date}"
                "</code>\n"
            )
        except UserNotParticipant:
            message_out_str += f"<b>➲ᴊᴏɪɴᴇᴅ ᴛʜɪꜱ ᴄʜᴀᴛ ᴏɴ:</b> ɴᴏᴛ ᴀ ᴍᴇᴍʙᴇʀ\n" # Font applied

    chat_photo = from_user.photo
    if chat_photo:
        local_user_photo = await client.download_media(
            message=chat_photo.big_file_id
        )
        await message.reply_photo(
            photo=local_user_photo,
            quote=True,
            caption=message_out_str,
            parse_mode=enums.ParseMode.HTML,
            disable_notification=True
        )
        os.remove(local_user_photo)
    else:
        await message.reply_text(
            text=message_out_str,
            quote=True,
            parse_mode=enums.ParseMode.HTML,
            disable_notification=True
        )
    await status_message.delete()


def last_online(from_user):
    # Font applied to status descriptions
    time = ""
    if from_user.is_bot:
        time += "🤖 ʙᴏᴛ :("
    elif from_user.status == enums.UserStatus.RECENTLY:
        time += "ʀᴇᴄᴇɴᴛʟʏ"
    elif from_user.status == enums.UserStatus.LAST_WEEK:
        time += "ᴡɪᴛʜɪɴ ᴛʜᴇ ʟᴀꜱᴛ ᴡᴇᴇᴋ"
    elif from_user.status == enums.UserStatus.LAST_MONTH:
        time += "ᴡɪᴛʜɪɴ ᴛʜᴇ ʟᴀꜱᴛ ᴍᴏɴᴛʜ"
    elif from_user.status == enums.UserStatus.LONG_AGO:
        time += "ᴀ ʟᴏɴɢ ᴛɪᴍᴇ ᴀɢᴏ :("
    elif from_user.status == enums.UserStatus.ONLINE:
        time += "ᴄᴜʀʀᴇɴᴛʟʏ ᴏɴʟɪɴᴇ"
    elif from_user.status == enums.UserStatus.OFFLINE:
        try: # Add try-except for potential naive datetime
             time += from_user.last_online_date.strftime("%Y-%m-%d %H:%M:%S")
        except AttributeError:
             time += "ᴜɴᴋɴᴏᴡɴ (ᴏꜰꜰʟɪɴᴇ)"
    else:
        time += "ᴜɴᴋɴᴏᴡɴ"
    return time

