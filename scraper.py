#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     TELEGRAM USER SCRAPER CLI TOOL                          ║
║                        Created by Benjamin White                             ║
║                            Professional Edition                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# ═══════════════════════════════════════════════════════════════════════════════
#                           ⚙️ CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

API_ID         = 21085700
API_HASH       = '8654516355b40ce46ce93f821cfaf6d8'
DB_PATH        = 'sessions.db'
OUTPUT_FILE    = 'users.txt'

# ═══════════════════════════════════════════════════════════════════════════════
#                              📦 IMPORTS & SETUP
# ═══════════════════════════════════════════════════════════════════════════════

import os
import asyncio
import sqlite3
import logging
import gc
import sys
import signal
import re
import threading
from contextlib import asynccontextmanager, contextmanager
import psutil
from datetime import datetime
import platform
import warnings
from getpass import getpass

# سرکوب تمام warnings برای جلوگیری از segfault
warnings.filterwarnings("ignore")
os.environ['PYTHONWARNINGS'] = 'ignore'

# تنظیم signal handler برای جلوگیری از segmentation fault
def signal_handler(signum, frame):
    try:
        print("\n🛑 Signal received - Safe shutdown...")
        os._exit(0)
    except:
        os._exit(1)

signal.signal(signal.SIGSEGV, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# جایگزینی event loop پیش‌فرض با uvloop برای I/O سریع‌تر
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

# اگر tgcrypto نصب باشد، Telethon خودکار از آن استفاده می‌کند
try:
    import tgcrypto
except ImportError:
    pass

from telethon import TelegramClient
from telethon.sync import TelegramClient as SyncTelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    PeerFloodError, FloodWaitError, ChatAdminRequiredError,
    ChatWriteForbiddenError, ForbiddenError, UserKickedError,
    ChannelPrivateError, InviteHashExpiredError, InviteHashInvalidError,
    SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError
)
from telethon.tl.functions.channels import JoinChannelRequest, GetParticipantsRequest
from telethon.tl.functions.messages import ImportChatInviteRequest, GetHistoryRequest
from telethon.tl.types import ChannelParticipantsSearch, ChannelParticipantsAdmins

# ===== ENHANCED LOGGING SYSTEM =====
class ColoredFormatter(logging.Formatter):
    """Colorful and stylish log formatter"""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m',       # Reset
        'BOLD': '\033[1m',        # Bold
        'DIM': '\033[2m',         # Dim
    }
    
    EMOJIS = {
        'DEBUG': '🔍',
        'INFO': '✅',
        'WARNING': '⚠️',
        'ERROR': '❌',
        'CRITICAL': '🚨',
    }
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        emoji = self.EMOJIS.get(record.levelname, '📝')
        reset = self.COLORS['RESET']
        bold = self.COLORS['BOLD']
        
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        if record.levelname == 'INFO':
            formatted = f"{color}{bold}[{timestamp}]{reset} {emoji} {color}{record.getMessage()}{reset}"
        elif record.levelname == 'WARNING':
            formatted = f"{color}{bold}[{timestamp}]{reset} {emoji} {color}⚡ {record.getMessage()}{reset}"
        elif record.levelname == 'ERROR':
            formatted = f"{color}{bold}[{timestamp}]{reset} {emoji} {color}💥 {record.getMessage()}{reset}"
        elif record.levelname == 'CRITICAL':
            formatted = f"{color}{bold}[{timestamp}]{reset} {emoji} {color}🔥 CRITICAL: {record.getMessage()}{reset}"
        else:
            formatted = f"{record.getMessage()}"
        
        return formatted

# Setup enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

for handler in logging.root.handlers:
    handler.setFormatter(ColoredFormatter())

# خاموش کردن کامل لاگ‌های مزاحم Telethon
telethon_loggers = [
    'telethon', 'telethon.client', 'telethon.network', 'telethon.sessions',
    'telethon.network.connection', 'telethon.network.mtprotosender',
    'telethon.crypto', 'telethon.extensions', 'asyncio', 'urllib3'
]

for logger_name in telethon_loggers:
    telethon_logger = logging.getLogger(logger_name)
    telethon_logger.setLevel(logging.CRITICAL + 10)
    telethon_logger.disabled = True

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
#                           🧠 MEMORY MANAGEMENT & DATABASE
# ═══════════════════════════════════════════════════════════════════════════════

gc.set_threshold(100, 3, 3)
gc.enable()

db_lock = threading.Lock()

def init_db(path):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=OFF')
    conn.execute('PRAGMA cache_size=1000')
    conn.execute('PRAGMA temp_store=MEMORY')
    conn.execute('PRAGMA mmap_size=67108864')
    conn.execute('PRAGMA optimize')
    conn.execute('''
    CREATE TABLE IF NOT EXISTS sessions (
        phone TEXT PRIMARY KEY,
        session_str TEXT,
        status TEXT,
        last_error TEXT
    )
    ''')
    conn.commit()
    return conn

@contextmanager
def get_db_connection_sync():
    with db_lock:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=OFF')
        try:
            yield conn
        finally:
            conn.close()

@asynccontextmanager
async def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=OFF')
    try:
        yield conn
    finally:
        conn.close()

conn = init_db(DB_PATH)

# ═══════════════════════════════════════════════════════════════════════════════
#                              🎨 UI FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_banner():
    """Display the main application banner"""
    banner = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║  ████████╗███████╗██╗     ███████╗ ██████╗ ██████╗  █████╗ ███╗   ███╗       ║
║  ╚══██╔══╝██╔════╝██║     ██╔════╝██╔════╝ ██╔══██╗██╔══██╗████╗ ████║       ║
║     ██║   █████╗  ██║     █████╗  ██║  ███╗██████╔╝███████║██╔████╔██║       ║
║     ██║   ██╔══╝  ██║     ██╔══╝  ██║   ██║██╔══██╗██╔══██║██║╚██╔╝██║       ║
║     ██║   ███████╗███████╗███████╗╚██████╔╝██║  ██║██║  ██║██║ ╚═╝ ██║       ║
║     ╚═╝   ╚══════╝╚══════╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝       ║
║                                                                              ║
║                        🚀 USER SCRAPER CLI TOOL 🚀                           ║
║                                                                              ║
║                        Created by Benjamin White                             ║
║                            Professional Edition                              ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
    print(banner)

def print_main_menu():
    """Display the main menu options"""
    menu = """
┌─────────────────────────────────────────────────────────────────────────────┐
│                               🎯 MAIN MENU                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  [1] 📱 Connect Session    - Add Telegram sessions to the database          │
│                                                                             │
│  [2] 🔍 Start Scraper      - Scrape users from groups/channels              │
│                                                                             │
│  [3] 📋 Credits & License  - View credits and license information           │
│                                                                             │
│  [4] 🚪 Exit               - Close the application                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
"""
    print(menu)

def print_credits():
    """Display credits and license information"""
    credits = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║                          📋 CREDITS & LICENSE                               ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  🎨 CREATED BY: Benjamin White                                               ║
║                                                                              ║
║  📅 VERSION: Professional Edition v1.0                                      ║
║                                                                              ║
║  🌟 FEATURES:                                                                ║
║     • Advanced Telegram user scraping                                       ║
║     • Complete message history analysis                                     ║
║     • Smart admin filtering                                                 ║
║     • Memory-optimized for low-resource servers                             ║
║     • Professional CLI interface                                            ║
║                                                                              ║
║  📜 LICENSE:                                                                 ║
║                                                                              ║
║     This software is provided "as is" for educational and research          ║
║     purposes only. The creator, Benjamin White, retains all rights          ║
║     to this code and its associated documentation.                          ║
║                                                                              ║
║     🔒 TERMS OF USE:                                                         ║
║     • Use responsibly and in compliance with Telegram's Terms of Service    ║
║     • Do not use for spam, harassment, or malicious purposes                ║
║     • Respect user privacy and data protection laws                         ║
║     • Commercial use requires explicit permission from Benjamin White       ║
║                                                                              ║
║     ⚖️  DISCLAIMER:                                                          ║
║     The creator is not responsible for any misuse of this software.         ║
║     Users are solely responsible for their actions and compliance           ║
║     with applicable laws and regulations.                                   ║
║                                                                              ║
║  💫 ACKNOWLEDGMENTS:                                                         ║
║     • Telethon library developers                                           ║
║     • Python community                                                      ║
║     • Open source contributors worldwide                                    ║
║                                                                              ║
║                    🌟 Thank you for using this tool! 🌟                     ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
    print(credits)

def get_user_input(prompt, valid_options=None):
    """Get user input with validation"""
    while True:
        try:
            user_input = input(f"\n{prompt}").strip()
            if valid_options and user_input not in valid_options:
                print(f"❌ Invalid option. Please choose from: {', '.join(valid_options)}")
                continue
            return user_input
        except KeyboardInterrupt:
            print("\n🛑 Operation cancelled by user")
            return None

# ═══════════════════════════════════════════════════════════════════════════════
#                           📱 SESSION MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

def update_session(phone, session_str, status, error=None):
    """Update session in database"""
    with get_db_connection_sync() as conn:
        conn.execute(
            '''INSERT INTO sessions(phone, session_str, status, last_error)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(phone) DO UPDATE SET
                 session_str=excluded.session_str,
                 status=excluded.status,
                 last_error=excluded.last_error''',
            (phone, session_str, status, error)
        )
        conn.commit()

def connect_phone(phone: str):
    """Connect a phone number and create session"""
    client = SyncTelegramClient(
        StringSession(), 
        API_ID, API_HASH,
        connection_retries=2,
        retry_delay=1,
        timeout=15,
        request_retries=1,
        entity_cache_limit=0,
        auto_reconnect=False
    )
    
    try:
        client.connect()
        
        # مرحله اول: SMS Code
        if not client.is_user_authorized():
            logger.info(f"📨 Sending SMS code to {phone}...")
            client.send_code_request(phone)
            logger.info("✅ SMS code sent! Check your phone.")
            
            for attempt in range(1, 4):
                code = input(f"📱 Enter SMS code for {phone} (attempt {attempt}/3): ")
                try:
                    client.sign_in(phone, code)
                    logger.info(f"✅ SMS code verified for {phone}")
                    break
                except PhoneCodeInvalidError:
                    if attempt < 3:
                        logger.error(f"❌ Invalid code (attempt {attempt}/3), please try again.")
                    else:
                        logger.error("❌ Invalid code after 3 attempts, skipping.")
                except PhoneCodeExpiredError:
                    logger.error("⏰ Code expired, please request again.")
                    client.disconnect()
                    return None, False, 'Code expired'
                except SessionPasswordNeededError:
                    logger.info("🔐 2FA detected, moving to password verification...")
                    break

        # مرحله دوم: پسورد 2FA
        if not client.is_user_authorized():
            for attempt in range(1, 4):
                pw = getpass(f"🔐 Enter 2FA password for {phone} (attempt {attempt}/3): ")
                try:
                    client.sign_in(password=pw)
                    logger.info(f"🎉 2FA password correct for {phone}!")
                    break
                except SessionPasswordNeededError:
                    if attempt < 3:
                        logger.error(f"❌ Wrong password (attempt {attempt}/3), please try again.")
                        continue
                    else:
                        logger.error("❌ Wrong password after 3 attempts, giving up.")
                        client.disconnect()
                        return None, False, '2FA failed after 3 attempts'
                except Exception as e:
                    logger.error(f"🔧 2FA error: {e}")
                    if attempt == 3:
                        client.disconnect()
                        return None, False, f'2FA failed: {e}'
                    continue

        if not client.is_user_authorized():
            client.disconnect()
            return None, False, 'Authorization failed'

        session_str = client.session.save()
        client.disconnect()
        return session_str, True, None

    except ForbiddenError as e:
        client.disconnect()
        return None, False, f"Access forbidden: {e}"
    except Exception as e:
        client.disconnect()
        return None, False, str(e)

def connect_session_menu():
    """Handle the connect session menu"""
    print("\n" + "="*80)
    print("📱 CONNECT TELEGRAM SESSIONS")
    print("="*80)
    print("💡 This will add Telegram sessions to your database for scraping.")
    print("💡 You can add multiple sessions for better performance.")
    print("💡 Each session requires SMS verification and 2FA (if enabled).")
    
    while True:
        phone = get_user_input("📞 Enter phone number (with country code, e.g., +1234567890): ")
        if phone is None:  # User cancelled
            return
        
        if not phone:
            print("❌ Phone number cannot be empty!")
            continue
        
        logger.info(f"🔗 Connecting to {phone}...")
        session_str, success, error = connect_phone(phone)
        status = 'active' if success else 'error'
        update_session(phone, session_str or '', status, error)
        
        if success:
            logger.info(f"🎉 Session for {phone} created successfully!")
        else:
            logger.error(f"💥 Failed for {phone}: {error}")
        
        # Ask if user wants to add another session
        add_another = get_user_input("Do you want to add another session? (y/n): ", ['y', 'n', 'Y', 'N'])
        if add_another is None or add_another.lower() == 'n':
            break

# ═══════════════════════════════════════════════════════════════════════════════
#                           🔍 SCRAPING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

async def fetch_first_session():
    """Get the first available session from database"""
    async with get_db_connection() as conn:
        result = conn.execute(
            "SELECT phone, session_str FROM sessions WHERE status='active' AND session_str<>'' LIMIT 1"
        ).fetchone()
        return result

def parse_group_input(group_input):
    """Parse different types of group input (ID, username, invite link)"""
    group_input = group_input.strip()
    
    if group_input.lstrip('-').isdigit():
        return int(group_input), 'id'
    
    if 'joinchat/' in group_input or 't.me/+' in group_input:
        if 'joinchat/' in group_input:
            hash_part = group_input.split('joinchat/')[-1]
        else:
            hash_part = group_input.split('t.me/+')[-1]
        hash_part = hash_part.split('?')[0].split('&')[0]
        return hash_part, 'invite'
    
    if group_input.startswith('@'):
        return group_input[1:], 'username'
    elif 't.me/' in group_input and 'joinchat/' not in group_input and 't.me/+' not in group_input:
        username = group_input.split('t.me/')[-1]
        username = username.split('?')[0].split('/')[0]
        return username, 'username'
    else:
        return group_input, 'username'

async def join_group_if_needed(client, group_identifier, input_type):
    """Join group if not already joined"""
    try:
        if input_type == 'invite':
            logger.info(f"🔗 Joining group via invite link...")
            result = await client(ImportChatInviteRequest(group_identifier))
            return result.chats[0]
        
        elif input_type == 'username':
            logger.info(f"🔗 Joining group @{group_identifier}...")
            entity = await client.get_entity(group_identifier)
            try:
                await client(JoinChannelRequest(entity))
                logger.info(f"✅ Successfully joined @{group_identifier}")
            except Exception as e:
                if "already" in str(e).lower():
                    logger.info(f"ℹ️ Already a member of @{group_identifier}")
                else:
                    logger.warning(f"⚠️ Join attempt: {str(e)[:50]}")
            return entity
        
        else:  # input_type == 'id'
            entity = await client.get_entity(group_identifier)
            try:
                await client(JoinChannelRequest(entity))
                logger.info(f"✅ Successfully joined group {group_identifier}")
            except Exception as e:
                if "already" in str(e).lower():
                    logger.info(f"ℹ️ Already a member of group {group_identifier}")
                else:
                    logger.warning(f"⚠️ Join attempt: {str(e)[:50]}")
            return entity
            
    except Exception as e:
        error_msg = str(e)
        if "INVITE_HASH_EXPIRED" in error_msg:
            logger.error("❌ Invite link has expired")
        elif "INVITE_HASH_INVALID" in error_msg:
            logger.error("❌ Invalid invite link")
        elif "CHANNEL_PRIVATE" in error_msg:
            logger.error("❌ Group is private and requires invitation")
        else:
            logger.error(f"❌ Failed to join group: {error_msg[:100]}")
        raise

async def get_group_admins(client, group_entity):
    """Get list of admin user IDs"""
    admin_ids = set()
    try:
        admins = await client(GetParticipantsRequest(
            group_entity,
            ChannelParticipantsAdmins(),
            0,
            100,
            hash=0
        ))
        
        for admin in admins.users:
            if admin and not admin.deleted:
                admin_ids.add(admin.id)
        
        logger.info(f"👑 Found {len(admin_ids)} admins to exclude")
        return admin_ids
        
    except Exception as e:
        logger.warning(f"⚠️ Could not get admins: {str(e)[:50]}")
        return set()





async def scrape_group_users(client, group_entity):
    """Scrape users from the group by scanning entire chat history"""
    logger.info(f"🔍 Starting to scrape users from: {group_entity.title}")
    
    users_with_chat = set()
    admin_ids = await get_group_admins(client, group_entity)
    
    try:
        full_group = await client.get_entity(group_entity)
        logger.info(f"📊 Group: {full_group.title}")
        logger.info(f"🕐 Scanning entire message history for active users...")
        
        offset_id = 0
        limit = 100
        total_messages = 0
        processed_messages = 0
        
        while True:
            try:
                history = await client(GetHistoryRequest(
                    peer=group_entity,
                    offset_id=offset_id,
                    offset_date=None,
                    add_offset=0,
                    limit=limit,
                    max_id=0,
                    min_id=0,
                    hash=0
                ))
                
                if not history.messages:
                    break
                
                total_messages += len(history.messages)
                
                for message in history.messages:
                    processed_messages += 1
                    
                    if not hasattr(message, 'from_id') or not message.from_id:
                        continue
                    
                    user_id = None
                    if hasattr(message.from_id, 'user_id'):
                        user_id = message.from_id.user_id
                    elif isinstance(message.from_id, int):
                        user_id = message.from_id
                    
                    if not user_id or user_id in admin_ids:
                        continue
                    
                    try:
                        user = None
                        for u in history.users:
                            if u.id == user_id:
                                user = u
                                break
                        
                        if user and not user.deleted and user.username:
                            users_with_chat.add(user.username)
                            
                    except Exception:
                        continue
                
                if processed_messages % 5000 == 0:
                    logger.info(f"📈 Processed {processed_messages} messages, found {len(users_with_chat)} unique usernames")
                    gc.collect()
                
                if history.messages:
                    offset_id = history.messages[-1].id
                
                await asyncio.sleep(0.3)
                
            except FloodWaitError as e:
                wait_time = min(e.seconds, 300)
                logger.warning(f"⏳ Flood wait: {wait_time}s")
                await asyncio.sleep(wait_time)
                continue
                
            except Exception as e:
                error_msg = str(e)[:100]
                logger.error(f"❌ Error getting message history: {error_msg}")
                break
        
        logger.info(f"🎯 History scan completed!")
        logger.info(f"📊 Total messages processed: {processed_messages}")
        logger.info(f"✅ Unique usernames found: {len(users_with_chat)}")
        
        return users_with_chat
        
    except Exception as e:
        logger.error(f"💥 Scraping failed: {str(e)[:100]}")
        return set()

def save_users_to_file(usernames, filename):
    """Save usernames to file, one per line"""
    try:
        username_list = sorted(list(usernames))
        
        with open(filename, 'w', encoding='utf-8') as f:
            for username in username_list:
                f.write(f"{username}\n")
        
        logger.info(f"💾 Saved {len(username_list)} usernames to {filename}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to save file: {str(e)}")
        return False

async def load_client():
    """Load the first available client"""
    session_data = await fetch_first_session()
    if not session_data:
        logger.error("💀 No active sessions found in database!")
        return None
    
    phone, sess_str = session_data
    logger.info(f"📱 Loading session: {phone}")
    
    try:
        client = TelegramClient(
            StringSession(sess_str), 
            API_ID, API_HASH,
            connection_retries=10,
            retry_delay=10,
            timeout=60,
            request_retries=5,
            entity_cache_limit=0,
            auto_reconnect=False,
            use_ipv6=False,
            flood_sleep_threshold=600,
            receive_updates=False,
            catch_up=False,
            device_model="Server",
            system_version="Linux",
            app_version="1.0",
            lang_code="en",
            system_lang_code="en"
        )
        
        await client.start()
        client.phone = phone
        
        me = await client.get_me()
        logger.info(f"🔐 Authenticated as: {me.first_name or 'User'}")
        logger.info(f"✅ Client ready: {phone}")
        
        return client
        
    except Exception as e:
        logger.error(f"❌ Failed to load client {phone}: {str(e)[:100]}")
        return None


async def start_scraper_menu():
    """Handle the start scraper menu"""
    print("\n" + "="*80)
    print("🔍 START USER SCRAPER")
    print("="*80)
    print("💡 This will scrape usernames from a Telegram group/channel.")
    print("💡 The scraper analyzes the entire message history.")
    print("💡 Admins are automatically excluded from results.")
    
    # Load client
    client = await load_client()
    if not client:
        print("❌ No active sessions available! Please connect a session first.")
        return
    
    try:
        # Get group input
        print("\n📋 Supported input formats:")
        print("  • Group ID: -1001234567890")
        print("  • Username: @groupname or groupname")
        print("  • Invite Link: https://t.me/joinchat/xxxxx")
        print("  • Invite Link: https://t.me/+xxxxx")
        
        group_input = get_user_input("🔸 Enter group ID, username, or invite link: ")
        if not group_input:
            return
        
        # Parse input and join group
        group_identifier, input_type = parse_group_input(group_input)
        logger.info(f"🎯 Parsed input: {group_identifier} (type: {input_type})")
        
        group_entity = await join_group_if_needed(client, group_identifier, input_type)
        
        # Start scraping
        logger.info(f"🚀 Starting user scraping...")
        usernames = await scrape_group_users(client, group_entity)
        
        if usernames:
            if save_users_to_file(usernames, OUTPUT_FILE):
                logger.info(f"🎉 Successfully scraped {len(usernames)} usernames!")
                logger.info(f"📁 Results saved to: {OUTPUT_FILE}")
            else:
                logger.error("❌ Failed to save results to file")
        else:
            logger.warning("⚠️ No valid usernames found")
        
    except KeyboardInterrupt:
        logger.info("🛑 Scraping interrupted by user")
    except Exception as e:
        logger.error(f"💥 Scraper error: {str(e)[:100]}")
    finally:
        try:
            await client.disconnect()
            logger.info("🔌 Client disconnected")
        except:
            pass
        gc.collect()

# ═══════════════════════════════════════════════════════════════════════════════
#                              🚀 MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Main application entry point"""
    while True:
        clear_screen()
        print_banner()
        print_main_menu()
        
        choice = get_user_input("🎯 Select an option (1-4): ", ['1', '2', '3', '4'])
        
        if choice is None:  # User cancelled
            continue
        
        if choice == '1':
            connect_session_menu()
            input("\n⏸️ Press Enter to continue...")
            
        elif choice == '2':
            try:
                asyncio.run(start_scraper_menu())
            except Exception as e:
                logger.error(f"💥 Scraper error: {str(e)}")
            input("\n⏸️ Press Enter to continue...")
            
        elif choice == '3':
            clear_screen()
            print_credits()
            input("\n⏸️ Press Enter to continue...")
            
        elif choice == '4':
            print("\n🌟 Thank you for using Telegram User Scraper!")
            print("👋 Created by Benjamin White - Professional Edition")
            print("🔗 Have a great day!")
            break

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Application closed by user")
    except Exception as e:
        logger.critical(f"💥 Fatal error: {e}")
