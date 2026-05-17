import os

from app import db, auth


def test_create_and_find_user():
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    client = db.get_client(mongo_uri)
    test_db_name = "secure_wallet_test"
    client.drop_database(test_db_name)
    test_db = client[test_db_name]
    db.ensure_indexes(test_db)

    pwd_hash = auth.hash_password("secret")
    user_id = db.create_user(test_db, "testuser", "test@example.com", pwd_hash)
    assert user_id is not None
    user = db.find_user_by_username(test_db, "testuser")
    assert user["email"] == "test@example.com"

    client.drop_database(test_db_name)
