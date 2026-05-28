from info import BIN_CHANNEL, URL
from utils import temp
from web.utils.custom_dl import TGCustomYield
import urllib.parse
import aiofiles, html


# styles from deepseek.com
watch_tmplt = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta property="og:image" content="https://i.ibb.co/M8S0Zzj/live-streaming.png" itemprop="thumbnailUrl">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{heading}</title>
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap">
    <link rel="stylesheet" href="https://cdn.plyr.io/3.7.8/plyr.css" />
    <style>
        :root {
            --primary: #818cf8;
            --primary-hover: #6366f1;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --bg-color: #0f172a;
            --player-bg: #1e293b;
            --footer-bg: #1e293b;
            --border-color: #334155;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }
        
        header {
            padding: 1rem;
            background-color: var(--player-bg);
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            position: sticky;
            top: 0;
            z-index: 10;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        
        #file-name {
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--text-primary);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 80%;
            text-align: center;
        }
        
        .container {
            flex: 1;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 2rem;
            width: 100%;
        }
        
        .player-container {
            width: 100%;
            max-width: 1200px;
            background-color: var(--player-bg);
            border-radius: 0.5rem;
            overflow: hidden;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        }
        
        .action-buttons {
            display: flex;
            justify-content: center;
            gap: 1rem;
            margin-top: 1rem;
            padding: 0 1rem;
        }
        
        .action-btn {
            background-color: var(--primary);
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 0.25rem;
            font-weight: 500;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            text-decoration: none;
            transition: background-color 0.2s;
        }
        
        .action-btn:hover {
            background-color: var(--primary-hover);
        }
        
        footer {
            padding: 1rem;
            text-align: center;
            background-color: var(--footer-bg);
            color: var(--text-secondary);
            font-size: 0.875rem;
            border-top: 1px solid var(--border-color);
        }
        
        @media (max-width: 768px) {
            #file-name {
                font-size: 0.9rem;
                max-width: 90%;
            }
            
            .container {
                padding: 1rem;
            }
            
            .action-buttons {
                flex-direction: column;
                gap: 0.5rem;
            }
        }
        
        /* Plyr overrides */
        .plyr--video .plyr__control--overlaid {
            background: var(--primary);
        }
        
        .plyr--video .plyr__control:hover, 
        .plyr--video .plyr__control[aria-expanded="true"] {
            background: var(--primary-hover);
        }
        
        .plyr__control.plyr__tab-focus {
            box-shadow: 0 0 0 5px rgba(99, 102, 241, 0.5);
        }
        
        .plyr--full-ui input[type="range"] {
            color: var(--primary);
        }
        
        .plyr__menu__container .plyr__control[role="menuitemradio"][aria-checked="true"]::before {
            background: var(--primary);
        }
    </style>
</head>
<body class="dark">
    <header>
        <div id="file-name">{file_name}</div>
    </header>

    <div class="container">
        <div class="player-container">
            <video src="{src}" class="player" playsinline controls></video>
            <div class="action-buttons">
                <a href="{src}" class="action-btn" download>
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                        <polyline points="7 10 12 15 17 10"></polyline>
                        <line x1="12" y1="15" x2="12" y2="3"></line>
                    </svg>
                    Download
                </a>
                <a href="vlc://{src}" class="action-btn">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polygon points="5 3 19 12 5 21 5 3"></polygon>
                    </svg>
                    Play in VLC
                </a>
            </div>
        </div>
    </div>

    <footer>
        <p>Video not playing? Your browser might not support the codec. Please try downloading the file or playing in VLC.</p>
    </footer>

    <script src="https://cdn.plyr.io/3.7.8/plyr.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            // Initialize Plyr player
            const player = new Plyr('.player', {
                controls: [
                    'play-large',
                    'play',
                    'progress',
                    'current-time',
                    'duration',
                    'mute',
                    'volume',
                    'captions',
                    'settings',
                    'pip',
                    'airplay',
                    'fullscreen'
                ],
                settings: ['captions', 'quality', 'speed'],
                hideControls: false
            });
        });
    </script>
</body>
</html>
"""

async def media_watch(message_id):
    media_msg = await temp.BOT.get_messages(BIN_CHANNEL, message_id)
    media = getattr(media_msg, media_msg.media.value, None)
    src = urllib.parse.urljoin(URL, f'download/{message_id}')
    tag = media.mime_type.split('/')[0].strip()
    if tag == 'video':
        heading = html.escape(f'Watch - {media.file_name}')
        html_ = watch_tmplt.replace('{heading}', heading).replace('{file_name}', media.file_name).replace('{src}', src)
    else:
        html_ = '<h1>This is not streamable file</h1>'
    return html_
