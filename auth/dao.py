import os
import psycopg2
import logging
import hashlib
from exceptions import DatabaseConnectionError, UserRegistrationError, InvalidCredentialsError

class UserDAO:
    """DAO Layer abstraction for managing authentication"""

    def __init__(self):
        self.host = os.getenv("DB_HOST", "db")
        self.database = os.getenv("DB_NAME", "postgres")
        self.user = os.getenv("DB_USER", "postgres")
        self.password = os.getenv("DB_PASSWORD", "secret")
        self._ensure_table_exists()

    def _get_connection(self):
        try:
            return psycopg2.connect(
                host=self.host,
                database=self.database,
                user=self.user,
                password=self.password
            )
        except psycopg2.OperationalError as err:
            logging.error(f"Failed to establish live connection to database: {err}")
            raise DatabaseConnectionError("Database backend service is unreachable.")

    def _ensure_table_exists(self):
        connection = None
        cursor = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS application_users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    hashed_password VARCHAR(64) NOT NULL
                );
            """)
            connection.commit()
            logging.info("Schema integrity verified: application_users table exists.")
        except Exception as err:
            logging.critical(f"Failed to bootstrap application table schema: {err}")
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

    def _hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    def create_user(self, username: str, password: str):
        connection = None
        cursor = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            hashed = self._hash_password(password)
            cursor.execute(
                "INSERT INTO application_users (username, hashed_password) VALUES (%s, %s);",
                (username, hashed)
            )
            connection.commit()
        except psycopg2.IntegrityError:
            raise UserRegistrationError("Username is already registered inside the domain")
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

    def authenticate_user(self, username: str, password: str) -> bool:
        connection = None
        cursor = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            hashed = self._hash_password(password)
            cursor.execute(
                "SELECT id FROM application_users WHERE username = %s AND hashed_password = %s;",
                (username, hashed)
            )
            user_record = cursor.fetchone()
            if not user_record:
                raise InvalidCredentialsError("Invalid username or password validation cred")
            return True
        finally:
            if cursor: cursor.close()
            if connection: connection.close()