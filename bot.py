import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(module)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler("bot.log")]
)
logging.getLogger('hydrogram').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
logger.info("Starting Bot...")

import os
import time
import asyncio
import threading
import requests
from hydrogram import types, Client, idle
from hydrogram.errors import FloodWait
from aiohttp import web
from typing import Union, Optional, AsyncGenerator
from web import web_app
from info import (LOG_CHANNEL, API_ID, API_HASH, BOT_TOKEN, PORT, ADMINS, URL)
from utils import temp, get_readable_time
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
            logger.info("Hydrogram client started.")

            try:
                 loop = asyncio.get_running_loop()
                 b_users, b_chats = await loop.run_in_executor(None, db.get_banned)
                 logger.info("Fetched banned lists.")
            except Exception as db_err:
                 logger.error(f"Failed to fetch banned lists: {db_err}. Proceeding empty.")
                 b_users, b_chats = [], []

            temp.BANNED_USERS = b_users
            temp.BANNED_CHATS = b_chats
            temp.BOT = self

            if os.path.exists('restart.txt'):
                try:
                    with open("restart.txt") as file: chat_id, msg_id = map(int, file)
                    await self.edit_message_text(chat_id=chat_id, message_id=msg_id, text='✔️ ʀᴇꜱᴛᴀʀᴛᴇᴅ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ!')
                    os.remove('restart.txt')
                    logger.info("Restart message handled.")
                except Exception as e: logger.error(f"Restart message error: {e}")

            me = await self.get_me()
            temp.ME = me.id
            temp.U_NAME = me.username
            temp.B_NAME = me.first_name
            logger.info(f"Bot Info: ID={me.id}, Username=@{me.username}")

            try:
                web_runner = web.AppRunner(web_app)
                await web_runner.setup()
                site = web.TCPSite(web_runner, "0.0.0.0", PORT)
                await site.start()
                logger.info(f"Web server started on port {PORT}.")
            except OSError as e: logger.error(f"Web server failed: Port {PORT} busy? Error: {e}")
            except Exception as e: logger.error(f"Web server failed: {e}", exc_info=True)

            try:
                startup_msg = f"<b>✔️ {me.mention} ɪꜱ ɴᴏᴡ ᴏɴʟɪɴᴇ!</b>"
                await self.send_message(chat_id=LOG_CHANNEL, text=startup_msg)
            except Exception as e: logger.error(f"Log channel send error: {e}"); logger.warning("Ensure bot is admin in LOG_CHANNEL.")

            logger.info(f"@{me.username} started successfully. ✓")

        except FloodWait as e:
             logger.warning(f"TELEGRAM FLOODWAIT: Sleeping for {e.value} seconds.")
             await asyncio.sleep(e.value + 5) # Wait for the floodwait time + 5s
             # We will NOT stop the bot, we will let it continue starting
             await self.start() # Retry starting
             return # Return after the retry is done
        except Exception as start_err:
             logger.critical(f"Critical error during bot start method: {start_err}", exc_info=True)
             raise start_err

    async def stop(self, *args):
        logger.info("Stopping bot...")
        await super().stop()
        logger.info("Bot Stopped!")

    # Fix: Corrected iter_messages to properly iterate by ID range
    async def iter_messages(self: Client, chat_id: Union[int, str], limit: int, offset: int = 0) -> Optional[AsyncGenerator["types.Message", None]]:
        """
        Iterate through messages by ID range (forward).
        offset = start_message_id
        limit = end_message_id
        """
        current = offset # Start ID
        end_id = limit   # End ID (exclusive, as range works)
        
        while current < end_id:
            chunk_size = min(200, end_id - current)
            if chunk_size <= 0:
                return # We are done
            
            message_ids = list(range(current, current + chunk_size))
            
            try:
                messages = await self.get_messages(chat_id, message_ids)
                if not messages:
                    # No messages found in this range (e.g., deleted), skip to next chunk
                    current += chunk_size
                    continue
            except FloodWait as e:
                logger.warning(f"iter_messages FloodWait: sleep {e.value}s"); 
                await asyncio.sleep(e.value)
                continue # Retry this same chunk
            except Exception as e:
                logger.error(f"iter_messages error ({chat_id}): {e}"); 
                current += chunk_size # Skip this chunk on error
                continue

            for message in messages:
                if message is None:
                    continue
                yield message
            
            # Move to the next chunk
            current += chunk_size

def ping_loop():
    ping_interval = 180
    logger.info("Keepalive ping thread initiated.")
    while True:
        try:
            if not URL: logger.debug("Keepalive ping skipped: URL not set."); time.sleep(ping_interval * 2); continue
            ping_url = URL if URL.endswith('/') else URL + '/'
            logger.info(f"Pinging URL: {ping_url}")
            r = requests.get(ping_url, timeout=20)
            if r.status_code == 200: logger.info(f"Keepalive ping successful ✔️ (Status: {r.status_code})")
            else: logger.error(f"Keepalive ping failed: {r.status_code} ⚠️ - {r.text[:200]}")
        except requests.exceptions.Timeout: logger.error("Keepalive ping timed out ❌")
        except requests.exceptions.RequestException as e: logger.error(f"Keepalive ping exception: {e} ❌")
        except Exception as e: logger.error(f"Unexpected ping error: {e} ❌", exc_info=True)
        finally: time.sleep(ping_interval)

async def main():
    app = Bot()
    logger.info("Bot instance created inside main().")
    threading.Thread(target=ping_loop, daemon=True, name="PingThread").start()
    logger.info("Keepalive ping thread started.")
    await app.start()
    logger.info("Bot is running. Idling...")
    await idle()
    await app.stop()

if __name__ == "__main__":
    try:
        logger.info("Starting asyncio.run(main())...")
        asyncio.run(main())
    except RuntimeError as e:
         if "There is no current event loop" in str(e):
              logger.critical(f"FATAL: {e}. Event loop error during asyncio.run().")
         else:
              logger.critical(f"Bot failed - RuntimeError: {e}", exc_info=True)
    except KeyboardInterrupt:
         logger.info("Bot stopped manually.")
    except Exception as main_err:
        logger.critical(f"Bot failed unexpectedly in __main__: {main_err}", exc_info=True)
    finally:
         logger.info("Bot process ended.")