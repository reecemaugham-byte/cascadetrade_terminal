"""
Roleigh QuanTrader — 24/7 Background Worker
"""

import time
import datetime
import json
import traceback
import logging
from core.database import SessionLocal, User
from trading_engine import TradingEngine
from utils import safe_decrypt

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('worker.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

active_engines = {}

def get_or_create_engine(user):
    username = user.username
    if username in active_engines:
        return active_engines[username]
    logger.info(f"Initializing engine for {username}...")
    engine = TradingEngine()
    engine.set_username(username)
    active_engines[username] = engine
    return engine

def connect_engine(engine, user):
    api_key = safe_decrypt(user.alpaca_api_key or "")
    secret_key = safe_decrypt(user.alpaca_secret_key or "")
    if not api_key or not secret_key:
        return False, "Missing Alpaca API keys"
    trading_mode = getattr(user, 'trading_mode', 'paper') or 'paper'
    is_live = trading_mode == 'live'
    success = engine.connect_encrypted(api_key, secret_key, live_mode=is_live)
    return success, "Connected" if success else engine.status_message

def stop_engine(username):
    if username in active_engines:
        logger.info(f"Stopping engine for {username}...")
        try:
            active_engines[username].stop()
        except Exception as e:
            logger.warning(f"Error stopping engine for {username}: {e}")
        finally:
            del active_engines[username]

def load_settings_from_db_for_worker(engine, username):
    try:
        db = SessionLocal()
        user = db.query(User).filter(User.username == username).first()
        if user and hasattr(user, 'settings_json') and user.settings_json:
            saved = json.loads(user.settings_json)
            engine._deep_merge(engine.settings, saved)
            engine.save_settings()
            logger.info(f"Loaded {len(saved)} settings from DB for {username}")
            db.close()
            return True
        db.close()
    except Exception as e:
        logger.warning(f"Could not load DB settings for {username}: {e}")
    return False

def save_settings_to_db_for_worker(username, settings_dict):
    try:
        db = SessionLocal()
        user = db.query(User).filter(User.username == username).first()
        if user and hasattr(user, 'settings_json'):
            user.settings_json = json.dumps(settings_dict)
            db.commit()
            logger.info(f"Saved settings to DB for {username}")
        db.close()
    except Exception as e:
        logger.warning(f"Could not save settings to DB for {username}: {e}")

def run_worker():
    logger.info("=" * 60)
    logger.info("Worker Started")
    logger.info(f"Time: {datetime.datetime.now()}")
    logger.info("=" * 60)
    
    cycle = 0
    
    while True:
        cycle += 1
        db = SessionLocal()
        
        try:
            active_users = db.query(User).filter(User.bot_running == True).all()
            
            if not active_users:
                if cycle % 6 == 0:
                    logger.info(f"[{datetime.datetime.now()}] No active bots. Waiting...")
                db.close()
                time.sleep(10)
                continue
            
            logger.info(f"\n[{datetime.datetime.now()}] Cycle #{cycle} - {len(active_users)} active bot(s)")
            
            # Heartbeat: update last_login for all active users
            for user in active_users:
                username = user.username
                try:
                    from sqlalchemy import text
                    db.execute(text("UPDATE users SET last_login=:now WHERE username=:uname"),
                               {"now": datetime.datetime.now(), "uname": username})
                    db.commit()
                except Exception:
                    pass
            
            for user in active_users:
                username = user.username
                try:
                    engine = get_or_create_engine(user)
                    
                    if not engine.connected:
                        logger.info(f"Connecting {username}...")
                        success, msg = connect_engine(engine, user)
                        if not success:
                            logger.error(f"Connection failed for {username}: {msg}")
                            try:
                                from sqlalchemy import text
                                db.execute(text("UPDATE users SET bot_status=:status WHERE username=:uname"),
                                           {"status": f"Error: {msg[:80]}", "uname": username})
                                db.commit()
                            except Exception:
                                pass
                            continue
                        logger.info(f"Connected {username}")
                    
                    # Load settings
                    load_settings_from_db_for_worker(engine, username)
                    engine.load_settings()
                    engine.invalidate_all_caches()
                    
                    # Run cycle
                    engine.run_cycle()
                    
                    # Get status BEFORE any DB operations
                    status_msg = engine.status_message
                    logger.info(f"{username}: {status_msg}")
                    
                    # Update database with detailed status
                    try:
                        from sqlalchemy import text
                        buy_count = sum(1 for s in engine.signals_found if s.get("signal") == "BUY")
                        sell_count = sum(1 for s in engine.signals_found if s.get("signal") == "SELL")
                        scan_mode = "Universe" if engine.settings.get("scan_full_universe", True) else "Watchlist"
                        detailed_status = (
                            f"✅ Cycle #{engine.cycle_count} | "
                            f"{engine.status_message[:120]} | "
                            f"🟢{buy_count} 🔴{sell_count} | "
                            f"P&L: ${engine.daily_pnl:+,.2f} | "
                            f"Mode: {scan_mode}"
                        )
                        db.execute(text("UPDATE users SET bot_status=:status, last_login=:now WHERE username=:uname"),
                                   {"status": detailed_status[:500],
                                    "now": datetime.datetime.now(),
                                    "uname": username})
                        db.commit()
                    except Exception as e:
                        logger.warning(f"DB update failed for {username}: {e}")
                        try:
                            db.rollback()
                        except Exception:
                            pass
                    
                    # Also save last cycle timestamp in settings_json for heartbeat
                    try:
                        engine.settings["_last_cycle_time"] = datetime.datetime.now().isoformat()
                        engine.settings["_last_cycle_cycles"] = engine.cycle_count
                        engine.settings["_last_cycle_signals"] = len(engine.signals_found)
                        save_settings_to_db_for_worker(username, engine.settings)
                    except Exception:
                        pass
                   
                    # Save settings back to DB
                    save_settings_to_db_for_worker(username, engine.settings)
                    
                except Exception as e:
                    logger.error(f"Cycle error for {username}: {e}")
                    traceback.print_exc()
                    try:
                        db.rollback()
                    except Exception:
                        pass
            
            # Stop engines for users who clicked Stop
            try:
                stopped_users = db.query(User).filter(User.bot_running == False).all()
                for user in stopped_users:
                    username = user.username
                    if username in active_engines:
                        stop_engine(username)
                    try:
                        from sqlalchemy import text
                        db.execute(text("UPDATE users SET bot_status='Stopped' WHERE username=:uname"),
                                   {"uname": username})
                        db.commit()
                    except Exception:
                        pass
            except Exception:
                pass
            
        except Exception as e:
            logger.error(f"Database error: {e}")
            traceback.print_exc()
        finally:
            try:
                db.close()
            except Exception:
                pass
        
        # Calculate sleep time
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
        
        logger.info(f"Cycle #{cycle} complete. Sleeping {sleep_time}s...")
        time.sleep(sleep_time)

if __name__ == "__main__":
    run_worker()
