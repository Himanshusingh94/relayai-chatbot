import json
import os
import sqlite3
from datetime import datetime, timezone


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")


def get_database_path():
    prefix = "sqlite:///"

    if DATABASE_URL.startswith(prefix):
        return DATABASE_URL[len(prefix):]

    raise ValueError("DATABASE_URL must be a SQLite URL")


def get_connection():
    db_path = get_database_path()

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    return connection


def init_db():
    connection = get_connection()

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata TEXT,
            created_at TEXT NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_messages_session_id
        ON messages(session_id)
        """
    )

    connection.commit()
    connection.close()


def save_message(session_id, role, content, metadata=None):
    connection = get_connection()

    created_at = datetime.now(timezone.utc).isoformat()

    metadata_json = None

    if metadata is not None:
        metadata_json = json.dumps(metadata)

    connection.execute(
        """
        INSERT INTO messages
        (session_id, role, content, metadata, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            session_id,
            role,
            content,
            metadata_json,
            created_at,
        ),
    )

    connection.commit()
    connection.close()


def get_messages(session_id):
    connection = get_connection()

    rows = connection.execute(
        """
        SELECT role, content, metadata
        FROM messages
        WHERE session_id = ?
        ORDER BY id ASC
        """,
        (session_id,),
    ).fetchall()

    connection.close()

    messages = []

    for row in rows:
        message = {
            "role": row["role"],
            "content": row["content"],
        }

        if row["metadata"]:
            message["metadata"] = json.loads(row["metadata"])

        messages.append(message)

    return messages