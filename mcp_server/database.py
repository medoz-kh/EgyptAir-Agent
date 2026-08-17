import sqlite3
import os

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.abspath(os.path.join(SERVER_DIR, "..", "db", "database.db"))

def get_connection():
    """
    Create and return a SQLite connection.
    """

    connection = sqlite3.connect(DB_PATH)

    connection.row_factory = sqlite3.Row

    return connection