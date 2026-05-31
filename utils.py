import asyncio
import logging
from datetime import datetime
import pytz
from hydrogram.errors import UserNotParticipant, FloodWait
from hydrogram.types import InlineKeyboardButton, Message
from hydrogram import enums, types
from database.users_chats_db import db
from info import TIME_ZONE

logger = logging.getLogger(__name__)

class temp(object):
    START_TIME = 0
    BANNED_USERS = []
    BANNED_CHATS = []
    ME = None
    CANCEL = False
    U_NAME = None
    B_NAME = None
    SETTINGS = {}
    FILES = {}
    BOT = None
    VERIFICATIONS = {}

async def is_subscribed(bot, query_or_message):
    btn = []
    stg = await db.get_bot_sttgs()
    if not stg: return btn
    user_id = query_or_message.from_user.id
    fsub_channels_str = stg.get('FORCE_SUB_CHANNELS', '')
    all_fsub_ids = [int(c) for c in fsub_channels_str.split() if c]
    if not all_fsub_ids: return btn
    for chat_id in all_fsub_ids:
        user_is_member = False
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            if member.status not in [enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.BANNED]:
                user_is_member = True
        except: pass
        if not user_is_member:
            try:
                 chat = await bot.get_chat(chat_id)
                 invite_link = chat.invite_link or (await bot.create_chat_invite_link(chat_id)).invite_link
                 btn.append([InlineKeyboardButton(f'ᴊᴏɪɴ {chat.title}', url=invite_link)])
            except: pass
    return btn

def upload_image(*args, **kwargs): return None
def list_to_str(k): return "ɴ/ᴀ" if not k else (str(k[0]) if len(k) == 1 else ', '.join(map(str, k)))
async def get_poster(*args, **kwargs): return None
async def get_shortlink(url, api, link): return link
def get_seconds(time_string): return 0

async def is_check_admin(bot, chat_id, user_id):
    try: 
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
    except: return False

async def get_verify_status(*args, **kwargs): return {'is_verified': False, 'verify_token': '', 'link': ''}
async def update_verify_status(*args, **kwargs): pass

async def get_settings(group_id):
    group_id = int(group_id)
    settings = temp.SETTINGS.get(group_id)
    if not settings:
        settings = await db.get_settings(group_id)
        temp.SETTINGS[group_id] = settings
    return settings or {}

async def save_group_settings(group_id, key, value):
    group_id = int(group_id)
    current = await get_settings(group_id)
    current[key] = value
    temp.SETTINGS[group_id] = current.copy()
    await db.update_settings(group_id, {key: value})

async def broadcast_messages(user_id, message, pin=False):
    try:
        m = await message.copy(chat_id=user_id)
        if pin: await m.pin(disable_notification=True)
        return "Success"
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await broadcast_messages(user_id, message, pin)
    except:
        await db.delete_user(int(user_id))
        return "Error"

async def groups_broadcast_messages(chat_id, message, pin=False):
    try:
        k = await message.copy(chat_id=chat_id)
        if pin: await k.pin(disable_notification=True)
        return "Success"
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await groups_broadcast_messages(chat_id, message, pin)
    except:
        await db.delete_chat(int(chat_id))
        return "Error"

def get_size(size_bytes):
    if not isinstance(size_bytes, (int, float)) or size_bytes < 0: return "0 B"
    size = float(size_bytes); units = ["B", "KB", "MB", "GB", "TB", "PB", "EB"]; i = 0
    while size >= 1024.0 and i < len(units) - 1: i += 1; size /= 1024.0
    return "%.2f %s" % (size, units[i])

def get_readable_time(seconds):
    if not isinstance(seconds, (int, float)) or seconds < 0: return "0s"
    seconds = int(seconds); result = ''; periods = [('d', 86400), ('h', 3600), ('m', 60), ('s', 1)]
    for name, secs in periods:
        if seconds >= secs: val, seconds = divmod(seconds, secs); result += f'{val}{name}'
    return result or '0s'

def get_wish():
    try: hour = int(datetime.now(pytz.timezone(TIME_ZONE)).strftime("%H"))
    except: hour = datetime.now().hour
    if 5 <= hour < 12: return "ɢᴏᴏᴅ ᴍᴏʀɴɪɴɢ ☀️"
    elif 12 <= hour < 18: return "ɢᴏᴏᴅ ᴀꜰᴛᴇʀɴᴏᴏɴ 🌤️"
    else: return "ɢᴏᴏᴅ ᴇᴠᴇɴɪɴɢ 🌙"
