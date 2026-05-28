from hydrogram import Client
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultCachedDocument, InlineQuery
from database.ia_filterdb import get_search_results
# Removed is_premium import
from utils import get_size, temp, get_verify_status, is_subscribed # Removed is_premium
from info import CACHE_TIME, SUPPORT_LINK, UPDATES_LINK, FILE_CAPTION, IS_VERIFY, PROTECT_CONTENT # Added PROTECT_CONTENT
import logging
from datetime import datetime # Import datetime
import pytz # Import pytz


logger = logging.getLogger(__name__)
cache_time = CACHE_TIME # Use cache time from info

def is_banned(query: InlineQuery):
    # Check if user ID exists in the banned list
    return query.from_user and query.from_user.id in temp.BANNED_USERS

@Client.on_inline_query()
async def inline_search(bot, query: InlineQuery):
    """Show search results for given inline query"""

    user_id = query.from_user.id if query.from_user else 0

    # Fsub Check
    is_fsub = await is_subscribed(bot, query) # Pass the query object
    if is_fsub:
        await query.answer(results=[], cache_time=0,
                           switch_pm_text="⚠️ ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ(ꜱ) ꜰɪʀꜱᴛ!", # Font applied
                           switch_pm_parameter="inline_fsub")
        return

    # Verify Check
    verify_status = await get_verify_status(user_id)
    # Check expiry if verified
    is_expired = isinstance(verify_status.get('expire_time'), datetime) and datetime.now(pytz.utc) > verify_status['expire_time'].replace(tzinfo=pytz.utc)

    if IS_VERIFY and (not verify_status.get('is_verified') or is_expired):
        if is_expired: await update_verify_status(user_id, is_verified=False) # Mark expired
        await query.answer(results=[], cache_time=0,
                           switch_pm_text="🔐 ʏᴏᴜ ɴᴇᴇᴅ ᴛᴏ ᴠᴇʀɪꜰʏ!", # Font applied
                           switch_pm_parameter="inline_verify")
        return

    # Banned Check
    if is_banned(query):
        await query.answer(results=[], cache_time=0,
                           switch_pm_text="🚫 ʏᴏᴜ'ʀᴇ ʙᴀɴɴᴇᴅ!", # Font applied
                           switch_pm_parameter="start")
        return

    results = []
    string = query.query.strip()
    # Minimum query length check
    if len(string) < 2:
         await query.answer(results=[], cache_time=cache_time,
                            switch_pm_text="➡️ ᴛʏᴘᴇ ᴀᴛ ʟᴇᴀꜱᴛ ₂ ᴄʜᴀʀᴀᴄᴛᴇʀꜱ...", # Font applied
                            switch_pm_parameter="start")
         return

    offset = int(query.offset) if query.offset else 0

    # Fetch search results
    try:
        # Use async get_search_results
        files, next_offset, total = await get_search_results(string, offset=offset)
    except Exception as e:
        logger.error(f"Inline search error for '{string}': {e}", exc_info=True)
        await query.answer(results=[], cache_time=5,
                           switch_pm_text="❌ ᴇʀʀᴏʀ ꜱᴇᴀʀᴄʜɪɴɢ.", # Font applied
                           switch_pm_parameter="start")
        return

    # Process results
    if files:
        for file in files:
            caption_text = file.get('caption', '')
            try:
                 # Use FILE_CAPTION from info/Script (Assume font is handled there if needed)
                 f_caption = FILE_CAPTION.format(
                     file_name=file.get('file_name', 'N/A'),
                     file_size=get_size(file.get('file_size', 0)),
                     caption=caption_text if caption_text else ""
                 )
            except Exception as e:
                 logger.error(f"Inline caption format error: {e}"); f_caption = file.get('file_name', 'N/A')

            try:
                results.append(
                    InlineQueryResultCachedDocument(
                        # Title and Description often have limited font support in clients
                        title=file.get('file_name', 'N/A')[:60], # Limit title length
                        document_file_id=file['_id'],
                        caption=f_caption[:1024], # Limit caption
                        description=f"ꜱɪᴢᴇ: {get_size(file.get('file_size', 0))}", # Font partially applied
                        # Button text should generally avoid complex fonts
                        reply_markup=get_reply_markup(string)
                    )
                )
            except Exception as e:
                 logger.error(f"Error creating InlineQueryResult for {file.get('_id', 'N/A')}: {e}")

    # Answer the query
    if results:
        switch_pm_text = f"✔️ {total} ꜰᴏʀ: {string}" if string else f"✔️ {total} ʀᴇꜱᴜʟᴛꜱ" # Font applied
        try:
            await query.answer(
                results=results,
                cache_time=cache_time,
                switch_pm_text=switch_pm_text[:64], # PM text limit
                switch_pm_parameter="start",
                next_offset=str(next_offset) if next_offset else None
            )
        except Exception as e:
             logger.error(f"Error answering inline query '{string}': {e}", exc_info=True)
             try: # Fallback error answer
                  await query.answer(results=[], cache_time=5, switch_pm_text="❌ ᴇʀʀᴏʀ.", switch_pm_parameter="start") # Font applied
             except: pass
    else:
        switch_pm_text = f"🚫 ɴᴏ ʀᴇꜱᴜʟᴛꜱ ꜰᴏʀ: {string}" if string else "🚫 ɴᴏ ʀᴇꜱᴜʟᴛꜱ" # Font applied
        await query.answer(
            results=[],
            cache_time=cache_time,
            switch_pm_text=switch_pm_text[:64],
            switch_pm_parameter="start"
        )


def get_reply_markup(s):
    # Button text: Use font cautiously due to length limits
    buttons = [[ InlineKeyboardButton('🔄 ꜱᴇᴀʀᴄʜ ᴀɢᴀɪɴ', switch_inline_query_current_chat=s or '') ],
               [ InlineKeyboardButton('• ᴜᴘᴅᴀᴛᴇꜱ •', url=UPDATES_LINK),
                 InlineKeyboardButton('• ꜱᴜᴘᴘᴏʀᴛ •', url=SUPPORT_LINK) ]]
    return InlineKeyboardMarkup(buttons)

