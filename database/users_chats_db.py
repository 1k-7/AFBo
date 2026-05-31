import aiosqlite
import json
import logging
import os
from info import DATABASE_FILE

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_file):
        self.db_file = db_file
        self._initialized = False

    async def _init_db(self):
        if self._initialized: return
        async with aiosqlite.connect(self.db_file) as db:
            await db.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)')
            await db.execute('CREATE TABLE IF NOT EXISTS chats (id INTEGER PRIMARY KEY, title TEXT)')
            await db.execute('CREATE TABLE IF NOT EXISTS connections (group_id INTEGER, user_id INTEGER, PRIMARY KEY(group_id, user_id))')
            await db.execute('CREATE TABLE IF NOT EXISTS settings (chat_id INTEGER PRIMARY KEY, settings_json TEXT)')
            await db.execute('CREATE TABLE IF NOT EXISTS bot_settings (key TEXT PRIMARY KEY, value TEXT)')
            await db.commit()
        self._initialized = True

    async def add_user(self, id, name):
        await self._init_db()
        async with aiosqlite.connect(self.db_file) as db:
            await db.execute('INSERT OR IGNORE INTO users (id, name) VALUES (?, ?)', (id, name))
            await db.commit()

    async def is_user_exist(self, id):
        await self._init_db()
        async with aiosqlite.connect(self.db_file) as db:
            async with db.execute('SELECT 1 FROM users WHERE id = ?', (id,)) as cursor:
                return await cursor.fetchone() is not None

    async def total_users_count(self):
        await self._init_db()
        async with aiosqlite.connect(self.db_file) as db:
            async with db.execute('SELECT COUNT(*) FROM users') as cursor:
                return (await cursor.fetchone())[0]

    async def get_all_users(self):
        await self._init_db()
        async with aiosqlite.connect(self.db_file) as db:
            async with db.execute('SELECT id FROM users') as cursor:
                rows = await cursor.fetchall()
                return [{"id": row[0]} for row in rows]

    async def delete_user(self, user_id):
        await self._init_db()
        async with aiosqlite.connect(self.db_file) as db:
            await db.execute('DELETE FROM users WHERE id = ?', (int(user_id),))
            await db.commit()

    async def add_chat(self, chat, title):
        await self._init_db()
        async with aiosqlite.connect(self.db_file) as db:
            await db.execute('INSERT OR IGNORE INTO chats (id, title) VALUES (?, ?)', (chat, title))
            await db.commit()

    async def total_chat_count(self):
        await self._init_db()
        async with aiosqlite.connect(self.db_file) as db:
            async with db.execute('SELECT COUNT(*) FROM chats') as cursor:
                return (await cursor.fetchone())[0]

    async def get_all_chats(self):
        await self._init_db()
        async with aiosqlite.connect(self.db_file) as db:
            async with db.execute('SELECT id FROM chats') as cursor:
                rows = await cursor.fetchall()
                return [{"id": row[0]} for row in rows]

    async def delete_chat(self, chat_id):
        await self._init_db()
        async with aiosqlite.connect(self.db_file) as db:
            await db.execute('DELETE FROM chats WHERE id = ?', (int(chat_id),))
            await db.commit()

    async def get_bot_sttgs(self):
        await self._init_db()
        settings = {}
        async with aiosqlite.connect(self.db_file) as db:
            async with db.execute('SELECT key, value FROM bot_settings') as cursor:
                async for row in cursor:
                    settings[row[0]] = json.loads(row[1])
        return settings

    async def update_bot_sttgs(self, key, value):
        await self._init_db()
        val_str = json.dumps(value)
        async with aiosqlite.connect(self.db_file) as db:
            await db.execute('INSERT INTO bot_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value', (key, val_str))
            await db.commit()

    async def add_connect(self, group_id, user_id):
        await self._init_db()
        async with aiosqlite.connect(self.db_file) as db:
            await db.execute('INSERT OR IGNORE INTO connections (group_id, user_id) VALUES (?, ?)', (group_id, user_id))
            await db.commit()

    async def del_connect(self, group_id, user_id):
        await self._init_db()
        async with aiosqlite.connect(self.db_file) as db:
            await db.execute('DELETE FROM connections WHERE group_id = ? AND user_id = ?', (group_id, user_id))
            await db.commit()

    async def get_connections(self, user_id):
        await self._init_db()
        async with aiosqlite.connect(self.db_file) as db:
            async with db.execute('SELECT group_id FROM connections WHERE user_id = ?', (user_id,)) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]

    async def get_settings(self, chat_id):
        await self._init_db()
        async with aiosqlite.connect(self.db_file) as db:
            async with db.execute('SELECT settings_json FROM settings WHERE chat_id = ?', (chat_id,)) as cursor:
                row = await cursor.fetchone()
                if row: return json.loads(row[0])
                return {}

    async def update_settings(self, chat_id, settings_dict):
        await self._init_db()
        settings_json = json.dumps(settings_dict)
        async with aiosqlite.connect(self.db_file) as db:
            await db.execute('INSERT INTO settings (chat_id, settings_json) VALUES (?, ?) ON CONFLICT(chat_id) DO UPDATE SET settings_json = excluded.settings_json', (chat_id, settings_json))
            await db.commit()
            
    async def get_banned(self):
        stg = await self.get_bot_sttgs()
        return stg.get("banned_users", []), stg.get("banned_chats", [])

    async def get_data_db_size(self):
        return os.path.getsize(self.db_file) if os.path.exists(self.db_file) else 0

    async def get_all_files_db_stats(self):
        size = await self.get_data_db_size()
        await self._init_db()
        count = 0
        async with aiosqlite.connect(self.db_file) as db:
            try:
                async with db.execute('SELECT COUNT(*) FROM files') as cursor:
                    count = (await cursor.fetchone())[0]
            except Exception: pass
        return [{'name': 'bot_database.db', 'size': size, 'coll_count': count}]

db = Database(DATABASE_FILE)
