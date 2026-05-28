import re
from os import environ
import logging

logger = logging.getLogger(__name__)

def is_enabled(type, value):
    data = environ.get(type, str(value))
    if data.lower() in ["true", "yes", "1", "enable", "y"]: return True
    elif data.lower() in ["false", "no", "0", "disable", "n"]: return False
    else: return value 

# Core Bot Settings (Must be set in ENV)
API_ID = int(environ.get('API_ID', 0))
API_HASH = environ.get('API_HASH', '')
BOT_TOKEN = environ.get('BOT_TOKEN', '')
if not (API_ID and API_HASH and BOT_TOKEN):
    logger.error('Missing API_ID, API_HASH, or BOT_TOKEN. Exiting.')
    exit()

BOT_ID = BOT_TOKEN.split(":")[0]

# Admins & Channels
ADMINS = [int(x) for x in environ.get('ADMINS', '').split()]
if not ADMINS:
    logger.error('ADMINS missing. Exiting.')
    exit()

INDEX_CHANNELS = [int(x) if x.startswith("-") else x for x in environ.get('INDEX_CHANNELS', '').split()]
LOG_CHANNEL = int(environ.get('LOG_CHANNEL', 0))
SUPPORT_GROUP = int(environ.get('SUPPORT_GROUP', 0))
UPDATES_LINK = environ.get('UPDATES_LINK', '')
SUPPORT_LINK = environ.get('SUPPORT_LINK', '')
PICS = (environ.get('PICS', 'https://files.catbox.moe/e0a7rw.png')).split()

# Databases
DATA_DATABASE_URL = environ.get('DATA_DATABASE_URL', '')
DATABASE_URIS = environ.get('DATABASE_URIS', '')
if not (DATA_DATABASE_URL and DATABASE_URIS):
    logger.error('Database URIs are missing. Exiting.')
    exit()

DATABASE_NAME = environ.get('DATABASE_NAME', "FilesDB")
COLLECTION_NAME = environ.get('COLLECTION_NAME', 'Files')
DB_MAX_SIZE_MB = int(environ.get('DB_MAX_SIZE_MB', 460))

# Bot Config & Toggles
TIME_ZONE = environ.get('TIME_ZONE', 'UTC')
DELETE_TIME = int(environ.get('DELETE_TIME', 3600))
CACHE_TIME = int(environ.get('CACHE_TIME', 300))
MAX_BTN = int(environ.get('MAX_BTN', 8))
INDEX_EXTENSIONS = [ext.lower().strip().lstrip('.') for ext in environ.get('INDEX_EXTENSIONS', 'mkv mp4 pdf zip rar apk 7z txt docx').split()]
PM_FILE_DELETE_TIME = int(environ.get('PM_FILE_DELETE_TIME', 3600))

USE_CAPTION_FILTER = is_enabled('USE_CAPTION_FILTER', True)
AUTO_DELETE = is_enabled('AUTO_DELETE', False)
WELCOME = is_enabled('WELCOME', False)
PROTECT_CONTENT = is_enabled('PROTECT_CONTENT', False)
LINK_MODE = is_enabled("LINK_MODE", False)
SPELL_CHECK = is_enabled("SPELL_CHECK", False)