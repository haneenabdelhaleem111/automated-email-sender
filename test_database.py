
import os
import pytest
import sqlite3

from database import (
    get_connection,
    database_connection,
    initialize_database,
    save_email,
    save_email_batch,
    update_email_status,
    get_all_emails,
    get_email_by_idempotency_key,
    create_email_batch,
    get_email_batch_by_idempotency_key,
    get_emails_by_batch_id,
    update_email_batch_status,
)


TEST_DATABASE = "test_emails.db"
@pytest.fixture
def test_db():
    if os.path.exists(TEST_DATABASE):
        os.remove(TEST_DATABASE)

    initialize_database(TEST_DATABASE)

    connection = get_connection(TEST_DATABASE)
    try:
        tables = [
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master"
            ).fetchall()
        ]
        print("TABLES AFTER FIXTURE INIT:", tables)
    finally:
        connection.close()

    yield TEST_DATABASE

    if os.path.exists(TEST_DATABASE):
        os.remove(TEST_DATABASE)

def test_save_email(test_db):
    email_id = save_email(
        "test@example.com",
        "Test Subject",
        "Test Body",
        database_name=test_db,
    )

    emails = get_all_emails(database_name=test_db)

    assert len(emails) == 1
    assert emails[0]["id"] == email_id
    assert emails[0]["recipient_email"] == "test@example.com"
    assert emails[0]["status"] == "pending"


def test_update_email_status(test_db):
    email_id = save_email(
        "test@example.com",
        "Test Subject",
        "Test Body",
        database_name=test_db,
    )

    update_email_status(
        email_id,
        "sent",
        database_name=test_db,
    )

    emails = get_all_emails(database_name=test_db)

    assert emails[0]["status"] == "sent"
    assert emails[0]["sent_at"] is not None


def test_get_all_emails_empty_database(test_db):
    emails = get_all_emails(database_name=test_db)

    assert emails == []

def test_find_email_by_idempotency_key(test_db):
    save_email(
        "test@example.com",
        "Test Subject",
        "Test Body",
        database_name=test_db,
        idempotency_key="request-123",
    )

    email = get_email_by_idempotency_key(
        "request-123",
        database_name=test_db,
    )

    assert email is not None
    assert email["idempotency_key"] == "request-123"
    assert email["recipient_email"] == "test@example.com"


def test_duplicate_idempotency_key_is_rejected(test_db):
    save_email(
        "test@example.com",
        "Test Subject",
        "Test Body",
        database_name=test_db,
        idempotency_key="request-123",
    )

    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        save_email(
            "another@example.com",
            "Another Subject",
            "Another Body",
            database_name=test_db,
            idempotency_key="request-123",
        )

    emails = get_all_emails(database_name=test_db)
    assert len(emails) == 1



from database import (
    create_email_batch,
    get_email_batch_by_idempotency_key,
    get_emails_by_batch_id,
    update_email_batch_status,
)


def test_create_and_find_email_batch(test_db):
    batch_id = create_email_batch(
        "Test Subject",
        "Test Body",
        database_name=test_db,
        idempotency_key="batch-123",
    )

    batch = get_email_batch_by_idempotency_key(
        "batch-123",
        database_name=test_db,
    )

    assert batch is not None
    assert batch["id"] == batch_id
    assert batch["subject"] == "Test Subject"
    assert batch["status"] == "pending"


def test_emails_can_be_linked_to_batch(test_db):
    batch_id = create_email_batch(
        "Test Subject",
        "Test Body",
        database_name=test_db,
    )

    save_email(
        "first@example.com",
        "Test Subject",
        "Test Body",
        database_name=test_db,
        batch_id=batch_id,
    )
    save_email(
        "second@example.com",
        "Test Subject",
        "Test Body",
        database_name=test_db,
        batch_id=batch_id,
    )

    emails = get_emails_by_batch_id(
        batch_id,
        database_name=test_db,
    )

    assert len(emails) == 2
    assert emails[0]["batch_id"] == batch_id
    assert emails[1]["batch_id"] == batch_id


def test_update_email_batch_status(test_db):
    batch_id = create_email_batch(
        "Test Subject",
        "Test Body",
        database_name=test_db,
    )

    update_email_batch_status(
        batch_id,
        "sent",
        database_name=test_db,
    )

    with database_connection(test_db) as connection:
        row = connection.execute(
            "SELECT status FROM email_batches WHERE id = ?",
            (batch_id,),
        ).fetchone()

    assert row["status"] == "sent"




def test_save_email_batch_rolls_back_on_recipient_failure(tmp_path):
    test_db = str(tmp_path / "test_rollback.db")
    initialize_database(test_db)

    with sqlite3.connect(test_db) as connection:
        connection.execute("""
            CREATE TRIGGER fail_second_recipient
            BEFORE INSERT ON emails
            WHEN NEW.recipient_email = 'second@example.com'
            BEGIN
                SELECT RAISE(ABORT, 'forced failure');
            END;
        """)

    with pytest.raises(sqlite3.IntegrityError):
        save_email_batch(
            subject="Rollback Test",
            body="Testing transaction rollback",
            recipient_emails=[
                "first@example.com",
                "second@example.com",
            ],
            database_name=test_db,
        )

    with sqlite3.connect(test_db) as connection:
        batch_count = connection.execute(
            "SELECT COUNT(*) FROM email_batches"
        ).fetchone()[0]

        email_count = connection.execute(
            "SELECT COUNT(*) FROM emails"
        ).fetchone()[0]

    assert batch_count == 0
    assert email_count == 0