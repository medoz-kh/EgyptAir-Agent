""""Purpose

Instead of opening SQLite connections everywhere, every memory component will call one helper.

This follows the Single Responsibility Principle."""
import sqlite3

from .config import MEMORY_DB


def get_memory_connection() -> sqlite3.Connection:

    MEMORY_DB.parent.mkdir(exist_ok=True)

    connection = sqlite3.connect(MEMORY_DB)

    connection.row_factory = sqlite3.Row

    return connection