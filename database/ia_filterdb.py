import aiosqlite
import logging
import re
from info import DATABASE_FILE, USE_CAPTION_FILTER, MAX_BTN

logger = logging.getLogger(__name__)
_db_initialized = False

def get_size(size_bytes):
    if size_bytes is None or not isinstance(size_bytes, (int, float)) or size_bytes < 0: return "0 B"
    size = float(size_bytes); units = ["B", "KB", "MB", "GB", "TB", "PB", "EB"]; i = 0
    while size >= 1024.0 and i < len(units) - 1: i += 1; size /= 1024.0
    return "%.2f %s" % (size, units[i])

async def _init_db():
    global _db_initialized
    if _db_initialized: return
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS files (
                file_id TEXT PRIMARY KEY,
                file_name TEXT,
                file_size INTEGER,
                caption TEXT
            )
        ''')
        await db.execute('CREATE INDEX IF NOT EXISTS idx_file_name ON files(file_name)')
        await db.commit()
    _db_initialized = True

async def get_total_files_count():
    await _init_db()
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute('SELECT COUNT(*) FROM files') as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def save_file(media, replace=False):
    await _init_db()
    file_id = media.file_id
    if not file_id: return 'err'

    raw_file_name = str(media.file_name) if getattr(media, 'file_name', None) else "UnknownFile"
    file_name = re.sub(r"[@\(\)\[\]]", "", raw_file_name.strip())
    file_name = re.sub(r"(_|\-|\.|\+)+", " ", file_name)
    file_name = re.sub(r'\s+', ' ', file_name).strip()

    caption_text = str(media.caption) if getattr(media, 'caption', None) else ""
    file_caption = re.sub(r"@\w+|(_|\-|\.|\+)|https?://\S+", " ", caption_text).strip()
    file_caption = re.sub(r'\s+', ' ', file_caption)

    file_size = getattr(media, 'file_size', 0) or 0

    async with aiosqlite.connect(DATABASE_FILE) as db:
        if replace:
            await db.execute('DELETE FROM files WHERE file_name = ? AND file_size = ?', (file_name, file_size))
        else:
            async with db.execute('SELECT 1 FROM files WHERE file_name = ? AND file_size = ?', (file_name, file_size)) as cursor:
                if await cursor.fetchone():
                    return 'dup'
        try:
            await db.execute('INSERT INTO files (file_id, file_name, file_size, caption) VALUES (?, ?, ?, ?)', (file_id, file_name, file_size, file_caption))
            await db.commit()
            return 'suc'
        except aiosqlite.IntegrityError:
            return 'dup'
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            return 'err'

async def get_search_results(query, max_results=MAX_BTN, offset=0):
    await _init_db()
    query = str(query).strip()
    if not query: return [], '', 0

    words = query.split()
    like_query = '%' + '%'.join(words) + '%'
    
    async with aiosqlite.connect(DATABASE_FILE) as db:
        db.row_factory = aiosqlite.Row
        if USE_CAPTION_FILTER:
            sql = 'SELECT * FROM files WHERE file_name LIKE ? OR caption LIKE ?'
            params = (like_query, like_query)
        else:
            sql = 'SELECT * FROM files WHERE file_name LIKE ?'
            params = (like_query,)

        count_sql = sql.replace('SELECT *', 'SELECT COUNT(*)')
        async with db.execute(count_sql, params) as cursor:
            total_results = (await cursor.fetchone())[0]

        sql += ' LIMIT ? OFFSET ?'
        params += (max_results, offset)
        
        async with db.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            results = [dict(row) for row in rows]
            for r in results:
                r['_id'] = r['file_id']

    next_offset_val = offset + len(results)
    next_offset_str = str(next_offset_val) if next_offset_val < total_results else ''

    return results, next_offset_str, total_results

async def delete_files(query):
    await _init_db()
    query = str(query).strip()
    if not query: return 0
    words = query.split()
    like_query = '%' + '%'.join(words) + '%'
    
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute('DELETE FROM files WHERE file_name LIKE ?', (like_query,)) as cursor:
            deleted_count = cursor.rowcount
        await db.commit()
        return deleted_count

async def get_file_details(query_id):
    await _init_db()
    async with aiosqlite.connect(DATABASE_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM files WHERE file_id = ?', (query_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                res = dict(row)
                res['_id'] = res['file_id']
                return [res]
    return []