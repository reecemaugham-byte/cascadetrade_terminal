"""
Roleigh QuanTrader — 24/7 Background Worker
This script runs independently of Streamlit. It reads the database for active users,
connects to Alpaca, and executes trades. 
"""

import time
import datetime
import traceback
from core.database import SessionLocal, User
from trading_engine import TradingEngine
from utils import safe_decrypt

# Keep track of active engines in memory so we don't reconnect every cycle
active_engines = {}

def get_or_create_engine(user):
    """Get an existing engine for a user, or create a new one."""
    username = user.username
    
    if username in active_engines:
        return active_engines[username]
    
    print(f"[{datetime.datetime.now()}] ⚡ Initializing engine for {username}...")
    engine = TradingEngine()
    engine.set_username(username)
    active_engines[username] = engine
    return engine

def connect_engine(engine, user):
    """Decrypt the user's Alpaca keys and connect the engine."""
    # Decrypt keys
    # Decrypt keys using the app's safe fallback method
    api_key = safe_decrypt(user.alpaca_api_key)
    secret_key = safe_decrypt(user.alpaca_secret_key)
        
    if not api_key or not secret_key:
        return False, "Missing Alpaca API keys"
    
    # Determine Paper vs Live mode
    trading_mode = getattr(user, 'trading_mode', 'paper') or 'paper'
    is_live = trading_mode == 'live'
    
    # Connect
    success = engine.connect_encrypted(api_key, secret_key, live_mode=is_live)
    return success, "Connected" if success else engine.status_message

def run_worker():
    print("=" * 60)
    print("🚀 Roleigh QuanTrader Worker Started")
    print(f"⏰ Time: {datetime.datetime.now()}")
    print("=" * 60)
    
    while True:
        db = SessionLocal()
        try:
            # 1. Find all users who have clicked "Start Bot"
            active_users = db.query(User).filter(User.bot_running == True).all()
            
            if not active_users:
                # No one is trading, just wait
                time.sleep(10)
                continue
                
            print(f"\n[{datetime.datetime.now()}] 🔄 Checking {len(active_users)} active bot(s)...")
            
            # 2. Run a cycle for each active user
            for user in active_users:
                username = user.username
                try:
                    engine = get_or_create_engine(user)
                    
                    # Connect if not connected
                    if not engine.connected:
                        success, msg = connect_engine(engine, user)
                        if not success:
                            print(f"❌ {username}: Connection failed - {msg}")
                            user.bot_status = f"Error: {msg[:50]}"
                            db.commit()
                            continue
                    
                    # Run one trading cycle
                    engine.run_cycle()
                    
                    # Update status in DB so Streamlit can see it
                    user.bot_status = f"Running - Cycle {engine.cycle_count}"
                    db.commit()
                    
                except Exception as e:
                    print(f"❌ {username}: Cycle error - {str(e)}")
                    user.bot_status = f"Error: {str(e)[:50]}"
                    db.commit()
            
            # 3. Check for users who clicked "Stop Bot"
            stopped_users = db.query(User).filter(User.bot_running == False).all()
            for user in stopped_users:
                username = user.username
                if username in active_engines:
                    print(f"🛑 Stopping engine for {username}...")
                    engine = active_engines[username]
                    engine.stop()
                    del active_engines[username]
                user.bot_status = "Stopped"
                db.commit()
                
        except Exception as e:
            print(f"❌ Database error: {str(e)}")
            traceback.print_exc()
        finally:
            db.close()
            
        # Wait 60 seconds before the next scan
        print(f"[{datetime.datetime.now()}] 💤 Cycle complete. Sleeping for 60 seconds...")
        time.sleep(60)

if __name__ == "__main__":
    run_worker()
