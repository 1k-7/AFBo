from hydrogram import Client, filters
from info import INDEX_CHANNELS, INDEX_EXTENSIONS
from database.ia_filterdb import save_file
from database.users_chats_db import db as data_db # <-- ADD THIS IMPORT

media_filter = filters.document | filters.video


@Client.on_message(filters.chat(INDEX_CHANNELS) & media_filter)
async def media(bot, message):
    """Media Handler"""
    media = getattr(message, message.media.value, None)
    if (str(media.file_name).lower()).endswith(tuple(INDEX_EXTENSIONS)):
        media.caption = message.caption
        # --- OLD ---
        # await save_file(media)
        # --- NEW ---
        await save_file(media, data_db)