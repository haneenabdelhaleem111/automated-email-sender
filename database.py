
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
            CREATE TABLE IF NOT EXISTS email_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                idempotency_key TEXT UNIQUE
            )
        """)

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

        if "batch_id" not in columns:
            connection.execute("""
                ALTER TABLE emails
                ADD COLUMN batch_id INTEGER
                REFERENCES email_batches(id)
            """)
        if "scheduled_at" not in columns:
            connection.execute("""
                ALTER TABLE emails
                ADD COLUMN scheduled_at TEXT
            """)
        connection.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_emails_idempotency_key
            ON emails(idempotency_key)
        """)


def create_email_batch(
    subject,
    body,
    database_name=None,
    idempotency_key=None,
):
    with database_connection(database_name) as connection:
        cursor = connection.execute("""
            INSERT INTO email_batches (
                subject,
                body,
                idempotency_key
            )
            VALUES (?, ?, ?)
        """, (subject, body, idempotency_key))

        return cursor.lastrowid


def get_email_batch_by_idempotency_key(
    idempotency_key,
    database_name=None,
):
    with database_connection(database_name) as connection:
        row = connection.execute("""
            SELECT id, subject, body, status, created_at,
                   idempotency_key
            FROM email_batches
            WHERE idempotency_key = ?
        """, (idempotency_key,)).fetchone()

        return dict(row) if row else None


def update_email_batch_status(batch_id, status, database_name=None):
    with database_connection(database_name) as connection:
        connection.execute("""
            UPDATE email_batches
            SET status = ?
            WHERE id = ?
        """, (status, batch_id))


def save_email(
    recipient_email,
    subject,
    body,
    database_name=None,
    idempotency_key=None,
    batch_id=None,
    scheduled_at=None,
):
    with database_connection(database_name) as connection:
        cursor = connection.execute("""
            INSERT INTO emails (
                recipient_email,
                subject,
                body,
                idempotency_key,
                batch_id,
                scheduled_at,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            recipient_email,
            subject,
            body,
            idempotency_key,
            batch_id,
            scheduled_at,
            "scheduled" if scheduled_at else "pending",
        ))

        return cursor.lastrowid

def get_email_by_idempotency_key(
    idempotency_key,
    database_name=None,
):
    with database_connection(database_name) as connection:
            row = connection.execute("""
        SELECT id, recipient_email, subject, body,
                status, created_at, sent_at, scheduled_at,
                idempotency_key, batch_id
            FROM emails
            WHERE idempotency_key = ?
        """, (idempotency_key,)).fetchone()

    return dict(row) if row else None


def get_emails_by_batch_id(batch_id, database_name=None):
    with database_connection(database_name) as connection:
              rows = connection.execute("""
            SELECT id, recipient_email, subject, body,
                   status, created_at, sent_at, scheduled_at,
                   idempotency_key, batch_id
            FROM emails
            WHERE batch_id = ?
            ORDER BY id
        """, (batch_id,)).fetchall()

    return [dict(row) for row in rows]


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
                   status, created_at, sent_at, scheduled_at,
                   idempotency_key, batch_id
            FROM emails
            ORDER BY id DESC
        """).fetchall()

    return [dict(row) for row in rows]


def save_email_batch(
    subject,
    body,
    recipient_emails,
    database_name=None,
    idempotency_key=None,
    scheduled_at=None,
):
    with database_connection(database_name) as connection:
        batch_status = "scheduled" if scheduled_at else "pending"

        cursor = connection.execute(
            """
            INSERT INTO email_batches (
                subject,
                body,
                status,
                idempotency_key
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                subject,
                body,
                batch_status,
                idempotency_key,
            ),
        )

        batch_id = cursor.lastrowid
        email_ids = []

        email_status = "scheduled" if scheduled_at else "pending"

        for recipient_email in recipient_emails:
            cursor = connection.execute(
                """
                INSERT INTO emails (
                    recipient_email,
                    subject,
                    body,
                    batch_id,
                    scheduled_at,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    recipient_email,
                    subject,
                    body,
                    batch_id,
                    scheduled_at,
                    email_status,
                ),
            )

            email_ids.append(cursor.lastrowid)

        return batch_id, email_ids


def save_scheduled_email(
    recipient_email,
    subject,
    body,
    scheduled_at,
    database_name=None,
    idempotency_key=None,
    batch_id=None,
):
    if not scheduled_at:
        raise ValueError("scheduled_at is required")

    return save_email(
        recipient_email=recipient_email,
        subject=subject,
        body=body,
        database_name=database_name,
        idempotency_key=idempotency_key,
        batch_id=batch_id,
        scheduled_at=scheduled_at,
    )


def get_due_scheduled_emails(database_name=None):
    with database_connection(database_name) as connection:
        rows = connection.execute("""
            SELECT
                id,
                recipient_email,
                subject,
                body,
                scheduled_at,
                status
            FROM emails
            WHERE status = 'scheduled'
              AND scheduled_at IS NOT NULL
              AND scheduled_at <= strftime(
                  '%Y-%m-%dT%H:%M:%f+00:00',
                  'now'
              )
            ORDER BY scheduled_at ASC, id ASC
        """).fetchall()

        return [dict(row) for row in rows]


def claim_due_scheduled_emails(database_name=None, limit=20):
    """Atomically claim due scheduled emails for one worker."""

    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit must be a positive integer")

    with database_connection(database_name) as connection:
        # Lock the database for this transaction before selecting rows.
        connection.execute("BEGIN IMMEDIATE")

        rows = connection.execute("""
            SELECT
                id,
                recipient_email,
                subject,
                body,
                scheduled_at
            FROM emails
            WHERE status = 'scheduled'
              AND scheduled_at IS NOT NULL
              AND scheduled_at <= strftime(
                  '%Y-%m-%dT%H:%M:%f+00:00',
                  'now'
              )
            ORDER BY scheduled_at ASC, id ASC
            LIMIT ?
        """, (limit,)).fetchall()

        claimed = []

        for row in rows:
            cursor = connection.execute("""
                UPDATE emails
                SET status = 'sending'
                WHERE id = ?
                  AND status = 'scheduled'
            """, (row["id"],))

            if cursor.rowcount == 1:
                item = dict(row)
                item["status"] = "sending"
                claimed.append(item)

        return claimed
