# src/init_db.py
from src.shared.storage import init_db
if __name__ == "__main__":
    init_db()
    print("✅ SQLite initialized at ./events.db")
