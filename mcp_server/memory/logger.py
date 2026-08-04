""""Purpose

Every router decision must be inspectable.

This creates the routing log table automatically."""
import json
from datetime import datetime

from .storage import get_memory_connection


class RoutingLogger:

    def __init__(self):

        connection = get_memory_connection()

        cursor = connection.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS routing_logs(

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            timestamp TEXT,

            original_message TEXT,

            decision TEXT,

            reasoning TEXT,

            entity_id TEXT
        )
        """)

        connection.commit()
        connection.close()

    def log(
        self,
        message: str,
        decision: str,
        reasoning: str,
        entity_id: str | None = None
    ):

        connection = get_memory_connection()

        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO routing_logs(
                timestamp,
                original_message,
                decision,
                reasoning,
                entity_id
            )
            VALUES(?,?,?,?,?)
            """,
            (
                datetime.utcnow().isoformat(),
                message,
                decision,
                reasoning,
                entity_id
            )
        )

        connection.commit()
        connection.close()

    def export_json(self, path="memory/routing_logs.json"):

        connection = get_memory_connection()

        cursor = connection.cursor()

        cursor.execute("SELECT * FROM routing_logs")

        rows = [dict(r) for r in cursor.fetchall()]

        connection.close()

        with open(path, "w", encoding="utf8") as file:
            json.dump(rows, file, indent=4)