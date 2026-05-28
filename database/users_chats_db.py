from pymongo import MongoClient
from info import (
    BOT_ID, ADMINS, DATABASE_NAME, DATA_DATABASE_URL, COLLECTION_NAME, # <--- ADDED COLLECTION_NAME HERE
    IMDB_TEMPLATE, WELCOME_TEXT, LINK_MODE,
    TUTORIAL, SHORTLINK_URL, SHORTLINK_API, SHORTLINK, FILE_CAPTION,
    IMDB, WELCOME, SPELL_CHECK, PROTECT_CONTENT, AUTO_DELETE, IS_STREAM,
    VERIFY_EXPIRE
)
import time
from datetime import datetime, timedelta, timezone # Added timezone
import logging
import pytz # Import pytz

# Import the new multi-DB connection objects
from .ia_filterdb import file_db_clients, file_db_collections

logger = logging.getLogger(__name__)

# --- Database Connections ---
# Remove old file_db clients, they are now in ia_filterdb.py
data_db_client = None; data_db = None

try:
    data_db_client = MongoClient(DATA_DATABASE_URL)
    data_db = data_db_client[DATABASE_NAME]
    logger.info("Connected to Data DB.")
except Exception as e:
    logger.critical(f"Cannot connect to data DB: {e}", exc_info=True); exit()

# The file DB connections are already handled in ia_filterdb

# --- LOCAL GET_SIZE TO AVOID CIRCULAR IMPORT ---
def get_size(size_bytes):
    if size_bytes is None or not isinstance(size_bytes, (int, float)) or size_bytes < 0: return "0 B"
    size = float(size_bytes); units = ["B", "KB", "MB", "GB", "TB", "PB", "EB"]; i = 0
    while size >= 1024.0 and i < len(units) - 1: i += 1; size /= 1024.0
    return "%.2f %s" % (size, units[i])
# --- END LOCAL GET_SIZE ---


class Database:
    # Default settings for groups
    default_setgs = {
        'file_secure': PROTECT_CONTENT, 'imdb': IMDB, 'spell_check': SPELL_CHECK,
        'auto_delete': AUTO_DELETE, 'welcome': WELCOME, 'welcome_text': WELCOME_TEXT,
        'template': IMDB_TEMPLATE, 'caption': FILE_CAPTION, 'url': SHORTLINK_URL,
        'api': SHORTLINK_API, 'shortlink': SHORTLINK, 'tutorial': TUTORIAL,
        'links': LINK_MODE
    }

    # Default verification status for users
    default_verify = {
        'is_verified': False,
        'verified_time': None, # Use None or epoch start instead of 0
        'verify_token': "",
        'link': "",
        'expire_time': None # Use None or epoch start instead of 0
    }

    def __init__(self):
        self.col = data_db.Users # User information (ID, name, ban status, verify status)
        self.grp = data_db.Groups # Group information (ID, title, chat status, settings)
        # self.prm = data_db.Premiums # Removed
        self.req = data_db.Requests # Join requests
        self.con = data_db.Connections # PM connections to groups
        self.stg = data_db.Settings # Bot-wide settings

    def new_user(self, id, name):
        # Creates a default user document
        return dict(
            id=int(id), name=name,
            ban_status=dict(is_banned=False, ban_reason=""),
            verify_status=self.default_verify.copy()
        )

    def new_group(self, id, title):
        # Creates a default group document
        return dict(
            id=int(id), title=title,
            chat_status=dict(is_disabled=False, reason=""),
            settings=self.default_setgs.copy()
        )

    # --- User Methods ---
    def add_user(self, id, name):
        # Adds a user if they don't exist (synchronous)
        user_id = int(id)
        if not self.col.find_one({'id': user_id}):
             user = self.new_user(user_id, name)
             try:
                 self.col.insert_one(user)
                 logger.info(f"New user {name} ({user_id}) added to DB.")
             except Exception as e:
                 logger.error(f"Error adding user {user_id}: {e}")

    def is_user_exist(self, id):
        # Checks if a user exists (synchronous)
        user = self.col.find_one({'id': int(id)})
        return bool(user)

    def total_users_count(self):
        # Gets total user count (synchronous)
        try: return self.col.estimated_document_count()
        except: return self.col.count_documents({})

    def remove_ban(self, id):
        # Unbans a user (synchronous)
        ban_status = dict(is_banned=False, ban_reason='')
        self.col.update_one({'id': int(id)}, {'$set': {'ban_status': ban_status}})
        logger.info(f"User {id} unbanned.")

    def ban_user(self, user_id, ban_reason="No Reason"):
        # Bans a user (synchronous)
        ban_status = dict(is_banned=True, ban_reason=ban_reason)
        self.col.update_one({'id': int(user_id)}, {'$set': {'ban_status': ban_status}})
        logger.info(f"User {user_id} banned. Reason: {ban_reason}")

    def get_ban_status(self, id):
        # Gets ban status (synchronous)
        default = dict(is_banned=False, ban_reason='')
        user = self.col.find_one({'id': int(id)})
        return user.get('ban_status', default) if user else default

    def get_all_users(self):
        # Returns a cursor for all users (synchronous)
        return self.col.find({})

    def delete_user(self, user_id):
        # Deletes a user (synchronous)
        try:
             result = self.col.delete_many({'id': int(user_id)})
             logger.info(f"Deleted {result.deleted_count} user(s) with ID {user_id}.")
        except Exception as e:
             logger.error(f"Error deleting user {user_id}: {e}")

    # --- Join Request Methods ---
    def find_join_req(self, id):
        # Checks if a join request exists (synchronous)
        try:
             return bool(self.req.find_one({'id': int(id)}))
        except Exception as e:
             logger.error(f"Error finding join request for {id}: {e}")
             return False

    def add_join_req(self, id):
        # Adds a join request if not already present (synchronous)
        user_id = int(id)
        if not self.find_join_req(user_id):
            try:
                self.req.insert_one({'id': user_id})
                logger.debug(f"Added join request for user {user_id}.")
            except Exception as e:
                 logger.error(f"Error adding join request for {user_id}: {e}")

    def del_join_req(self):
        # Deletes all join requests (synchronous)
        try:
             result = self.req.delete_many({})
             logger.info(f"Deleted {result.deleted_count} join requests.")
        except Exception as e:
             logger.error(f"Error deleting join requests: {e}")

    # --- Get Banned Lists ---
    def get_banned(self):
        # Gets lists of banned users and chats (synchronous)
        try:
             users_cursor = self.col.find({'ban_status.is_banned': True}, {'id': 1})
             chats_cursor = self.grp.find({'chat_status.is_disabled': True}, {'id': 1})
             b_users = [user['id'] for user in users_cursor]
             b_chats = [chat['id'] for chat in chats_cursor]
             return b_users, b_chats
        except Exception as e:
             logger.error(f"Error getting banned lists: {e}")
             return [], []

    # --- Group Methods ---
    def add_chat(self, chat_id, title):
        # Adds a group if it doesn't exist (synchronous)
        group_id = int(chat_id)
        if not self.grp.find_one({'id': group_id}):
             chat = self.new_group(group_id, title)
             try:
                  self.grp.insert_one(chat)
                  logger.info(f"New group '{title}' ({group_id}) added to DB.")
             except Exception as e:
                  logger.error(f"Error adding group {group_id}: {e}")

    def get_chat(self, chat_id):
        # Gets group status (synchronous)
        chat = self.grp.find_one({'id': int(chat_id)})
        default_status = {'is_disabled': False, 'reason': ''}
        return chat.get('chat_status', default_status) if chat else default_status

    def re_enable_chat(self, id):
        # Enables a group (synchronous)
        chat_status = dict(is_disabled=False, reason="")
        self.grp.update_one({'id': int(id)}, {'$set': {'chat_status': chat_status}})
        logger.info(f"Group {id} re-enabled.")

    def update_settings(self, id, settings):
        # Updates group settings (synchronous)
        # Fix: Use $set to update only specified keys
        self.grp.update_one({'id': int(id)}, {'$set': {f'settings.{k}': v for k, v in settings.items()}})
        logger.debug(f"Updated settings for group {id}: {settings.keys()}")

    def get_settings(self, id):
        # Gets group settings, merging with defaults (synchronous)
        chat = self.grp.find_one({'id': int(id)})
        saved_settings = chat.get('settings', {}) if chat else {}
        final_settings = self.default_setgs.copy()
        final_settings.update(saved_settings)
        return final_settings

    def disable_chat(self, chat_id, reason="No Reason"):
        # Disables a group (synchronous)
        chat_status = dict(is_disabled=True, reason=reason)
        self.grp.update_one({'id': int(chat_id)}, {'$set': {'chat_status': chat_status}})
        logger.info(f"Group {chat_id} disabled. Reason: {reason}")

    def delete_chat(self, grp_id):
        # Deletes a group (synchronous)
        try:
             result = self.grp.delete_many({'id': int(grp_id)})
             logger.info(f"Deleted {result.deleted_count} group(s) with ID {grp_id}.")
        except Exception as e:
             logger.error(f"Error deleting group {grp_id}: {e}")

    # --- Verification Status Methods ---
    def get_verify_status(self, user_id):
        # Gets verification status, ensuring times are valid (synchronous)
        user = self.col.find_one({'id': int(user_id)})
        default_copy = self.default_verify.copy()
        if not user: return default_copy

        info = user.get('verify_status', default_copy)
        # Ensure times are datetime objects or None
        verified_time = info.get('verified_time')
        expire_time = info.get('expire_time')

        if not isinstance(verified_time, datetime) and verified_time is not None:
             info['verified_time'] = None # Invalidate non-datetime
        if not isinstance(expire_time, datetime) and expire_time is not None:
             info['expire_time'] = None # Invalidate non-datetime

        # Calculate expire_time if missing/invalid but verified_time is valid
        if info.get('is_verified') and info['verified_time'] and not info['expire_time']:
            try:
                 # Use UTC for calculation if verified_time is naive
                 base_time = info['verified_time']
                 if base_time.tzinfo is None:
                     base_time = base_time.replace(tzinfo=timezone.utc)
                 info['expire_time'] = base_time + timedelta(seconds=VERIFY_EXPIRE)
            except Exception as e:
                 logger.error(f"Error calculating expire_time for user {user_id}: {e}")
                 info['expire_time'] = None # Reset if calculation fails

        return info.copy() # Return copy

    def update_verify_status(self, user_id, verify_data):
        # Updates verification status (synchronous)
        # Ensure times being saved are datetime objects
        if 'verified_time' in verify_data and not isinstance(verify_data['verified_time'], datetime):
             verify_data['verified_time'] = None # Or convert if possible
        if 'expire_time' in verify_data and not isinstance(verify_data['expire_time'], datetime):
             verify_data['expire_time'] = None # Or convert if possible
        self.col.update_one({'id': int(user_id)}, {'$set': {'verify_status': verify_data}}, upsert=True) # Upsert in case user doc deleted race condition
        logger.debug(f"Updated verify status for user {user_id}.")

    # --- Count/Size Methods (Synchronous) ---
    def total_chat_count(self):
        try: return self.grp.estimated_document_count()
        except: return self.grp.count_documents({})

    def get_all_chats(self):
        return self.grp.find({})

    def get_all_files_db_stats(self):
        """Gets stats for all connected file databases."""
        stats = []
        if not file_db_clients:
            return stats
            
        for i, client in enumerate(file_db_clients):
            db_name = DATABASE_NAME
            coll_name = COLLECTION_NAME # <--- THIS IS THE VARIABLE THAT WAS UNDEFINED
            try:
                coll_stats = None
                coll_count = 0
                db_size = 0
                
                # Use the collection object's database name if available
                if i < len(file_db_collections):
                    coll = file_db_collections[i]
                    db_name = coll.database.name
                    coll_name = coll.name
                    
                    coll_stats = client[db_name].command("collStats", coll_name)
                    coll_count = coll_stats.get('count', 0)
                    db_size = coll_stats.get('storageSize', 0) # Use storageSize for quota
                else:
                    # Fallback if collection list is somehow out of sync (shouldn't happen)
                    db_stats_fb = client[db_name].command("dbstats")
                    db_size = db_stats_fb.get('storageSize', 0) # Use storageSize for quota

                stats.append({
                    'name': f"DB #{i+1}",
                    'db_name': db_name,
                    'coll_name': coll_name,
                    'size': db_size, # <--- This is now storageSize
                    'storage_size': coll_stats.get('storageSize', 0) if coll_stats else 0,
                    'collections': 1, # We are only checking one
                    'objects': coll_count, # Use coll_count
                    'coll_count': coll_count # <--- Use collection count
                })
            except Exception as e:
                logger.error(f"Error get_files_db_stats for DB #{i+1}: {e}")
                stats.append({
                    'name': f"DB #{i+1}",
                    'db_name': db_name,
                    'coll_name': coll_name,
                    'size': 0,
                    'coll_count': 0, # <--- Add default
                    'error': str(e)
                })
        return stats

    # Removed get_second_files_db_size()

    def get_data_db_size(self):
        try: return data_db.command("dbstats")['dataSize']
        except Exception as e: logger.error(f"Error get_data_db_size: {e}"); return 0

    # --- Premium Methods (Removed/Dummy) ---
    def get_premium_count(self):
        # logger.warning("get_premium_count called, but premium is disabled. Returning 0.")
        return 0 # Premium disabled

    # get_plan, update_plan, get_premium_users removed

    # --- Connection Methods ---
    def add_connect(self, group_id, user_id):
        # Adds group to user's connection list (synchronous)
        self.con.update_one(
             {'_id': int(user_id)},
             {'$addToSet': {"group_ids": int(group_id)}},
             upsert=True
         )
        logger.debug(f"Connected group {group_id} for user {user_id}.")

    def get_connections(self, user_id):
        # Gets connected groups for a user (synchronous)
        user = self.con.find_one({'_id': int(user_id)})
        return user.get("group_ids", []) if user else []

    # --- Bot Settings Methods ---
    def update_bot_sttgs(self, var, val):
        # Updates bot-wide settings (synchronous)
        self.stg.update_one(
             {'id': BOT_ID},
             {'$set': {var: val}},
             upsert=True
         )
        logger.info(f"Updated bot setting: {var} = {val}")

    def get_bot_sttgs(self):
        # Gets bot-wide settings, merging with defaults (synchronous)
        settings = self.stg.find_one({'id': BOT_ID})
        default_bot_settings = {
             'FORCE_SUB_CHANNELS': '', 'REQUEST_FORCE_SUB_CHANNELS': None,
             'AUTO_FILTER': True, 'PM_SEARCH': True,
             'CURRENT_DB_INDEX': 0, # Add the default active DB index
             # Add any other bot-specific defaults here
        }
        if settings:
             default_bot_settings.update(settings)
        return default_bot_settings

# Instantiate the database class
db = Database()