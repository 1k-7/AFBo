import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(module)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler("bot.log")]
)
logging.getLogger('hydrogram').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

import os
import time
import asyncio
from hydrogram import types, Client, idle
from hydrogram.errors import FloodWait
from typing import Union, Optional, AsyncGenerator
from info import (LOG_CHANNEL, API_ID, API_HASH, BOT_TOKEN, ADMINS)
from utils import temp
from database.users_chats_db import db

class Bot(Client):
    def __init__(self):
        super().__init__(
            name='Auto_Filter_Bot',
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            plugins={"root": "plugins"},
            workers=8,
            sleep_threshold=10
        )
        logger.info("Bot Client Initialized.")

    async def start(self):
        try:
            await super().start()
            temp.START_TIME = time.time()
            temp.BOT = self

            me = await self.get_me()
            temp.ME = me.id
            temp.U_NAME = me.username
            temp.B_NAME = me.first_name
            logger.info(f"Bot Info: ID={me.id}, Username=@{me.username}")

            try:
                startup_msg = f"<b>✔️ {me.mention} ɪꜱ ɴᴏᴡ ᴏɴʟɪɴᴇ!</b>"
                await self.send_message(chat_id=LOG_CHANNEL, text=startup_msg)
            except Exception as e: 
                logger.error(f"Log channel send error: {e}")

            logger.info(f"@{me.username} started successfully. ✓")

        except FloodWait as e:
             logger.warning(f"TELEGRAM FLOODWAIT: Sleeping for {e.value} seconds.")
             await asyncio.sleep(e.value + 5)
             await self.start()
             return
        except Exception as start_err:
             logger.critical(f"Critical error during bot start: {start_err}", exc_info=True)
             raise start_err

    async def stop(self, *args):
        logger.info("Stopping bot...")
        await super().stop()
        logger.info("Bot Stopped!")

    async def iter_messages(self: Client, chat_id: Union[int, str], limit: int, offset: int = 0) -> Optional[AsyncGenerator["types.Message", None]]:
        current = offset
        end_id = limit
        while current < end_id:
            chunk_size = min(200, end_id - current)
            if chunk_size <= 0: return
            message_ids = list(range(current, current + chunk_size))
            try:
                messages = await self.get_messages(chat_id, message_ids)
                if not messages:
                    current += chunk_size
                    continue
            except FloodWait as e:
                await asyncio.sleep(e.value)
                continue
            except Exception as e:
                current += chunk_size
                continue

            for message in messages:
                if message is None: continue
                yield message
            current += chunk_size

async def main():
    app = Bot()
    await app.start()
    logger.info("Bot is running. Idling...")
    await idle()
    await app.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped manually.")