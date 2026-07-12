import time
import datetime
from core.database import SessionLocal, User
from trading_engine import TradingEngine

def run_worker():
    print("🚀 Roleigh QuanTrader Worker started...")
    
    # Keep track of active engines to avoid reconnecting every second
    active_engines = {}

    while True:
        db = SessionLocal()
        try:
            # Find all users who have clicked "Start Bot" in the UI
            active_users = db.query(User).filter(User.bot_running == True).all()
            
            for user in active_users:
                username = user.username
                
                # If we don't have an engine for this user yet, create one
                if username not in active_engines:
                    print(f"⚡ Initializing engine for {username}...")
                    engine = TradingEngine()
                    engine.set_username(username)
                    active_engines[username] = engine
                
                engine = active_engines[username]
                
                # Update status to Running
                user.bot_status = f"Running - Cycle {engine.cycle_count}"
                db.commit()
                
                # Run a single trading cycle
                try:
                    engine.run_cycle()
                except Exception as e:
                    print(f"❌ Error running cycle for {username}: {e}")
                    user.bot_status = f"Error: {str(e)[:50]}"
                    db.commit()

            # Check for users who clicked "Stop Bot"
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
            print(f"❌ Database error: {e}")
        finally:
            db.close()

        # Wait 60 seconds before the next scan
        print(f"💤 Scan complete. Sleeping for 60 seconds... {datetime.datetime.now()}")
        time.sleep(60)

if __name__ == "__main__":
    run_worker()
