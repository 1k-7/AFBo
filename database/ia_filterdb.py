import logging
from struct import pack
import re
import base64
import asyncio
from functools import partial
from hydrogram.file_id import FileId
from hydrogram import enums
from pymongo import MongoClient, TEXT
from pymongo.errors import DuplicateKeyError, OperationFailure, BulkWriteError 
from info import (
    DATABASE_URIS, DATABASE_NAME, COLLECTION_NAME,
    USE_CAPTION_FILTER, MAX_BTN, DB_MAX_SIZE_MB
)

logger = logging.getLogger(__name__)

def get_size(size_bytes):
    if size_bytes is None or not isinstance(size_bytes, (int, float)) or size_bytes < 0: return "0 B"
    size = float(size_bytes); units = ["B", "KB", "MB", "GB", "TB", "PB", "EB"]; i = 0
    while size >= 1024.0 and i < len(units) - 1: i += 1; size /= 1024.0
    return "%.2f %s" % (size, units[i])

file_db_clients = []
file_db_collections = []
DB_MAX_SIZE_BYTES = DB_MAX_SIZE_MB * 1024 * 1024

try:
    uris = DATABASE_URIS.split()
    if not uris:
        raise ValueError("DATABASE_URIS environment variable is empty.")
        
    for i, uri in enumerate(uris):
        try:
            client = MongoClient(uri)
            db = client[DATABASE_NAME]
            collection = db[COLLECTION_NAME]
            
            try:
                collection.create_index([("file_name", TEXT)], background=True)
                collection.create_index([("file_name", 1), ("file_size", 1)], unique=True, background=True)
            except OperationFailure as e:
                if e.code == 8000:
                    logger.critical(f"Database #{i+1} is FULL! Couldn't create index: {e.details.get('errmsg', e)}")
                else:
                    logger.warning(f"Couldn't create index for Database #{i+1}: {e}")
            
            file_db_clients.append(client)
            file_db_collections.append(collection)
            logger.info(f"Connected to Files Database #{i+1}.")
            
        except Exception as e:
            logger.error(f"Failed to connect to Files Database #{i+1} (URI: {uri}): {e}")

    if not file_db_collections:
        logger.critical("No valid file database connections established. Exiting.")
        exit()

except Exception as e:
    logger.critical(f"Error processing DATABASE_URIS: {e}", exc_info=True)
    exit()

async def get_active_collection_with_index(data_db):
    loop = asyncio.get_running_loop()
    try:
        stg = await loop.run_in_executor(None, data_db.get_bot_sttgs)
        current_index = stg.get('CURRENT_DB_INDEX', 0)
        db_stats = await loop.run_in_executor(None, data_db.get_all_files_db_stats)
        
        if not db_stats or len(db_stats) != len(file_db_collections):
            logger.error("DB stats count mismatch or fetch error. Defaulting to first DB.")
            return file_db_collections[0], 0

        for i in range(current_index, len(file_db_collections)):
            coll = file_db_collections[i]
            stat = next((s for s in db_stats if s.get('coll_name') == coll.name and s.get('db_name') == coll.database.name), None)
            
            if stat and stat.get('size', 0) < DB_MAX_SIZE_BYTES:
                if i != current_index:
                    logger.info(f"DB #{current_index+1} is full. Switching active DB to #{i+1}.")
                    await loop.run_in_executor(None, data_db.update_bot_sttgs, 'CURRENT_DB_INDEX', i)
                return coll, i 

        if current_index > 0:
            for i in range(0, current_index):
                coll = file_db_collections[i]
                stat = next((s for s in db_stats if s.get('coll_name') == coll.name and s.get('db_name') == coll.database.name), None)
                
                if stat and stat.get('size', 0) < DB_MAX_SIZE_BYTES:
                    logger.info(f"All subsequent DBs full. Switching back to active DB #{i+1}.")
                    await loop.run_in_executor(None, data_db.update_bot_sttgs, 'CURRENT_DB_INDEX', i)
                    return coll, i

        logger.critical("All file databases are full!")
        return None, -1

    except Exception as e:
        logger.error(f"Error getting active collection: {e}", exc_info=True)
        return file_db_collections[0], 0 

def get_total_files_count():
     if not file_db_collections: return 0
     total_count = 0
     for collection in file_db_collections:
         try:
             total_count += collection.count_documents({})
         except Exception as e:
             logger.error(f"Error counting DB {collection.database.name}: {e}")
     return total_count

db_count_documents = get_total_files_count

async def save_file(media, data_db, replace=False):
    loop = asyncio.get_running_loop()
    
    active_coll, active_index = await get_active_collection_with_index(data_db)
    if active_coll is None:
        logger.critical("All databases are full. Cannot save file.")
        return 'err'

    db_name_log = f"Active DB #{active_index + 1}"
    file_id = media.file_id
    if not file_id: return 'err'

    raw_file_name = str(media.file_name) if media.file_name else "UnknownFile"
    file_name = raw_file_name.strip()
    file_name = re.sub(r"[@\(\)\[\]]", "", file_name)
    file_name = re.sub(r"(_|\-|\.|\+)+", " ", file_name)
    file_name = re.sub(r'\s+', ' ', file_name).strip()

    caption_text = str(media.caption) if media.caption is not None else ""
    file_caption = re.sub(r"@\w+|(_|\-|\.|\+)|https?://\S+", " ", caption_text).strip()
    file_caption = re.sub(r'\s+', ' ', file_caption)

    document = {
        '_id': file_id,
        'file_name': file_name,
        'file_size': media.file_size or 0,
        'caption': file_caption
    }

    if replace:
        try:
            delete_query = {'file_name': file_name, 'file_size': document['file_size']}
            del_tasks = [
                loop.run_in_executor(None, partial(coll.delete_one, delete_query))
                for coll in file_db_collections
            ]
            await asyncio.gather(*del_tasks)
        except Exception as e:
            logger.error(f"Error during replace deletion: {e}")

    if not replace:
        collections_to_check = [coll for i, coll in enumerate(file_db_collections) if i != active_index]
        if collections_to_check:
            try:
                query_filter = {
                    '$or': [
                        {'_id': document['_id']},
                        {'file_name': document['file_name'], 'file_size': document['file_size']}
                    ]
                }
                find_tasks = [
                    loop.run_in_executor(None, partial(coll.find_one, query_filter, {'_id': 1}))
                    for coll in collections_to_check
                ]
                duplicates = await asyncio.gather(*find_tasks)
                if any(duplicates):
                    return 'dup'
            except Exception as e:
                logger.error(f"Error checking other DBs for duplicates: {e}")
    
    try:
        await loop.run_in_executor(None, partial(active_coll.insert_one, document))
        logger.info(f'Saved [{get_size(document["file_size"])}] to {db_name_log}: {document["file_name"]}')
        return 'suc'
    except DuplicateKeyError:
        return 'dup'
    except OperationFailure as e:
         if e.code == 8000:
             logger.warning(f"{db_name_log} is FULL. File *not* saved. Active DB will switch on next save.")
             return 'err'
         else:
             logger.error(f"MongoDB Operation Failure on {db_name_log}: {e}")
             return 'err'
    except Exception as e:
        logger.error(f"Unexpected error saving file to {db_name_log}: {e}", exc_info=True)
        return 'err'

async def get_search_results(query, max_results=MAX_BTN, offset=0, lang=None):
    loop = asyncio.get_running_loop()
    query = str(query).strip()
    if not query: return [], '', 0

    words = [re.escape(word) for word in query.split()]
    raw_pattern = r'\b' + r'.*?\b'.join(words) + r'.*'
    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except re.error:
        simple_regex_pattern = r".*".join(words)
        regex = re.compile(simple_regex_pattern, flags=re.IGNORECASE)

    filter_query = {'file_name': regex}
    if USE_CAPTION_FILTER:
        filter_query = {'$or': [{'file_name': regex}, {'caption': regex}]}

    results = []; total_results = 0

    async def run_find(db_collection, q_filter):
        if db_collection is None: return [], 0
        try:
            cursor = db_collection.find(q_filter) 
            docs = await loop.run_in_executor(None, list, cursor)
            count = len(docs)
            return docs, count
        except Exception as e:
            logger.error(f"Database query error ({db_collection.database.name}): {e}"); return [], 0

    find_tasks = [run_find(collection, filter_query) for collection in file_db_collections]
    all_db_results = await asyncio.gather(*find_tasks)

    for docs, count in all_db_results:
        results.extend(docs)
        total_results += count

    if lang:
        lang = lang.lower()
        lang_files = [
            f for f in results
            if lang in f.get('file_name', '').lower() or lang in f.get('caption', '').lower()
        ]
        total_results = len(lang_files)
        files_to_return = lang_files[offset : offset + max_results]
    else:
        files_to_return = results[offset : offset + max_results]

    next_offset_val = offset + len(files_to_return)
    next_offset_str = str(next_offset_val) if next_offset_val < total_results else ''

    return files_to_return, next_offset_str, total_results

async def delete_files(query):
    loop = asyncio.get_running_loop(); total_deleted = 0
    query = str(query).strip()
    if not query: return 0

    words = [re.escape(word) for word in query.split()]
    raw_pattern = r'\b' + r'.*?\b'.join(words) + r'.*'
    try: regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except re.error: 
        simple_regex_pattern = r".*".join(words)
        regex = re.compile(simple_regex_pattern, flags=re.IGNORECASE)
        
    filter_query = {'file_name': regex}

    async def run_delete(db_collection, q_filter):
        if db_collection is None: return 0
        try:
            result = await loop.run_in_executor(None, partial(db_collection.delete_many, q_filter))
            return result.deleted_count if result else 0
        except Exception as e:
            logger.error(f"Error deleting from {db_collection.database.name}: {e}"); return 0

    delete_tasks = [run_delete(collection, filter_query) for collection in file_db_collections]
    deleted_counts = await asyncio.gather(*delete_tasks)
    total_deleted = sum(deleted_counts)

    logger.info(f"Deleted {total_deleted} files matching query: '{query}' from all DBs.")
    return total_deleted

async def get_file_details(query_id):
    loop = asyncio.get_running_loop()
    for collection in file_db_collections:
        file_details = None
        try:
            file_details = await loop.run_in_executor(None, partial(collection.find_one, {'_id': query_id}))
        except Exception as e:
            logger.error(f"Error find_one in {collection.database.name} ({query_id}): {e}")
        
        if file_details:
            return [file_details]
            
    return []