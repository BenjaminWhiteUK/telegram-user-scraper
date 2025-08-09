#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     تلگرام یوزر اسکرپر - حالت بدون مشکل حافظه                   ║
║                            تنظیمات قابل تغییر                                ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# ═══════════════════════════════════════════════════════════════════════════════
#                           ⚙️ تنظیمات اصلی - اینجا تغییر بده
# ═══════════════════════════════════════════════════════════════════════════════

# ===== اطلاعات تلگرام - دست نزن =====
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
from contextlib import asynccontextmanager
import psutil
from datetime import datetime
import platform
import warnings

# سرکوب تمام warnings برای جلوگیری از segfault
warnings.filterwarnings("ignore")
os.environ['PYTHONWARNINGS'] = 'ignore'

# تنظیم signal handler برای جلوگیری از segmentation fault
def signal_handler(signum, frame):
    try:
        logger.info("🛑 Signal received - Safe shutdown...")
        os._exit(0)
    except:
        os._exit(1)

signal.signal(signal.SIGSEGV, signal_handler)  # Segmentation fault
signal.signal(signal.SIGTERM, signal_handler)  # Termination
signal.signal(signal.SIGINT, signal_handler)   # Interrupt

# جایگزینی event loop پیش‌فرض با uvloop برای I/O سریع‌تر
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    PeerFloodError, FloodWaitError, ChatAdminRequiredError,
    ChatWriteForbiddenError, ForbiddenError, UserKickedError,
    ChannelPrivateError, InviteHashExpiredError, InviteHashInvalidError
)
from telethon.tl.functions.channels import JoinChannelRequest, GetParticipantsRequest
from telethon.tl.functions.messages import ImportChatInviteRequest, GetHistoryRequest
from telethon.tl.types import ChannelParticipantsSearch, ChannelParticipantsAdmins

# ===== ENHANCED LOGGING SYSTEM =====
class ColoredFormatter(logging.Formatter):
    """Colorful and stylish log formatter"""
    
    # ANSI Color codes
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
    
    # Emoji mapping
    EMOJIS = {
        'DEBUG': '🔍',
        'INFO': '✅',
        'WARNING': '⚠️',
        'ERROR': '❌',
        'CRITICAL': '🚨',
    }
    
    def format(self, record):
        # Get color and emoji for level
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        emoji = self.EMOJIS.get(record.levelname, '📝')
        reset = self.COLORS['RESET']
        bold = self.COLORS['BOLD']
        dim = self.COLORS['DIM']
        
        # Format timestamp with style
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        # Create styled log message
        if record.levelname == 'INFO':
            formatted = f"{color}{bold}[{timestamp}]{reset} {emoji} {color}{record.getMessage()}{reset}"
        elif record.levelname == 'WARNING':
            formatted = f"{color}{bold}[{timestamp}]{reset} {emoji} {color}⚡ {record.getMessage()}{reset}"
        elif record.levelname == 'ERROR':
            formatted = f"{color}{bold}[{timestamp}]{reset} {emoji} {color}💥 {record.getMessage()}{reset}"
        elif record.levelname == 'CRITICAL':
            formatted = f"{color}{bold}[{timestamp}]{reset} {emoji} {color}🔥 CRITICAL: {record.getMessage()}{reset}"
        else:
            formatted = f"{dim}[{timestamp}]{reset} {emoji} {record.getMessage()}"
        
        return formatted

# Setup enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',  # We'll handle formatting in ColoredFormatter
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Apply colored formatter to all handlers
for handler in logging.root.handlers:
    handler.setFormatter(ColoredFormatter())

# خاموش کردن کامل لاگ‌های مزاحم Telethon
telethon_loggers = [
    'telethon',
    'telethon.client', 
    'telethon.network',
    'telethon.sessions',
    'telethon.network.connection',
    'telethon.network.mtprotosender',
    'telethon.crypto',
    'telethon.extensions',
    'asyncio',
    'urllib3'
]

for logger_name in telethon_loggers:
    telethon_logger = logging.getLogger(logger_name)
    telethon_logger.setLevel(logging.CRITICAL + 10)  # خاموش کامل
    telethon_logger.disabled = True  # غیرفعال کردن کامل

logger = logging.getLogger(__name__)

# ===== SPECIAL LOG FUNCTIONS =====
def log_banner(title, subtitle=""):
    """Create a fancy banner for important sections"""
    width = 60
    print("\n" + "═" * width)
    print(f"🚀 {title.center(width-4)} 🚀")
    if subtitle:
        print(f"   {subtitle.center(width-6)}   ")
    print("═" * width + "\n")

def log_startup_info():
    """Display beautiful startup information"""
    log_banner("TELEGRAM USER SCRAPER", "Enhanced Logging Mode")
    
    # System info
    system_info = [
        f"🖥️  System: {platform.system()} {platform.release()}",
        f"🐍 Python: {platform.python_version()}",
        f"⚡ Mode: USER SCRAPING MODE - Anti-MemoryError",
        f"🕐 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ]
    
    for info in system_info:
        logger.info(info)

# ═══════════════════════════════════════════════════════════════════════════════
#                           🧠 MEMORY MANAGEMENT & GC SETUP
# ═══════════════════════════════════════════════════════════════════════════════

# مدیریت فوق‌العاده تهاجمی GC
gc.set_threshold(100, 3, 3)  # حداکثر تهاجمی برای جلوگیری از نشت حافظه
gc.enable()  # اطمینان از فعال بودن GC

def init_db(path):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    # تنظیمات فوق‌سبک برای سرور کم‌حافظه
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=OFF')  # سریع‌تر برای عملکرد
    conn.execute('PRAGMA cache_size=1000')  # کاهش کش برای صرفه‌جویی در RAM
    conn.execute('PRAGMA temp_store=MEMORY')
    conn.execute('PRAGMA mmap_size=67108864')  # کاهش به 64MB
    conn.execute('PRAGMA optimize')  # بهینه‌سازی خودکار
    conn.commit()
    return conn

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
    
    # If it's a number (group ID)
    if group_input.lstrip('-').isdigit():
        return int(group_input), 'id'
    
    # If it's an invite link
    if 'joinchat/' in group_input or 't.me/+' in group_input:
        # Extract hash from invite link
        if 'joinchat/' in group_input:
            hash_part = group_input.split('joinchat/')[-1]
        else:  # t.me/+ format
            hash_part = group_input.split('t.me/+')[-1]
        
        # Clean any additional parameters
        hash_part = hash_part.split('?')[0].split('&')[0]
        return hash_part, 'invite'
    
    # If it's a username or t.me link
    if group_input.startswith('@'):
        return group_input[1:], 'username'
    elif 't.me/' in group_input and 'joinchat/' not in group_input and 't.me/+' not in group_input:
        username = group_input.split('t.me/')[-1]
        username = username.split('?')[0].split('/')[0]  # Clean parameters
        return username, 'username'
    else:
        # Assume it's a username without @
        return group_input, 'username'

async def join_group_if_needed(client, group_identifier, input_type):
    """Join group if not already joined"""
    try:
        if input_type == 'invite':
            # Join using invite hash
            logger.info(f"🔗 Joining group via invite link...")
            result = await client(ImportChatInviteRequest(group_identifier))
            return result.chats[0]  # Return the chat object
        
        elif input_type == 'username':
            # Join using username
            logger.info(f"🔗 Joining group @{group_identifier}...")
            entity = await client.get_entity(group_identifier)
            try:
                await client(JoinChannelRequest(entity))
                logger.info(f"✅ Successfully joined @{group_identifier}")
            except Exception as e:
                # Might already be a member
                if "already" in str(e).lower():
                    logger.info(f"ℹ️ Already a member of @{group_identifier}")
                else:
                    logger.warning(f"⚠️ Join attempt: {str(e)[:50]}")
            return entity
        
        else:  # input_type == 'id'
            # Get entity by ID
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
        # Get admin participants
        admins = await client(GetParticipantsRequest(
            group_entity,
            ChannelParticipantsAdmins(),
            0,
            100,  # Most groups won't have more than 100 admins
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
    
    users_with_chat = set()  # Use set to avoid duplicates
    admin_ids = await get_group_admins(client, group_entity)
    
    try:
        # Get group info
        full_group = await client.get_entity(group_entity)
        logger.info(f"📊 Group: {full_group.title}")
        logger.info(f"🕐 Scanning entire message history for active users...")
        
        # Scan message history to find users who have actually chatted
        offset_id = 0
        limit = 100  # Messages per batch
        total_messages = 0
        processed_messages = 0
        
        while True:
            try:
                # Get message history batch
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
                
                # Process messages to find senders
                for message in history.messages:
                    processed_messages += 1
                    
                    # Skip if message has no sender (system messages, etc.)
                    if not hasattr(message, 'from_id') or not message.from_id:
                        continue
                    
                    # Get user ID from message
                    user_id = None
                    if hasattr(message.from_id, 'user_id'):
                        user_id = message.from_id.user_id
                    elif isinstance(message.from_id, int):
                        user_id = message.from_id
                    
                    if not user_id:
                        continue
                    
                    # Skip if user is admin
                    if user_id in admin_ids:
                        continue
                    
                    # Get user entity and check for username
                    try:
                        # Find user in the history.users list (more efficient)
                        user = None
                        for u in history.users:
                            if u.id == user_id:
                                user = u
                                break
                        
                        if user and not user.deleted and user.username:
                            users_with_chat.add(user.username)
                            
                    except Exception:
                        # Skip this user if we can't get their info
                        continue
                
                # Log progress every 5000 messages
                if processed_messages % 5000 == 0:
                    logger.info(f"📈 Processed {processed_messages} messages, found {len(users_with_chat)} unique usernames")
                    # Memory cleanup
                    gc.collect()
                
                # Update offset for next batch
                if history.messages:
                    offset_id = history.messages[-1].id
                
                # Small delay to avoid hitting rate limits
                await asyncio.sleep(0.3)
                
            except FloodWaitError as e:
                wait_time = min(e.seconds, 300)  # Max 5 minutes
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
        # Convert set to sorted list for consistent output
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
        
        # Test connection
        me = await client.get_me()
        logger.info(f"🔐 Authenticated as: {me.first_name or 'User'}")
        logger.info(f"✅ Client ready: {phone}")
        
        return client
        
    except Exception as e:
        logger.error(f"❌ Failed to load client {phone}: {str(e)[:100]}")
        return None

async def main():
    log_startup_info()
    
    # Load client
    client = await load_client()
    if not client:
        logger.error("💀 Could not load any session!")
        return
    
    try:
        # Get group input from user
        print("\n" + "="*60)
        print("🎯 GROUP INPUT OPTIONS:")
        print("  • Group ID: -1001234567890")
        print("  • Username: @groupname or groupname")
        print("  • Invite Link: https://t.me/joinchat/xxxxx")
        print("  • Invite Link: https://t.me/+xxxxx")
        print("="*60)
        
        group_input = input("\n🔸 Enter group ID, username, or invite link: ").strip()
        
        if not group_input:
            logger.error("❌ No input provided!")
            return
        
        # Parse the input
        group_identifier, input_type = parse_group_input(group_input)
        logger.info(f"🎯 Parsed input: {group_identifier} (type: {input_type})")
        
        # Join group if needed and get entity
        group_entity = await join_group_if_needed(client, group_identifier, input_type)
        
        # Start scraping
        logger.info(f"🚀 Starting user scraping...")
        usernames = await scrape_group_users(client, group_entity)
        
        if usernames:
            # Save to file
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
        logger.error(f"💥 Main error: {str(e)[:100]}")
    finally:
        # Cleanup
        try:
            await client.disconnect()
            logger.info("🔌 Client disconnected")
        except:
            pass
        
        # Final memory cleanup
        gc.collect()
        logger.info("🧹 Cleanup completed")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"💥 Fatal error: {e}")
