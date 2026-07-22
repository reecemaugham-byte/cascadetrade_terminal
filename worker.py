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
        logging.StreamHandler(),
        logging.FileHandler('worker.log', mode='a')
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
    api_key = safe_decrypt(user.alpaca_api_key or "")
    secret_key = safe_decrypt(user.alpaca_secret_key or "")
        
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

def load_settings_from_db_for_worker(engine, username):
    """Load settings from DB and apply to engine, with verification."""
    try:
        db = SessionLocal()
        user = db.query(User).filter(User.username == username).first()
        if user and hasattr(user, 'settings_json') and user.settings_json:
            try:
                import json
                saved = json.loads(user.settings_json)
                engine._deep_merge(engine.settings, saved)
                engine.save_settings()
                logger.info(f"✅ {username}: Loaded {len(saved)} settings from DB")
                return True
            except Exception as e:
                logger.warning(f"⚠️ {username}: Failed to parse settings_json: {e}")
        else:
            logger.warning(f"⚠️ {username}: No settings_json in DB, using file defaults")
        db.close()
    except Exception as e:
        logger.error(f"❌ {username}: Error loading settings from DB: {e}")
    return False

def save_settings_to_db_for_worker(username, settings_dict):
    """Save settings to DB with verification."""
    try:
        import json
        db = SessionLocal()
        user = db.query(User).filter(User.username == username).first()
        if user:
            if hasattr(user, 'settings_json'):
                user.settings_json = json.dumps(settings_dict)
                db.commit()
                # Verify the save worked
                db.refresh(user)
                if user.settings_json:
                    logger.info(f"✅ {username}: Settings saved to DB ({len(settings_dict)} keys)")
                    return True
                else:
                    logger.error(f"❌ {username}: settings_json is NULL after save!")
            else:
                logger.error(f"❌ {username}: User model doesn't have settings_json column!")
        else:
            logger.warning(f"⚠️ {username}: User not found in DB")
        db.close()
    except Exception as e:
        logger.error(f"❌ {username}: Error saving settings to DB: {e}")
    return False

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
                    
                    # Connect if not connected
                    if not engine.connected:
                        logger.info(f"🔌 {username}: Connecting to Alpaca...")
                        success, msg = connect_engine(engine, user)
                        if not success:
                            logger.error(f"❌ {username}: Connection failed - {msg}")
                            user.bot_status = f"Error: {msg[:80]}"
                            db.commit()
                            continue
                        logger.info(f"✅ {username}: {msg}")
                    
                    # Load settings from DB first (most up-to-date)
                    load_settings_from_db_for_worker(engine, username)
                    # Then also load from file (in case DB is empty)
                    engine.load_settings()
                    
                    # Invalidate all caches before each cycle for fresh data
                    engine.invalidate_all_caches()
                    
                    # Auto-build watchlist if it's too small or stale
                    watchlist_size = len(engine.settings.get("watchlist", []))
                    wl_last_built = engine.settings.get("watchlist_last_built", "")
                    needs_build = watchlist_size < 50 or not wl_last_built
                    
                    if needs_build and engine.connected:
                        try:
                            top_n = engine.settings.get("watchlist_auto_count", 100)
                            logger.info(f"📋 {username}: Auto-building watchlist ({watchlist_size} stocks, needs >= 50)...")
                            wl = engine.auto_build_watchlist(top_n=top_n)
                            if wl:
                                engine.settings["watchlist_last_built"] = datetime.datetime.utcnow().isoformat()
                                engine.save_settings()
                                save_settings_to_db_for_worker(username, engine.settings)
                                logger.info(f"✅ {username}: Auto-built watchlist with {len(wl)} stocks")
                        except Exception as e:
                            logger.warning(f"⚠️ {username}: Auto-build failed: {e}")
                    
                    # Log key settings for debugging
                    watchlist = engine.settings.get("watchlist", [])
                    logger.info(f"📋 {username}: Watchlist has {len(watchlist)} stocks")
                    logger.info(f"⚙️ {username}: Dividend={engine.settings.get('dividend_pct', 0):.0%} "
                               f"Growth={engine.settings.get('growth_pct', 0):.0%} "
                               f"Penny={engine.settings.get('penny_pct', 0):.0%}")
                    
                    # Run one trading cycle
                    logger.info(f"🔄 {username}: Running cycle...")
                    engine.run_cycle()
                    
                    # Log the result
                    status = engine.status_message
                    logger.info(f"📊 {username}: {status}")
                    
                    # Update status in DB so Streamlit can see it
                    user.bot_status = status[:200] if status else "Running"
                    user.last_login = datetime.datetime.utcnow()  # Use as heartbeat
                    db.commit()
                    
                    # Save settings back to DB in case the engine modified them
                    save_settings_to_db_for_worker(username, engine.settings)
                    
                except Exception as e:
                    logger.error(f"❌ {username}: Cycle error - {str(e)}")
                    traceback.print_exc()
                    try:
                        user.bot_status = f"Error: {str(e)[:80]}"
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
        
        # Calculate sleep time based on active users' settings
        if active_users:
            intervals = []
            for user in active_users:
                username = user.username
                if username in active_engines:
                    interval = active_engines[username].settings.get("scan_interval_min", 8) * 60
                    intervals.append(interval)
            sleep_time = max(60, min(intervals) if intervals else 300)
        else:
            sleep_time = 10
        
        logger.info(f"💤 Cycle #{cycle} complete. Sleeping for {sleep_time}s...")
        time.sleep(sleep_time)

if __name__ == "__main__":
    run_worker()
