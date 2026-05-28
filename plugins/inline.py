from hydrogram import Client
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultCachedDocument, InlineQuery
from database.ia_filterdb import get_search_results
from utils import get_size, temp, is_subscribed 
from info import CACHE_TIME, SUPPORT_LINK, UPDATES_LINK
import logging

logger = logging.getLogger(__name__)

def is_banned(query: InlineQuery):
    return query.from_user and query.from_user.id in temp.BANNED_USERS

@Client.on_inline_query()
async def inline_search(bot, query: InlineQuery):
    if is_banned(query): return await query.answer(results=[], cache_time=0, switch_pm_text="🚫 You're banned!", switch_pm_parameter="start")
    
    results = []
    string = query.query.strip()
    if len(string) < 2: return await query.answer(results=[], cache_time=CACHE_TIME, switch_pm_text="➡️ Type at least 2 characters...", switch_pm_parameter="start")

    offset = int(query.offset) if query.offset else 0

    try:
        files, next_offset, total = await get_search_results(string, offset=offset)
    except Exception as e:
        logger.error(f"Inline search error: {e}")
        return await query.answer(results=[], cache_time=5, switch_pm_text="❌ Error searching.", switch_pm_parameter="start")

    if files:
        for file in files:
            try:
                results.append(
                    InlineQueryResultCachedDocument(
                        title=file.get('file_name', 'N/A')[:60],
                        document_file_id=file['_id'],
                        caption=f"<b>{file.get('file_name', 'N/A')}</b>\nSize: <code>{get_size(file.get('file_size', 0))}</code>",
                        description=f"Size: {get_size(file.get('file_size', 0))}",
                        reply_markup=get_reply_markup(string)
                    )
                )
            except Exception as e: pass

    if results:
        switch_text = f"✔️ {total} Results for: {string}" if string else f"✔️ {total} Results"
        await query.answer(results=results, cache_time=CACHE_TIME, switch_pm_text=switch_text[:64], switch_pm_parameter="start", next_offset=str(next_offset) if next_offset else None)
    else:
        await query.answer(results=[], cache_time=CACHE_TIME, switch_pm_text="🚫 No results", switch_pm_parameter="start")

def get_reply_markup(s):
    buttons = [[ InlineKeyboardButton('🔄 Search Again', switch_inline_query_current_chat=s or '') ],
               [ InlineKeyboardButton('Updates', url=UPDATES_LINK), InlineKeyboardButton('Support', url=SUPPORT_LINK) ]]
    return InlineKeyboardMarkup(buttons)