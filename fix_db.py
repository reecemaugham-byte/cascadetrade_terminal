import os
import sqlalchemy
from sqlalchemy import text

# This reads the database URL from your DigitalOcean environment
DATABASE_URL = os.environ.get("DATABASE_URL", "")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found. Make sure you run this in the App Console.")
    exit(1)

# Fix postgres:// to postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = sqlalchemy.create_engine(DATABASE_URL)

print("Connecting to database...")

with engine.connect() as conn:
    print("Adding trading_mode column...")
    try:
        conn.execute(text("ALTER TABLE users ADD COLUMN trading_mode VARCHAR DEFAULT 'paper'"))
        conn.commit()
        print("✅ trading_mode column added successfully!")
    except Exception as e:
        if "already exists" in str(e):
            print("✅ trading_mode column already exists.")
        else:
            print(f"Error adding column: {e}")

    print("Updating tier names...")
    try:
        conn.execute(text("UPDATE users SET tier = 'free' WHERE tier = 'starter'"))
        conn.execute(text("UPDATE users SET tier = 'live_trading' WHERE tier = 'pro'"))
        conn.execute(text("UPDATE users SET tier = 'pro_trader' WHERE tier = 'fund'"))
        conn.execute(text("UPDATE users SET subscription_plan = 'free' WHERE subscription_plan = 'starter'"))
        conn.execute(text("UPDATE users SET subscription_plan = 'live_trading' WHERE subscription_plan = 'pro'"))
        conn.execute(text("UPDATE users SET subscription_plan = 'pro_trader' WHERE subscription_plan = 'fund'"))
        conn.commit()
        print("✅ Tier names updated successfully!")
    except Exception as e:
        print(f"Error updating tiers: {e}")

print("Database fix complete! You can close this console.")
