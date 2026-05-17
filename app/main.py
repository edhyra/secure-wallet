"""Streamlit UI for Secure Wallet."""

import os
import sys
import time

# Ensure repository root is on sys.path so `import app` works when running
# this file directly (e.g. `python app/main.py`) or inside some containers.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import streamlit as st
from app import db, auth


def safe_rerun():
    """Safely attempt to rerun the Streamlit script.

    Some Streamlit builds may not expose `experimental_rerun`; try it first,
    otherwise modify query params as a fallback which also triggers a rerun.
    """
    try:
        if hasattr(st, "experimental_rerun"):
            st.experimental_rerun()
            return
    except Exception:
        pass

    # Fallback: change query params to trigger a rerun
    try:
        st.experimental_set_query_params(_rerun=int(time.time()))
    except Exception:
        # Last resort: stop execution
        st.stop()


def _init_db():
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    database = db.get_db(mongo_uri)
    db.ensure_indexes(database)
    return database


def register_view(database):
    st.header("Register")
    with st.form("register_form"):
        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        password2 = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Register")
        if submitted:
            if not username or not password:
                st.error("Username and password are required")
                return
            if password != password2:
                st.error("Passwords do not match")
                return
            if db.find_user_by_username(database, username):
                st.error("Username already exists")
                return
            pwd_hash = auth.hash_password(password)
            user_id = db.create_user(database, username, email, pwd_hash)
            db.create_main_wallet(database, user_id, initial_balance=100.0)
            st.success("Registered successfully. You can now login.")


def login_view(database):
    st.header("Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            user = db.find_user_by_username(database, username)
            if not user:
                st.error("Invalid username or password")
                return
            if not auth.verify_password(password, user["password_hash"]):
                st.error("Invalid username or password")
                return
            st.session_state.user = {"_id": str(user["_id"]), "username": user["username"]}
            st.success(f"Logged in as {user['username']}")
            safe_rerun()


def dashboard_view(database):
    st.header("Dashboard")
    if "user" not in st.session_state or not st.session_state.user:
        st.info("Please login to access the dashboard")
        return
    user = st.session_state.user
    # Ensure active_menu exists before any menu interactions (logout/create/etc.)
    if "active_menu" not in st.session_state:
        st.session_state["active_menu"] = None

    st.markdown(f"**User:** {user['username']}")

    if st.button("Logout"):
        st.session_state["active_menu"] = "logout_confirm"

    # Logout confirmation rendered as a Streamlit form to match the "Add a side wallet" style
    if st.session_state.get("active_menu") == "logout_confirm":
        with st.form("logout_confirm_form"):
            st.write("Are you sure you want to logout?")
            # Place the two submit buttons close together (left-aligned similar to Create)
            yes_col, no_col = st.columns([1, 3])
            yes = yes_col.form_submit_button("Yes", key="logout_yes")
            no = no_col.form_submit_button("No", key="logout_no")
            if yes:
                st.session_state.user = None
                st.session_state["active_menu"] = None
                safe_rerun()
            if no:
                st.session_state["active_menu"] = None
                safe_rerun()

    main_wallet = db.get_main_wallet_by_user(database, user["_id"])
    if not main_wallet:
        st.error("Main wallet not found for user")
        return

    # Main Wallet summary (only show main wallet balance)
    st.subheader("Main Wallet")
    st.write(f"Balance: {main_wallet.get('balance', 0.0):.2f}")

    # Initialize active_menu state (single active menu at a time)
    if "active_menu" not in st.session_state:
        st.session_state["active_menu"] = None

    # Toggle create side wallet menu
    if st.button("Add a side wallet"):
        if st.session_state.get("active_menu") == "create":
            st.session_state["active_menu"] = None
        else:
            st.session_state["active_menu"] = "create"

    # Side wallets list and state
    st.subheader("Side Wallets")
    side_wallets = db.get_side_wallets(database, str(main_wallet["_id"]))
    if not side_wallets:
        st.info("No side wallets yet.")
        # Do NOT return here — allow the create form to appear even when
        # there are currently no side wallets.

    sids = [str(sw["_id"]) for sw in side_wallets]
    any_unlocked = any(st.session_state.get(f"access_{s}") for s in sids)

    # Show create form if active
    if st.session_state.get("active_menu") == "create":
        with st.form("create_side_wallet"):
            st.write("Create new side wallet (protected by password)")
            wallet_name = st.text_input("Wallet name")
            wallet_password = st.text_input("Wallet password", type="password")
            create = st.form_submit_button("Create")
            if create:
                if not wallet_name or not wallet_password:
                    st.error("Name and password required")
                else:
                    db.create_side_wallet(database, str(main_wallet["_id"]), wallet_name, auth.hash_password(wallet_password))
                    st.success("Side wallet created")
                    st.session_state["active_menu"] = None
                    safe_rerun()

    # Render each side wallet row
    for sw in side_wallets:
        sid = str(sw["_id"])
        cols = st.columns([6, 1, 1])
        cols[0].write(sw["wallet_name"])

        # Open button (disabled when any wallet unlocked)
        if not any_unlocked and not st.session_state.get(f"access_{sid}"):
            if cols[1].button("Open", key=f"open_{sid}"):
                # toggle active menu for this wallet
                if st.session_state.get("active_menu") == f"open_{sid}":
                    st.session_state["active_menu"] = None
                else:
                    st.session_state["active_menu"] = f"open_{sid}"
        else:
            if st.session_state.get(f"access_{sid}"):
                cols[1].write("Unlocked")
            else:
                cols[1].write("")

        # Delete button (available only when no wallet is unlocked and wallet is locked)
        if not any_unlocked and not st.session_state.get(f"access_{sid}"):
            if cols[2].button("Delete", key=f"del_btn_{sid}"):
                if st.session_state.get("active_menu") == f"delete_{sid}":
                    st.session_state["active_menu"] = None
                else:
                    st.session_state["active_menu"] = f"delete_{sid}"
        else:
            cols[2].write("")

        # Open form (password) for this wallet
        if st.session_state.get("active_menu") == f"open_{sid}" and not st.session_state.get(f"access_{sid}"):
            with st.form(f"auth_{sid}"):
                pwd = st.text_input("Enter side wallet password", type="password", key=f"pwd_{sid}")
                submit = st.form_submit_button("Unlock")
                if submit:
                    if db.verify_side_wallet_password(database, sid, pwd):
                        # grant access to this wallet and clear active menu
                        st.session_state[f"access_{sid}"] = True
                        st.session_state["active_menu"] = None
                        st.success("Unlocked")
                        safe_rerun()
                    else:
                        st.error("Invalid password")

        # Delete form (only when not unlocked, outside the unlocked view)
        if st.session_state.get("active_menu") == f"delete_{sid}" and not st.session_state.get(f"access_{sid}"):
            with st.form(f"delete_auth_{sid}"):
                del_pwd = st.text_input("Enter password to delete (wallet must have 0 balance)", type="password", key=f"del_pwd_{sid}")
                confirm = st.form_submit_button("Confirm Delete")
                if confirm:
                    if not db.verify_side_wallet_password(database, sid, del_pwd):
                        st.error("Invalid password")
                    else:
                        sw_curr = db.find_side_wallet(database, sid)
                        if round(float(sw_curr.get("balance", 0.0)), 8) != 0.0:
                            st.error("Cannot delete side wallet with non-zero balance")
                        else:
                            if db.delete_side_wallet(database, sid):
                                st.success("Side wallet deleted")
                                st.session_state.pop(f"access_{sid}", None)
                                st.session_state["active_menu"] = None
                                safe_rerun()
                            else:
                                st.error("Failed to delete side wallet")

        # If access granted, show unlocked view (no delete form here)
        if st.session_state.get(f"access_{sid}"):
            sw_obj = db.find_side_wallet(database, sid)
            st.markdown(f"**{sw_obj['wallet_name']} (Unlocked)**")
            st.write(f"Balance: {sw_obj.get('balance', 0.0):.2f}")

            # Transaction form
            with st.form(f"tx_{sid}"):
                amt_raw = st.text_input("Amount (use dot as decimal)", key=f"amt_{sid}")
                tx_type = st.radio("Type", ["Deposit", "Withdraw"], key=f"type_{sid}")
                submitted = st.form_submit_button("Submit")
                if submitted:
                    amt_str = (amt_raw or "").replace(",", ".").strip()
                    try:
                        amount = float(amt_str)
                    except Exception:
                        st.error("Invalid amount format; use dot for decimals, e.g. 12.34")
                        amount = None

                    if amount is not None:
                        if amount <= 0:
                            st.error("Amount must be positive")
                        else:
                            is_deposit = tx_type == "Deposit"
                            proc_key = f"processing_tx_{sid}"
                            last_key = f"last_tx_{sid}"
                            cur_token = (round(amount, 8), is_deposit)
                            if st.session_state.get(proc_key):
                                st.info("Processing...")
                            elif st.session_state.get(last_key) == cur_token:
                                st.info("Already recorded")
                            else:
                                st.session_state[proc_key] = True
                                try:
                                    db.create_transaction(database, sid, amount, is_deposit)
                                except Exception as e:
                                    st.error(str(e))
                                    st.session_state[proc_key] = False
                                else:
                                    st.session_state[last_key] = cur_token
                                    st.session_state[proc_key] = False
                                    st.success("Transaction recorded")
                                    safe_rerun()

            st.markdown("---")
            txs = db.list_transactions(database, sid, limit=50)
            if txs:
                for t in txs:
                    dt = t.get("transaction_date")
                    date_str = dt.strftime("%Y-%m-%d %H:%M:%S") if dt else ""
                    ttype = "Deposit" if t.get("transaction_type") else "Withdraw"
                    st.write(f"{date_str} — {ttype} — {t.get('amount'):.2f}")
            else:
                st.info("No transactions yet for this side wallet")

            if st.button("Lock side wallet", key=f"lock_{sid}"):
                st.session_state[f"access_{sid}"] = False
                st.session_state["active_menu"] = None
                safe_rerun()


def main():
    st.set_page_config(page_title="Secure Wallet", page_icon="💼")
    database = _init_db()

    if "user" not in st.session_state:
        st.session_state.user = None

    page = st.sidebar.selectbox("Menu", ["Login", "Register", "Dashboard"])
    if page == "Login":
        login_view(database)
    elif page == "Register":
        register_view(database)
    elif page == "Dashboard":
        dashboard_view(database)


if __name__ == "__main__":
    main()
