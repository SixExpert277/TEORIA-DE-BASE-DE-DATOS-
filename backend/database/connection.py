import mysql.connector
from mysql.connector import Error

from config import BATCH_SIZE, DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER


class DatabaseConnectionError(Exception):
    pass


def get_db_connection(autocommit=False):
    try:
        return mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset="utf8mb4",
            collation="utf8mb4_unicode_ci",
            autocommit=autocommit,
        )
    except Error as error:
        raise DatabaseConnectionError(f"No se pudo conectar a MySQL: {error}") from error


def get_connection():
    return get_db_connection()


def batch_size():
    return BATCH_SIZE
