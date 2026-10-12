
import sqlite3
from contextlib import contextmanager

DATABASE_NAME = "emails.db"


@contextmanager
def database_connection(database_name=None):
    connection = get_connection(database_name)

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_connection(database_name=None):
    if database_name is None:
        database_name = DATABASE_NAME

    connection = sqlite3.connect(database_name)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(database_name=None):
    with database_connection(database_name) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient_email TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sent_at TIMESTAMP,
                idempotency_key TEXT
            )
        """)

        # Add the column if the database already existed
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(emails)"
            ).fetchall()
        }

        if "idempotency_key" not in columns:
            connection.execute("""
                ALTER TABLE emails
                ADD COLUMN idempotency_key TEXT
            """)

        # Non-null keys must be unique; multiple NULL values are allowed
        connection.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_emails_idempotency_key
            ON emails(idempotency_key)
        """)


def save_email(
    recipient_email,
    subject,
    body,
    database_name=None,
    idempotency_key=None,
):
    with database_connection(database_name) as connection:
        cursor = connection.execute("""
            INSERT INTO emails (
                recipient_email,
                subject,
                body,
                idempotency_key
            )
            VALUES (?, ?, ?, ?)
        """, (
            recipient_email,
            subject,
            body,
            idempotency_key,
        ))

        return cursor.lastrowid


def get_email_by_idempotency_key(
    idempotency_key,
    database_name=None,
):
    with database_connection(database_name) as connection:
        row = connection.execute("""
            SELECT id, recipient_email, subject, body,
                   status, created_at, sent_at, idempotency_key
            FROM emails
            WHERE idempotency_key = ?
        """, (idempotency_key,)).fetchone()

        return dict(row) if row else None


def update_email_status(email_id, status, database_name=None):
    with database_connection(database_name) as connection:
        if status == "sent":
            connection.execute("""
                UPDATE emails
                SET status = ?, sent_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, email_id))
        else:
            connection.execute("""
                UPDATE emails
                SET status = ?
                WHERE id = ?
            """, (status, email_id))


def get_all_emails(database_name=None):
    with database_connection(database_name) as connection:
        rows = connection.execute("""
            SELECT id, recipient_email, subject, body,
                   status, created_at, sent_at, idempotency_key
            FROM emails
            ORDER BY id DESC
        """).fetchall()

        return [dict(row) for row in rows]
