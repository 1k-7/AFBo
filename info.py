import re
from os import environ
import logging

logger = logging.getLogger(__name__)

def is_enabled(type, value):
    data = environ.get(type, str(value))
    if data.lower() in ["true", "yes", "1", "enable", "y"]: return True
    elif data.lower() in ["false", "no", "0", "disable", "n"]: return False
    else: return value 

# Core
API_ID = int(environ.get('API_ID', 0))
API_HASH = environ.get('API_HASH', '')
BOT_TOKEN = environ.get('BOT_TOKEN', '')
BOT_ID = BOT_TOKEN.split(":")[0] if BOT_TOKEN else ""

try:
    ADMINS = [int(x) for x in environ.get('ADMINS', '').split()]
except:
    ADMINS = []

INDEX_CHANNELS = [int(x) if x.startswith("-") else x for x in environ.get('INDEX_CHANNELS', '').split()]
LOG_CHANNEL = int(environ.get('LOG_CHANNEL', 0))
SUPPORT_GROUP = int(environ.get('SUPPORT_GROUP', 0))
UPDATES_LINK = environ.get('UPDATES_LINK', '')
SUPPORT_LINK = environ.get('SUPPORT_LINK', '')
FILMS_LINK = environ.get('FILMS_LINK', '')

# DB (SQLite used, MongoDB vars kept for backwards compatibility in old plugins)
DATABASE_FILE = environ.get('DATABASE_FILE', 'bot_database.db')
DATABASE_URIS = environ.get('DATABASE_URIS', '')
DATA_DATABASE_URL = environ.get('DATA_DATABASE_URL', '')
DATABASE_NAME = environ.get('DATABASE_NAME', 'FilesDB')
COLLECTION_NAME = environ.get('COLLECTION_NAME', 'Files')
DB_MAX_SIZE_MB = int(environ.get('DB_MAX_SIZE_MB', 460))

# Configs
TIME_ZONE = environ.get('TIME_ZONE', 'UTC')
DELETE_TIME = int(environ.get('DELETE_TIME', 3600))
CACHE_TIME = int(environ.get('CACHE_TIME', 300))
MAX_BTN = int(environ.get('MAX_BTN', 8))
INDEX_EXTENSIONS = [ext.lower().strip().lstrip('.') for ext in environ.get('INDEX_EXTENSIONS', 'mkv mp4 pdf zip rar apk 7z txt docx').split()]
PM_FILE_DELETE_TIME = int(environ.get('PM_FILE_DELETE_TIME', 3600))
PORT = int(environ.get('PORT', '8080'))

# Visuals/Texts
PICS = (environ.get('PICS', 'https://files.catbox.moe/e0a7rw.png')).split()
TUTORIAL = environ.get("TUTORIAL", "")
VERIFY_TUTORIAL = environ.get("VERIFY_TUTORIAL", "")

# Toggles
USE_CAPTION_FILTER = is_enabled('USE_CAPTION_FILTER', True)
AUTO_DELETE = is_enabled('AUTO_DELETE', False)
PROTECT_CONTENT = is_enabled('PROTECT_CONTENT', False)
LINK_MODE = is_enabled("LINK_MODE", False)
WELCOME = is_enabled('WELCOME', False)
SPELL_CHECK = is_enabled("SPELL_CHECK", False)
LONG_IMDB_DESCRIPTION = is_enabled("LONG_IMDB_DESCRIPTION", False)

# Stream & Shortlink & Verify (Dummies to satisfy imports)
URL = environ.get("URL", "")
BIN_CHANNEL = int(environ.get("BIN_CHANNEL", 0))
IS_STREAM = is_enabled('IS_STREAM', False)
IS_VERIFY = is_enabled('IS_VERIFY', False)
VERIFY_EXPIRE = int(environ.get('VERIFY_EXPIRE', 86400))
SHORTLINK_API = environ.get("SHORTLINK_API", "")
SHORTLINK_URL = environ.get("SHORTLINK_URL", "")
SHORTLINK = is_enabled('SHORTLINK', False)
LANGUAGES = ["hindi", "english", "telugu", "tamil", "kannada", "malayalam", "bengali", "marathi", "gujarati", "punjabi"]
QUALITY = ["360p", "480p", "720p", "1080p", "1440p", "2160p", "4k"]