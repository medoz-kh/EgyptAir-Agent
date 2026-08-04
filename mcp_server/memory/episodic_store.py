""""Purpose

Stores promoted memories.

The router writes ONLY here"""
from .models import Episode
from .storage import get_memory_connection


class EpisodicStore:

    def __init__(self):

        connection = get_memory_connection()

        cursor = connection.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS episodes(

            episode_id INTEGER PRIMARY KEY AUTOINCREMENT,

            entity_id TEXT,

            timestamp TEXT,

            event_summary TEXT,

            context TEXT,

            outcome TEXT,

            conversation_id TEXT
        )
        """)

        connection.commit()
        connection.close()

    def add_episode(self, episode: Episode):

        connection = get_memory_connection()

        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO episodes(

                entity_id,

                timestamp,

                event_summary,

                context,

                outcome,

                conversation_id

            )
            VALUES(?,?,?,?,?,?)
            """,
            (
                episode.entity_id,
                episode.timestamp.isoformat(),
                episode.event_summary,
                episode.context,
                episode.outcome,
                episode.conversation_id
            )
        )

        connection.commit()
        connection.close()

    def get_all(self):

        connection = get_memory_connection()

        cursor = connection.cursor()

        cursor.execute("SELECT * FROM episodes")

        rows = cursor.fetchall()

        connection.close()

        return rows

    def get_by_entity(self, entity_id: str):

        connection = get_memory_connection()

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM episodes
            WHERE entity_id=?
            """,
            (entity_id,)
        )

        rows = cursor.fetchall()

        connection.close()

        return rows