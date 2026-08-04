""""Purpose

Unlike episodic memory, semantic memory stores facts, not events."""
from datetime import datetime

from .config import DEFAULT_FACT_STATUS
from .models import SemanticFact
from .storage import get_memory_connection


class SemanticStore:

    def __init__(self):

        connection = get_memory_connection()

        cursor = connection.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS semantic_memory(

            fact_id INTEGER PRIMARY KEY AUTOINCREMENT,

            entity_id TEXT,

            attribute TEXT,

            value TEXT,

            version INTEGER,

            current INTEGER,

            status TEXT,

            expires_at TEXT,

            updated_from_episode INTEGER,

            created_at TEXT
        )
        """)

        connection.commit()
        connection.close()

    # ----------------------------------------------------

    def get_current_fact(
        self,
        entity_id: str,
        attribute: str
    ):

        connection = get_memory_connection()

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT *

            FROM semantic_memory

            WHERE entity_id=?

            AND attribute=?

            AND current=1
            """,
            (entity_id, attribute)
        )

        row = cursor.fetchone()

        connection.close()

        return row

    # ----------------------------------------------------

    def get_versions(
        self,
        entity_id: str,
        attribute: str
    ):

        connection = get_memory_connection()

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT *

            FROM semantic_memory

            WHERE entity_id=?

            AND attribute=?

            ORDER BY version
            """,
            (entity_id, attribute)
        )

        rows = cursor.fetchall()

        connection.close()

        return rows

    # ----------------------------------------------------

    def deactivate_current(
        self,
        entity_id: str,
        attribute: str
    ):

        connection = get_memory_connection()

        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE semantic_memory

            SET current=0

            WHERE entity_id=?

            AND attribute=?
            AND current=1
            """,
            (
                entity_id,
                attribute
            )
        )

        connection.commit()
        connection.close()

    # ----------------------------------------------------

    def add_fact(self, fact: SemanticFact):

        connection = get_memory_connection()

        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO semantic_memory(

                entity_id,

                attribute,

                value,

                version,

                current,

                status,

                expires_at,

                updated_from_episode,

                created_at

            )

            VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (
                fact.entity_id,

                fact.attribute,

                fact.value,

                fact.version,

                1 if fact.current else 0,

                fact.status,

                fact.expires_at.isoformat()
                if fact.expires_at
                else None,

                fact.updated_from_episode,

                datetime.utcnow().isoformat()
            )
        )

        connection.commit()

        connection.close()

    # ----------------------------------------------------

    def mark_stale(self):

        connection = get_memory_connection()

        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE semantic_memory

            SET status='STALE'

            WHERE expires_at IS NOT NULL

            AND expires_at < datetime('now')

            AND current=1
            """
        )

        connection.commit()

        connection.close()