import re
from os import environ
import os
from Script import script
import logging

logger = logging.getLogger(__name__)

def is_enabled(type, value):
    data = environ.get(type, str(value))
    if data.lower() in ["true", "yes", "1", "enable", "y"]:
        return True
    elif data.lower() in ["false", "no", "0", "disable", "n"]:
        return False
    else:
        logger.warning(f'{type} is invalid, using default: {value}')
        return value # Return the default value if invalid

def is_valid_ip(ip):
    # Basic IP pattern check
    ip_pattern = r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
    return re.match(ip_pattern, ip) is not None

# Bot information
API_ID = environ.get('API_ID', '24574155')
if len(API_ID) == 0:
    logger.error('API_ID is missing, exiting now')
    exit()
else:
    API_ID = int(API_ID)
API_HASH = environ.get('API_HASH', '94001be339d1264432c215f698bc3868')
if len(API_HASH) == 0:
    logger.error('API_HASH is missing, exiting now')
    exit()
BOT_TOKEN = environ.get('BOT_TOKEN', '7662068183:AAFzsXnI_OIpYgEb6-n-NFUEpKVjMTW3Xa0')
if len(BOT_TOKEN) == 0:
    logger.error('BOT_TOKEN is missing, exiting now')
    exit()
BOT_ID = BOT_TOKEN.split(":")[0]
PORT = int(environ.get('PORT', '8080')) # Default port for web server
PICS = (environ.get('PICS', 'https://files.catbox.moe/e0a7rw.png')).split() # List of image URLs

# Bot Admins
ADMINS = environ.get('ADMINS', '6909365769 7683268664 6732237631 7269579203')
if len(ADMINS) == 0:
    logger.error('ADMINS is missing, exiting now')
    exit()
else:
    ADMINS = [int(admins) for admins in ADMINS.split()]

# Channels
INDEX_CHANNELS = [int(index_channels) if index_channels.startswith("-") else index_channels for index_channels in environ.get('INDEX_CHANNELS', '-1002646022372').split()]
if len(INDEX_CHANNELS) == 0:
    logger.info('INDEX_CHANNELS is empty')
LOG_CHANNEL = environ.get('LOG_CHANNEL', '-1002708115180')
if len(LOG_CHANNEL) == 0:
    logger.error('LOG_CHANNEL is missing, exiting now')
    exit()
else:
    LOG_CHANNEL = int(LOG_CHANNEL)

# support group
SUPPORT_GROUP = environ.get('SUPPORT_GROUP', '-1002708115180')
if len(SUPPORT_GROUP) == 0:
    logger.error('SUPPORT_GROUP is missing, exiting now')
    exit()
else:
    SUPPORT_GROUP = int(SUPPORT_GROUP)

# MongoDB information
DATA_DATABASE_URL = environ.get('DATA_DATABASE_URL', "mongodb+srv://realbloodkin:cd3BGb5QXVTVshH2@cluster0.mrat6lh.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
if len(DATA_DATABASE_URL) == 0:
    logger.error('DATA_DATABASE_URL is missing, exiting now')
    exit()

# --- New Dynamic Files Database Setup ---
DATABASE_URIS = environ.get('DATABASE_URIS', "mongodb+srv://aldrinrishi01:GTgduaENtVUk6VLt@norcluster.qsaqymo.mongodb.net/?retryWrites=true&w=majority&appName=norCluster mongodb+srv://lordemperean:dpiU0sq9yGR5PjWc@cluster0.gvgbd5e.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0 mongodb+srv://norSearch3:5LAovtgK6Rp0DdJ3@cluster0.amkwtfi.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
if len(DATABASE_URIS) == 0:
    logger.error('DATABASE_URIS is missing, exiting now. Please provide at least one MongoDB URL.')
    exit()
# --- End New Setup ---

# Remove old single DB variables
# FILES_DATABASE_URL = environ.get('FILES_DATABASE_URL', "mongodb+srv://aldrinrishi01:GTgduaENtVUk6VLt@norcluster.qsaqymo.mongodb.net/?retryWrites=true&w=majority&appName=norCluster")
# SECOND_FILES_DATABASE_URL = environ.get('SECOND_FILES_DATABASE_URL', "mongodb+srv://lordemperean:dpiU0sq9yGR5PjWc@cluster0.gvgbd5e.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
# DB_CHANGE_LIMIT = int(environ.get('DB_CHANGE_LIMIT', 450)) # No longer needed

DATABASE_NAME = environ.get('DATABASE_NAME', "Cluster0") # Shared DB name
COLLECTION_NAME = environ.get('COLLECTION_NAME', 'Files') # Collection name for files
DB_MAX_SIZE_MB = int(environ.get('DB_MAX_SIZE_MB', 460)) # 90% of 512MB free tier

# Links
SUPPORT_LINK = environ.get('SUPPORT_LINK', 'https://t.me/norFedSupport')
UPDATES_LINK = environ.get('UPDATES_LINK', 'https://t.me/norFedUpdates')
FILMS_LINK = environ.get('FILMS_LINK', 'https://t.me/+Y3W42VyeQDljNGIy')
TUTORIAL = environ.get("TUTORIAL", "https://t.me/norFederation")
VERIFY_TUTORIAL = environ.get("VERIFY_TUTORIAL", "https://t.me/norFederation")

# Bot settings
TIME_ZONE = environ.get('TIME_ZONE', 'Asia/Kolkata') # Changed to IST
DELETE_TIME = int(environ.get('DELETE_TIME', 3600)) # Auto-delete delay in seconds
CACHE_TIME = int(environ.get('CACHE_TIME', 300)) # Inline cache time
MAX_BTN = int(environ.get('MAX_BTN', 8)) # Max buttons per page
LANGUAGES = [language.lower() for language in environ.get('LANGUAGES', 'hindi english telugu tamil kannada malayalam marathi punjabi').split()]
QUALITY = [quality.lower() for quality in environ.get('QUALITY', '360p 480p 720p 1080p 2160p').split()]
IMDB_TEMPLATE = environ.get("IMDB_TEMPLATE", script.IMDB_TEMPLATE) # Use default from Script.py
FILE_CAPTION = environ.get("FILE_CAPTION", script.FILE_CAPTION) # Use default from Script.py
SHORTLINK_URL = environ.get("SHORTLINK_URL", "") # Empty by default unless set
SHORTLINK_API = environ.get("SHORTLINK_API", "") # Empty by default unless set
VERIFY_EXPIRE = int(environ.get('VERIFY_EXPIRE', 86400)) # Verification validity in seconds
WELCOME_TEXT = environ.get("WELCOME_TEXT", script.WELCOME_TEXT) # Use default from Script.py
INDEX_EXTENSIONS = [ext.lower().strip().lstrip('.') for ext in environ.get('INDEX_EXTENSIONS', 'mkv mp4').split()] # Ensure no dots
PM_FILE_DELETE_TIME = int(environ.get('PM_FILE_DELETE_TIME', '3600')) # Delete time for files sent to PM

# Boolean settings (using is_enabled for clarity)
USE_CAPTION_FILTER = is_enabled('USE_CAPTION_FILTER', False) # Search in captions too?
IS_VERIFY = is_enabled('IS_VERIFY', False) # Enable user verification?
AUTO_DELETE = is_enabled('AUTO_DELETE', False) # Auto-delete results message in group?
WELCOME = is_enabled('WELCOME', False) # Send welcome message?
PROTECT_CONTENT = is_enabled('PROTECT_CONTENT', False) # Prevent forwarding from PM?
LONG_IMDB_DESCRIPTION = is_enabled("LONG_IMDB_DESCRIPTION", True) # Use full plot?
LINK_MODE = is_enabled("LINK_MODE", False) # Show results as links instead of buttons?
IMDB = is_enabled('IMDB', True) # Fetch IMDb data?
SPELL_CHECK = is_enabled("SPELL_CHECK", True) # Enable spelling suggestions?
SHORTLINK = is_enabled('SHORTLINK', False) # Use shortlinks for file access?

# for stream (if enabled)
IS_STREAM = is_enabled('IS_STREAM', False) # Enable streaming?
BIN_CHANNEL = environ.get("BIN_CHANNEL", "-1002614750404") # Channel for caching media for streaming
if IS_STREAM:
    if len(BIN_CHANNEL) == 0:
        logger.error('BIN_CHANNEL is missing, required for streaming, exiting now')
        exit()
    else:
        try:
             BIN_CHANNEL = int(BIN_CHANNEL)
        except ValueError:
             logger.error('BIN_CHANNEL ID must be an integer, exiting now')
             exit()

URL = environ.get("URL", "") # Web server URL (Auto-detected for Heroku/Koyeb if not set)
if IS_STREAM and len(URL) == 0:
    logger.warning('URL is not set, streaming might not work unless auto-detected by platform.')
elif len(URL) > 0:
    if URL.startswith(('https://', 'http://')):
        if not URL.endswith("/"):
            URL += '/'
    elif is_valid_ip(URL):
        URL = f'http://{URL}/' # Assume http for IP by default
    else:
        # Assume it's a platform app name if not IP or URL
        # Platform detection in bot.py might override/confirm this
        pass # Allow platform app names

# Premium system is disabled
IS_PREMIUM = False
# PRE_DAY_AMOUNT = int(environ.get('PRE_DAY_AMOUNT', '9'))
# UPI_ID = environ.get("UPI_ID", "")
# UPI_NAME = environ.get("UPI_NAME", "")
# RECEIPT_SEND_USERNAME = environ.get("RECEIPT_SEND_USERNAME", "")