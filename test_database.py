
import os
import pytest

from database import (
    initialize_database,
    save_email,
    update_email_status,
    get_all_emails,
)
from database import get_email_by_idempotency_key


TEST_DATABASE = "test_emails.db"


@pytest.fixture
def test_db():
    # Remove the previous test database, if it exists
    if os.path.exists(TEST_DATABASE):
        os.remove(TEST_DATABASE)

    # Create a fresh test database
    initialize_database(TEST_DATABASE)

    yield TEST_DATABASE

    # Clean up after the test
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
