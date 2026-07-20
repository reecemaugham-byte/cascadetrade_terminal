"""
Roleigh QuanTrader — 24/7 Background Worker
Runs independently of Streamlit. Reads the database for active users,
connects to Alpaca, and executes trades.
"""

import time
import datetime
import traceback
import logging
from core.database import SessionLocal, User
from sqlalchemy import text
from trading_engine import TradingEngine
from utils import safe_decrypt

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Keep track of active engines in memory
active_engines = {}

def get_or_create_engine(user):
    """Get an existing engine for a user, or create a new one."""
    username = user.username
    
    if username in active_engines:
        return active_engines[username]
    
    logger.info(f"⚡ Initializing engine for {username}...")
    engine = TradingEngine()
    engine.set_username(username)
    active_engines[username] = engine
    return engine

def connect_engine(engine, user):
    """Decrypt the user's Alpaca keys and connect the engine."""
    api_key = safe_decrypt(user.alpaca_api_key)
    secret_key = safe_decrypt(user.alpaca_secret_key)
        
    if not api_key or not secret_key:
        return False, "Missing Alpaca API keys"
    
    trading_mode = getattr(user, 'trading_mode', 'paper') or 'paper'
    is_live = trading_mode == 'live'
    
    success = engine.connect_encrypted(api_key, secret_key, live_mode=is_live)
    return success, "Connected" if success else engine.status_message

def stop_engine(username):
    """Cleanly shut down a user's engine."""
    if username in active_engines:
        logger.info(f"🛑 Stopping engine for {username}...")
        try:
            active_engines[username].stop()
        except Exception as e:
            logger.warning(f"Error stopping engine for {username}: {e}")
        finally:
            del active_engines[username]

def run_worker():
    logger.info("=" * 60)
    logger.info("🚀 Roleigh QuanTrader Worker Started")
    logger.info(f"⏰ Time: {datetime.datetime.now()}")
    logger.info("=" * 60)
    
    cycle = 0
    
    while True:
        cycle += 1
        db = SessionLocal()
        active_users = []
        
        try:
            # 1. Find all users who have clicked "Start Bot"
            active_users = db.query(User).filter(User.bot_running == True).all()
            
            if not active_users:
                # Only print heartbeat every 6th cycle (every ~60 seconds at 10s sleep)
                if cycle % 6 == 0:
                    logger.info(f"[{datetime.datetime.now()}] 💤 No active bots. Waiting...")
                time.sleep(10)
                continue
            
            logger.info(f"\n[{datetime.datetime.now()}] 🔄 Cycle #{cycle} — Checking {len(active_users)} active bot(s)...")
            
            # 2. Run a cycle for each active user
            for user in active_users:
                username = user.username
                try:
                    engine = get_or_create_engine(user)
                    
                    logger.info(f"🔍 {username}: engine.connected = {engine.connected}")
                    
                    # Connect if not connected
                    if not engine.connected:
                        logger.info(f"🔌 {username}: Connecting to Alpaca...")
                        success, msg = connect_engine(engine, user)
                        if not success:
                            logger.error(f"❌ {username}: Connection failed - {msg}")
                            user.bot_status = f"Error: {msg[:50]}"
                            db.commit()
                            continue
                        logger.info(f"✅ {username}: {msg}")
                    
                    # Reload settings from file so UI changes take effect
                    engine.load_settings()
                    engine.invalidate_bucket_cache()
                    
                    # Run one trading cycle
                    logger.info(f"🔄 {username}: Running cycle...")
                    engine.run_cycle()
                    
                    # Update status in DB so Streamlit can see it
                    status_msg = f"Running - Cycle {engine.cycle_count}"
                    user.bot_status = status_msg
                    user.last_login = datetime.datetime.utcnow()  # Use as heartbeat timestamp
                    db.commit()
                    logger.info(f"✅ {username}: Cycle {engine.cycle_count} complete")
                except Exception as e:
                    logger.error(f"❌ {username}: Cycle error - {str(e)}")
                    traceback.print_exc()
                    try:
                        user.bot_status = f"Error: {str(e)[:50]}"
                        db.commit()
                    except:
                        pass
            
            # 3. Check for users who clicked "Stop Bot"
            stopped_users = db.query(User).filter(User.bot_running == False).all()
            for user in stopped_users:
                username = user.username
                if username in active_engines:
                    stop_engine(username)
                user.bot_status = "Stopped"
                db.commit()
            
        except Exception as e:
            logger.error(f"❌ Database error: {str(e)}")
            traceback.print_exc()
        finally:
            db.close()
        
        # Use the shortest scan interval from active users' settings
        if active_users:
            min_interval = min(
                (e.settings.get("scan_interval_min", 8) * 60 for e in 
                 [active_engines.get(u.username) for u in active_users if u.username in active_engines]
                 if e is not None),
                default=300
            )
            sleep_time = max(60, min_interval)  # At least 60 seconds
        else:
            sleep_time = 10
        logger.info(f"[{datetime.datetime.now()}] 💤 Cycle #{cycle} complete. Sleeping for {sleep_time}s...")
        time.sleep(sleep_time)

if __name__ == "__main__":
    run_worker()
