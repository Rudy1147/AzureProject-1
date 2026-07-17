import os
import psycopg2
import logging
import hashlib
from app.exceptions import DatabaseConnectionError, LogCreationError, UserRegistrationError, InvalidCredentialsError

# Initialize structured logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class SystemLogDAO:
    """DAO layer abstraction managing operational payloads for system_logs."""

    def __init__(self):
        # Read parameters provided by Docker Compose environment variables
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
        """Initializes database schema structurally if missing."""
        connection = None
        cursor = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_logs (
                    id SERIAL PRIMARY KEY,
                    host VARCHAR(50),
                    severity VARCHAR(20),
                    message TEXT
                );
            """)
            connection.commit()
            logging.info("Schema integrity verified: system_logs table exists.")
        except Exception as err:
            logging.critical(f"Failed to bootstrap application table schema: {err}")
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

    def insert_log(self, host: str, severity: str, message: str):
        """Securely inserts log strings using parameterized inputs."""
        connection = None
        cursor = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()

            # Parameterized Query execution
            query = "INSERT INTO system_logs (host, severity, message) VALUES (%s, %s, %s);"
            cursor.execute(query, (host, severity, message))
            connection.commit()
            logging.info(f"Successfully recorded structured log entry for host: {host}")
        except DatabaseConnectionError:
            raise
        except Exception as err:
            logging.error(f"Failed to execute target insert statement: {err}")
            raise LogCreationError("Data layer constraint violation occurred.")
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

    def get_all_logs(self) -> list:
        """Fetches and handles database record sets cleanly."""
        connection = None
        cursor = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute("SELECT host, severity, message FROM system_logs ORDER BY id DESC;")
            records = cursor.fetchall()

            # Map elements into a structured payload list of dictionaries
            return [{"host": row[0], "severity": row[1], "message": row[2]} for row in records]
        except DatabaseConnectionError:
            raise
        except Exception as err:
            logging.error(f"Retrieval failure across data layers: {err}")
            raise DatabaseConnectionError("Failed to retrieve logs from the database.")
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

class UserDAO:
    """DAO Layer abstraciton for managing authentication"""

    def __init__(self, system_log_dao):
        # Read parameters provided by Docker Compose environment variables
        self.host = system_log_dao.host
        self.database = system_log_dao.database
        self.user = system_log_dao.user
        self.password = system_log_dao.password
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
        """Initializes database schema structurally if missing."""
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