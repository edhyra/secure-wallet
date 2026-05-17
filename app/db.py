"""MongoDB helper functions for Secure Wallet."""

import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson.objectid import ObjectId

# import auth from same package for side-wallet password verification
from . import auth

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "secure_wallet")


def get_client(uri: Optional[str] = None) -> MongoClient:
    uri = uri or MONGO_URI
    return MongoClient(uri)


def get_db(uri: Optional[str] = None):
    client = get_client(uri)
    return client[MONGO_DB]


def ensure_indexes(db):
    db.users.create_index([("username", ASCENDING)], unique=True)
    db.users.create_index([("email", ASCENDING)], unique=True)
    db.main_wallets.create_index([("user_id", ASCENDING)], unique=True)
    db.side_wallets.create_index([("main_wallet_id", ASCENDING)])
    db.transactions.create_index([("side_wallet_id", ASCENDING), ("transaction_date", DESCENDING)])


def to_json(doc: Optional[Dict[str, Any]]):
    if not doc:
        return doc
    doc = dict(doc)
    for k, v in list(doc.items()):
        if isinstance(v, ObjectId):
            doc[k] = str(v)
    return doc


def create_user(db, username: str, email: str, password_hash: str) -> str:
    user = {"username": username, "email": email, "password_hash": password_hash}
    res = db.users.insert_one(user)
    return str(res.inserted_id)


def find_user_by_username(db, username: str) -> Optional[Dict[str, Any]]:
    return db.users.find_one({"username": username})


def find_user_by_id(db, user_id: str) -> Optional[Dict[str, Any]]:
    return db.users.find_one({"_id": ObjectId(user_id)})


def create_main_wallet(db, user_id: str, initial_balance: float = 0.0) -> str:
    mw = {"user_id": ObjectId(user_id), "balance": float(initial_balance)}
    res = db.main_wallets.insert_one(mw)
    return str(res.inserted_id)


def get_main_wallet_by_user(db, user_id: str) -> Optional[Dict[str, Any]]:
    return db.main_wallets.find_one({"user_id": ObjectId(user_id)})


def create_side_wallet(db, main_wallet_id: str, wallet_name: str, wallet_password_hash: str) -> str:
    sw = {
        "main_wallet_id": ObjectId(main_wallet_id),
        "wallet_name": wallet_name,
        "wallet_password_hash": wallet_password_hash,
        "balance": 0.0,
    }
    res = db.side_wallets.insert_one(sw)
    return str(res.inserted_id)


def get_side_wallets(db, main_wallet_id: str) -> List[Dict[str, Any]]:
    return list(db.side_wallets.find({"main_wallet_id": ObjectId(main_wallet_id)}))


def find_side_wallet(db, side_wallet_id: str) -> Optional[Dict[str, Any]]:
    return db.side_wallets.find_one({"_id": ObjectId(side_wallet_id)})


def create_transaction(db, side_wallet_id: str, amount: float, transaction_type: bool) -> str:
    """Create a transaction for a side wallet and update both side and main wallets.

    If `transaction_type` is True -> Deposit into side wallet (move from main -> side).
    If False -> Withdraw from side wallet (move from side -> main).

    Raises ValueError on insufficient funds or duplicate transactions.
    Returns inserted transaction id as string on success.
    """
    now = datetime.utcnow()

    sw = db.side_wallets.find_one({"_id": ObjectId(side_wallet_id)})
    if not sw:
        raise ValueError("Side wallet not found")

    main_wallet = db.main_wallets.find_one({"_id": sw["main_wallet_id"]})
    if not main_wallet:
        raise ValueError("Main wallet not found")

    # duplicate check: ignore if last identical tx within 2 seconds
    last = db.transactions.find({"side_wallet_id": sw["_id"]}).sort("transaction_date", DESCENDING).limit(1)
    last_tx = None
    for l in last:
        last_tx = l
        break
    if last_tx is not None:
        try:
            last_dt = last_tx.get("transaction_date")
            if last_tx.get("amount") == float(amount) and last_tx.get("transaction_type") == bool(transaction_type):
                if (now - last_dt).total_seconds() < 2:
                    raise ValueError("Duplicate transaction detected")
        except Exception:
            pass

    # fund checks
    if transaction_type:
        # deposit: move from main to side
        if float(main_wallet.get("balance", 0.0)) < float(amount):
            raise ValueError("Insufficient funds in main wallet")
    else:
        # withdraw: move from side to main
        if float(sw.get("balance", 0.0)) < float(amount):
            raise ValueError("Insufficient funds in side wallet")

    tr = {
        "side_wallet_id": sw["_id"],
        "amount": float(amount),
        "transaction_type": bool(transaction_type),
        "transaction_date": now,
    }
    res = db.transactions.insert_one(tr)

    # update balances
    if transaction_type:
        # deposit: main -amount, side +amount
        db.main_wallets.update_one({"_id": main_wallet["_id"]}, {"$inc": {"balance": -float(amount)}})
        db.side_wallets.update_one({"_id": sw["_id"]}, {"$inc": {"balance": float(amount)}})
    else:
        # withdraw: side -amount, main +amount
        db.side_wallets.update_one({"_id": sw["_id"]}, {"$inc": {"balance": -float(amount)}})
        db.main_wallets.update_one({"_id": main_wallet["_id"]}, {"$inc": {"balance": float(amount)}})

    return str(res.inserted_id)


def verify_side_wallet_password(db, side_wallet_id: str, password: str) -> bool:
    """Verify a provided password for a side wallet."""
    sw = db.side_wallets.find_one({"_id": ObjectId(side_wallet_id)})
    if not sw:
        return False
    pw_hash = sw.get("wallet_password_hash")
    if not pw_hash:
        return False
    return auth.verify_password(password, pw_hash)


def delete_side_wallet(db, side_wallet_id: str) -> bool:
    """Delete a side wallet and its transactions only if its balance is zero.

    Returns True when deletion succeeded, False otherwise.
    """
    sw = db.side_wallets.find_one({"_id": ObjectId(side_wallet_id)})
    if not sw:
        return False
    balance = float(sw.get("balance", 0.0))
    if round(balance, 8) != 0.0:
        return False
    # delete transactions and side wallet
    db.transactions.delete_many({"side_wallet_id": sw["_id"]})
    db.side_wallets.delete_one({"_id": sw["_id"]})
    return True


def list_transactions(db, side_wallet_id: str, limit: int = 100):
    return list(
        db.transactions.find({"side_wallet_id": ObjectId(side_wallet_id)}).sort("transaction_date", -1).limit(limit)
    )
