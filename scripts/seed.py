"""Seed script to create demo user, wallets and sample transactions."""

import os
import sys

# Ensure the repository root is on sys.path when running the script directly
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import db, auth


def main():
    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    # Reset database to ensure seed creates a fresh dataset
    client = db.get_client(uri)
    try:
        client.drop_database(db.MONGO_DB)
    except Exception:
        pass

    database = db.get_db(uri)
    db.ensure_indexes(database)

    pwd_hash = auth.hash_password("password")
    user_id = db.create_user(database, "demo", "demo@example.com", pwd_hash)
    # Create main wallet with a starting balance of 100 (no side wallets by default)
    main_wallet_id = db.create_main_wallet(database, user_id, initial_balance=100.0)

    print("Seed created: user=demo password=password (main wallet balance=100)")


if __name__ == "__main__":
    main()
