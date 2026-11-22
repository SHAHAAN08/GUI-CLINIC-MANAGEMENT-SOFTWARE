import hashlib
import hmac
import os
from mysql.connector import Error
from database import get_connection


def hash_password(password, salt=None):
    """Hash a password using PBKDF2-HMAC-SHA256."""
    if salt is None:
        salt = os.urandom(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        310_000
    )

    # Store salt and hash together as hexadecimal text.
    return salt.hex() + "$" + password_hash.hex()


def verify_password(password, stored_value):
    try:
        salt_hex, hash_hex = stored_value.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        expected_hash = bytes.fromhex(hash_hex)

        actual_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            310_000
        )

        return hmac.compare_digest(actual_hash, expected_hash)
    except (ValueError, TypeError):
        return False


def signup():
    print("\\n========== CLINIC SIGNUP ==========")
    clinic_name = input("Clinic Name: ").strip()
    username = input("Username: ").strip()
    email = input("Email: ").strip().lower()
    password = input("Password: ")
    confirm_password = input("Confirm Password: ")

    if not all([clinic_name, username, email, password]):
        print("All fields are required.")
        return None

    if password != confirm_password:
        print("Passwords do not match.")
        return None

    if len(password) < 8:
        print("Password must contain at least 8 characters.")
        return None

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            "SELECT user_id FROM users WHERE username = %s OR email = %s",
            (username, email)
        )

        if cursor.fetchone():
            print("Username or email already registered.")
            return None

        password_hash = hash_password(password)

        cursor.execute(
            """
            INSERT INTO users (clinic_name, username, email, password_hash)
            VALUES (%s, %s, %s, %s)
            """,
            (clinic_name, username, email, password_hash)
        )
        connection.commit()

        user_id = cursor.lastrowid
        print("\\nSignup successful. Your clinic account has been created.")
        return {
            "user_id": user_id,
            "clinic_name": clinic_name,
            "username": username
        }

    except Error as error:
        if connection:
            connection.rollback()
        print("Signup database error:", error)
        return None

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def login():
    print("\\n========== CLINIC LOGIN ==========")
    username = input("Username: ").strip()
    password = input("Password: ")

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT user_id, clinic_name, username, password_hash
            FROM users
            WHERE username = %s
            """,
            (username,)
        )
        user = cursor.fetchone()

        if not user or not verify_password(password, user["password_hash"]):
            print("Invalid username or password.")
            return None

        print("\\nLogin successful. Welcome to", user["clinic_name"])
        return {
            "user_id": user["user_id"],
            "clinic_name": user["clinic_name"],
            "username": user["username"]
        }

    except Error as error:
        print("Login database error:", error)
        return None

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
