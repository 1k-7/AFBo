class script(object):

    START_TXT = """<b>ʜᴇʟʟᴏ {},</b>

I am an advanced file indexing and retrieval bot.
Send me a query to search my database."""

    STATUS_TXT = """<b>📊 Database & Bot Status</b>

<b>Users:</b> <code>{}</code>
<b>Chats:</b> <code>{}</code>
<b>Total Files:</b> <code>{}</code>
<b>Uptime:</b> <code>{}</code>

<b>Storage Used:</b> <code>{}</code>
<b>Active Database:</b> DB #<code>{}</code>
{}"""

    NEW_GROUP_TXT = """#NEW_GROUP
<b>Title:</b> {}
<b>ID:</b> <code>{}</code>
<b>Members:</b> <code>{}</code>"""

    NEW_USER_TXT = """#NEW_USER
<b>Name:</b> {}
<b>ID:</b> <code>{}</code>"""

    NOT_FILE_TXT = """<b>No results found for</b>: <code>{}</code>

Please check your spelling or try broader keywords."""

    FILE_CAPTION = """<b>{file_name}</b>\nSize: <code>{file_size}</code>""" 

    WELCOME_TEXT = """Welcome to {title}, {mention}!"""

    HELP_TXT = """<b>Help Menu</b>

You can search for files here in PM or add me to a group.

Use inline search via <code>@BotUsername query</code>."""

    ADMIN_COMMAND_TXT = """<b>Admin Commands:</b>
/index - Index a channel
/index_channels - Check indexed channels
/stats - Bot stats
/delete [query] - Delete specific files
/users - List users
/chats - List groups
/export [db_num] - Export DB to JSON
/import [db_num] - Import JSON to DB"""