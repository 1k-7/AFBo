class script(object):

    START_TXT = """<b>ʜᴇʟʟᴏ {},</b>\n\nI am an advanced file indexing and retrieval bot.\nSend me a query to search my database."""

    STATUS_TXT = """<b>📊 Database & Bot Status</b>\n\n<b>Users:</b> <code>{}</code>\n<b>Chats:</b> <code>{}</code>\n<b>Total Files:</b> <code>{}</code>\n<b>Uptime:</b> <code>{}</code>"""

    NEW_GROUP_TXT = """#NEW_GROUP\n<b>Title:</b> {}\n<b>ID:</b> <code>{}</code>\n<b>Members:</b> <code>{}</code>"""

    NEW_USER_TXT = """#NEW_USER\n<b>Name:</b> {}\n<b>ID:</b> <code>{}</code>"""

    NOT_FILE_TXT = """<b>No results found for</b>: <code>{}</code>\n\nPlease check your spelling or try broader keywords."""

    FILE_CAPTION = """<b>{file_name}</b>\nSize: <code>{file_size}</code>""" 

    HELP_TXT = """<b>Help Menu</b>\n\nYou can search for files here in PM or add me to a group.\n\nUse inline search via <code>@BotUsername query</code>."""

    ADMIN_COMMAND_TXT = """<b>Admin Commands:</b>
/index - Index a channel (forward msg or send link)
/2nd [token] - Add secondary bot for indexing logs
/index_channels - Check indexed channels
/stats - Bot stats
/delete [query] - Delete specific files
/export - Export Database to JSON
/import - Reply to JSON to Import DB
/users - List users
/chats - List groups
/set_fsub [ids] - Set force sub channels"""