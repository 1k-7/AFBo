class script(object):

    START_TXT = """<b>ʜᴇʏ {}, <i>{}</i></b>

ɪ'ᴍ ᴀ ᴘᴏᴡᴇʀꜰᴜʟ ʙᴏᴛ ᴅᴇꜱɪɢɴᴇᴅ ᴛᴏ ᴘʀᴏᴠɪᴅᴇ ᴍᴏᴠɪᴇꜱ & ꜱᴇʀɪᴇꜱ.

<blockquote>ᴊᴏɪɴ: @norFederation ✨</blockquote></b>"""

    MY_ABOUT_TXT = """♢ ꜱᴇʀᴠᴇʀ: <a href=https://www.koyeb.com>ᴋᴏʏᴇʙ</a>
♢ ᴅᴀᴛᴀʙᴀꜱᴇ: <a href=https://www.mongodb.com>ᴍᴏɴɢᴏᴅʙ</a>
♢ ʟᴀɴɢᴜᴀɢᴇ: <a href=https://www.python.org>ᴘʏᴛʜᴏɴ</a>
♢ ʟɪʙʀᴀʀʏ: <a href=https://t.me/HydrogramNews>ʜʏᴅʀᴏɢʀᴀᴍ</a>"""

    MY_OWNER_TXT = """♢ ɴᴀᴍᴇ: ᴢᴀᴄʜ
♢ ᴜꜱᴇʀɴᴀᴍᴇ: @ActualHomie
♢ ᴄᴏᴜɴᴛʀʏ: 𝚜𝚘𝚖𝚎𝚠𝚑𝚎𝚛𝚎 𝚒𝚗 𝚛𝚎𝚊𝚕𝚒𝚝𝚢"""

    # Reworked STATUS_TXT for Multi-DB
    STATUS_TXT = """<blockquote>ʙᴏᴛ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ</blockquote>

<blockquote>╭─[ ᴜꜱᴇʀ ɪɴꜰᴏ ]───➣
│ 👤 ᴛᴏᴛᴀʟ ᴜꜱᴇʀꜱ: <code>{}</code>
│ 👥 ᴛᴏᴛᴀʟ ᴄʜᴀᴛꜱ: <code>{}</code>
╰──────────────➣</blockquote>
<blockquote>╭─[ ᴅᴀᴛᴀʙᴀꜱᴇ ꜱᴛᴀᴛꜱ ]────➣
│ 🗳️ ʙᴏᴛ ᴅᴀᴛᴀ ꜱɪᴢᴇ: <code>{}</code>
│ 💾 ᴛᴏᴛᴀʟ ꜰɪʟᴇꜱ (ᴀʟʟ ᴅʙꜱ): <code>{}</code>
│ ⚡ ᴀᴄᴛɪᴠᴇ ᴅʙ ɪɴᴅᴇx: <code>{}</code>
{}╰─────────────────────────➣</blockquote>
<blockquote> ⏳ ʙᴏᴛ ᴜᴘᴛɪᴍᴇ: <code>{}</code> </blockquote>
""" # Removed premium user count, added {} for dynamic DB stats

    NEW_GROUP_TXT = """#ɴᴇᴡ_ɢʀᴏᴜᴘ
♢ ᴛɪᴛʟᴇ: {}
♢ ɪᴅ: <code>{}</code>
♢ ᴜꜱᴇʀɴᴀᴍᴇ: {}
♢ ᴍᴇᴍʙᴇʀꜱ: code>{}</code>"""

    NEW_USER_TXT = """#ɴᴇᴡ_ᴜꜱᴇʀ
♢ ɴᴀᴍᴇ: {}
♢ ɪᴅ: <code>{}</code>"""

    NOT_FILE_TXT = """ ʜᴇʟʟᴏ {},

ɪ ᴄᴏᴜʟᴅɴ'ᴛ ꜰɪɴᴅ `<b>{}</b>` ɪɴ ᴍʏ ᴅᴀᴛᴀʙᴀꜱᴇ!

♢ ᴅᴏᴜʙʟᴇ-ᴄʜᴇᴄᴋ ᴛʜᴇ ꜱᴘᴇʟʟɪɴɢ.
♢ ᴛʀʏ ᴜꜱɪɴɢ ᴍᴏʀᴇ ꜱᴘᴇᴄɪꜰɪᴄ ᴋᴇʏᴡᴏʀᴅꜱ.
♢ ᴛʜᴇ ꜰɪʟᴇ ᴍɪɢʜᴛ ɴᴏᴛ ʙᴇ ʀᴇʟᴇᴀꜱᴇᴅ ᴏʀ ᴀᴅᴅᴇᴅ ʏᴇᴛ."""

    # Updated IMDB_TEMPLATE
    IMDB_TEMPLATE = """<blockquote>✨ ꜰᴏᴜɴᴅ: <code>{query}</code> </blockquote>

🎬 ᴛɪᴛʟᴇ: <a href={url}>{title}</a> {year_info}
🎭 ɢᴇɴʀᴇꜱ: {genres}
⭐ ʀᴀᴛɪɴɢ: <a href={url}/ratings>{rating} / 10</a> ({votes} ᴠᴏᴛᴇꜱ)
🌐 ʟᴀɴɢᴜᴀɢᴇꜱ: {languages}
⏰ ʀᴜɴᴛɪᴍᴇ: {runtime}

📝 ᴘʟᴏᴛ: {plot}

<blockquote>👤 ʀᴇǫᴜᴇꜱᴛᴇᴅ ʙʏ: {message.from_user.mention}
⚙️ ᴘᴏᴡᴇʀᴇᴅ ʙʏ: <b>𝚢𝚊 𝚑𝚘𝚖𝚒𝚎 </blockquote></b>"""

    FILE_CAPTION = """<i>{file_name}</i>""" # Kept simple

    WELCOME_TEXT = """ ʜᴇʟʟᴏ {mention}, ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ {title}! 🎉"""

    HELP_TXT = """ ʜᴇʟʟᴏ {},

ʜᴏᴡ ᴄᴀɴ ɪ ᴀꜱꜱɪꜱᴛ ʏᴏᴜ ᴛᴏᴅᴀʏ?
ʏᴏᴜ ᴄᴀɴ ꜱᴇᴀʀᴄʜ ꜰᴏʀ ꜰɪʟᴇꜱ ɪɴ ᴘᴍ ᴏʀ ɪɴ ᴀ ɢʀᴏᴜᴘ.

ᴄʜᴇᴄᴋ ᴏᴜᴛ ᴛʜᴇ ᴀᴠᴀɪʟᴀʙʟᴇ ᴄᴏᴍᴍᴀɴᴅꜱ ʙᴇʟᴏᴡ! 👇"""

    ADMIN_COMMAND_TXT = """<b>⚙️ ᴀᴅᴍɪɴ ᴄᴏᴍᴍᴀɴᴅꜱ:</b>

/index_channels ⤬ ᴄʜᴇᴄᴋ ɪɴᴅᴇхᴇᴅ ᴄʜᴀɴɴᴇʟꜱ
/stats ⤬ ɢᴇᴛ ʙᴏᴛ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ
/delete [ǫᴜᴇʀʏ] ⤬ ᴅᴇʟᴇᴛᴇ ꜰɪʟᴇꜱ
/delete_all ⤬ ᴅᴇʟᴇᴛᴇ ᴀʟʟ ɪɴᴅᴇхᴇᴅ ꜰɪʟᴇꜱ (⚠️)
/broadcast ⤬ ꜱᴇɴᴅ ᴍꜱɢ ᴛᴏ ᴜꜱᴇʀꜱ (ʀᴇᴘʟʏ)
/grp_broadcast ⤬ ꜱᴇɴᴅ ᴍꜱɢ ᴛᴏ ɢʀᴏᴜᴘꜱ (ʀᴇᴘʟʏ)
/pin_broadcast ⤬ ʙʀᴏᴀᴅᴄᴀꜱᴛ & ᴘɪɴ (ᴜꜱᴇʀꜱ)
/pin_grp_broadcast ⤬ ʙʀᴏᴀᴅᴄᴀꜱᴛ & ᴘɪɴ (ɢʀᴏᴜᴘꜱ)
/restart ⤬ ʀᴇꜱᴛᴀʀᴛ ʙᴏᴛ
/leave [ᴄʜᴀᴛ_ɪᴅ] ⤬ ʟᴇᴀᴠᴇ ᴀ ɢʀᴏᴜᴘ
/users ⤬ ʟɪꜱᴛ ᴀʟʟ ᴜꜱᴇʀꜱ
/chats ⤬ ʟɪꜱᴛ ᴀʟʟ ᴄʜᴀᴛꜱ
/invite_link [ᴄʜᴀᴛ_ɪᴅ] ⤬ ɢᴇɴ ɪɴᴠɪᴛᴇ ʟɪɴᴋ
/index ⤬ ꜱᴛᴀʀᴛ ɪɴᴅᴇхɪɴɢ
/delreq ⤬ ᴄʟᴇᴀʀ ᴊᴏɪɴ ʀᴇǫᴜᴇꜱᴛꜱ
/set_req_fsub [ᴄʜᴀɴɴᴇʟ_ɪᴅ] ⤬ ꜱᴇᴛ ᴊᴏɪɴ ʀᴇǫ ꜰꜱᴜʙ
/set_fsub [ɪᴅꜱ...] ⤬ ꜱᴇᴛ ɴᴏʀᴍᴀʟ ꜰꜱᴜʙ
/off_auto_filter ⤬ ᴅɪꜱᴀʙʟᴇ ᴀᴜᴛᴏ-ꜰɪʟᴛᴇʀ
/on_auto_filter ⤬ ᴇɴᴀʙʟᴇ ᴀᴜᴛᴏ-ꜰɪʟᴛᴇʀ
/off_pm_search ⤬ ᴅɪꜱᴀʙʟᴇ ᴘᴍ ꜱᴇᴀʀᴄʜ
/on_pm_search ⤬ ᴇɴᴀʙʟᴇ ᴘᴍ ꜱᴇᴀʀᴄʜ""" # Removed /cleanmultdb and /dbequal

    USER_COMMAND_TXT = """<b>✨ ᴜꜱᴇʀ ᴄᴏᴍᴍᴀɴᴅꜱ:</b>

/start ⤬ ᴄʜᴇᴄᴋ ʙᴏᴛ ꜱᴛᴀᴛᴜꜱ
/settings ⤬ ᴄʜᴀɴɢᴇ ɢʀᴏᴜᴘ ꜱᴇᴛᴛɪɴɢꜱ (ᴀᴅᴍɪɴꜱ)
/connect [ɢʀᴘ_ɪᴅ] ⤬ ʟɪɴᴋ ɢʀᴏᴜᴘ ᴛᴏ ᴘᴍ
/id ⤬ ɢᴇᴛ ᴄᴜʀʀᴇɴᴛ ᴄʜᴀᴛ/ᴜꜱᴇʀ ɪᴅ"""

    SOURCE_TXT = """<b> ꜱᴏᴜʀᴄᴇ ᴄᴏᴅᴇ:</b>

ᴛʜɪꜱ ɪꜱ ᴀɴ ᴏᴘᴇɴ-ꜱᴏᴜʀᴄᴇ ᴘʀᴏᴊᴇᴄᴛ.
ᴅᴇᴠᴇʟᴏᴘᴇʀ - @ActualHomie"""

    # Removed PLAN_TXT