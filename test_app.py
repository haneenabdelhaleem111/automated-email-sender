
from unittest.mock import patch
from urllib import response

import app as app_module
from unittest.mock import patch

def test_home_endpoint():
    client = app_module.app.test_client()

    response = client.get("/")

    assert response.status_code == 200
    assert response.json["status"] == "success"


def test_get_emails_endpoint():
    client = app_module.app.test_client()

    response = client.get("/api/emails")

    assert response.status_code == 200
    assert response.json["status"] == "success"
    assert "emails" in response.json
    assert "count" in response.json


def test_invalid_email_is_rejected():
    client = app_module.app.test_client()

    payload = {
        "recipient_email": "not-an-email",
        "subject": "Test",
        "body": "Testing invalid email"
    }

    with patch.object(app_module, "send_email") as mock_send:
        response = client.post("/api/emails", json=payload)

    assert response.status_code == 400
    mock_send.assert_not_called()

def test_missing_fields_are_rejected():
    client = app_module.app.test_client()

    payload = {
        "recipient_email": "test@example.com",
        "subject": "",
        "body": "Hello!"
    }

    with patch.object(app_module, "send_email") as mock_send:
        response = client.post("/api/emails", json=payload)

    assert response.status_code == 400
    mock_send.assert_not_called()


def test_invalid_json_body_is_rejected():
    client = app_module.app.test_client()

    response = client.post(
        "/api/emails",
        data="this is not JSON",
        content_type="text/plain"
    )

    assert response.status_code == 400


def test_successful_email_send():
    client = app_module.app.test_client()

    payload = {
        "recipient_email": "test@example.com",
        "subject": "Test Subject",
        "body": "Test message"
    }

    with (
        patch.object(app_module, "send_email") as mock_send,
        patch.object(app_module, "save_email", return_value=123),
        patch.object(app_module, "update_email_status") as mock_update
    ):
        response = client.post("/api/emails", json=payload)

    assert response.status_code == 200
    assert response.json["status"] == "sent"
    assert response.json["email_id"] == 123

    mock_send.assert_called_once()

    mock_update.assert_called_once_with(
        123,
        "sent",
        database_name=app_module.app.config["DATABASE"]
    )


def test_failed_email_send():
    client = app_module.app.test_client()

    payload = {
        "recipient_email": "test@example.com",
        "subject": "Test Subject",
        "body": "Test message"
    }

    with (
        patch.object(app_module, "save_email", return_value=456),
        patch.object(
            app_module,
            "send_email",
            side_effect=Exception("SMTP connection failed")
        ) as mock_send,
        patch.object(app_module, "update_email_status") as mock_update
    ):
        response = client.post("/api/emails", json=payload)

    assert response.status_code == 500
    assert response.json["status"] == "failed"
    assert response.json["email_id"] == 456

    mock_send.assert_called_once()
    mock_update.assert_called_once_with(
        456,
        "failed",
        database_name=app_module.app.config["DATABASE"]
    )

def test_duplicate_request_is_not_sent_twice():
    client = app_module.app.test_client()

    payload = {
        "recipient_email": "test@example.com",
        "subject": "Test Subject",
        "body": "Test message",
    }
    headers = {"Idempotency-Key": "duplicate-test-001"}

    existing_email = {
        "id": 123,
        "recipient_email": payload["recipient_email"],
        "subject": payload["subject"],
        "body": payload["body"],
        "status": "sent",
    }

    with (
        patch.object(
            app_module,
            "get_email_by_idempotency_key",
            return_value=existing_email,
        ),
        patch.object(app_module, "send_email") as mock_send,
        patch.object(app_module, "save_email") as mock_save,
    ):
        response = client.post(
            "/api/emails",
            json=payload,
            headers=headers,
        )

    assert response.status_code == 200
    assert response.json["duplicate"] is True
    assert response.json["email_id"] == 123
    assert response.json["status"] == "sent"

    mock_send.assert_not_called()
    mock_save.assert_not_called()


def test_same_idempotency_key_with_different_data():
    client = app_module.app.test_client()

    payload = {
        "recipient_email": "test@example.com",
        "subject": "Different Subject",
        "body": "Test message",
    }
    headers = {"Idempotency-Key": "duplicate-test-002"}

    existing_email = {
        "id": 124,
        "recipient_email": "test@example.com",
        "subject": "Original Subject",
        "body": "Test message",
        "status": "sent",
    }

    with (
        patch.object(
            app_module,
            "get_email_by_idempotency_key",
            return_value=existing_email,
        ),
        patch.object(app_module, "send_email") as mock_send,
        patch.object(app_module, "save_email") as mock_save,
    ):
        response = client.post(
            "/api/emails",
            json=payload,
            headers=headers,
        )

    assert response.status_code == 409
    mock_send.assert_not_called()
    mock_save.assert_not_called()


def test_new_idempotency_key_sends_email():
    client = app_module.app.test_client()

    payload = {
        "recipient_email": "test@example.com",
        "subject": "New Subject",
        "body": "New message",
    }
    headers = {"Idempotency-Key": "new-request-003"}

    with (
        patch.object(
            app_module,
            "get_email_by_idempotency_key",
            return_value=None,
        ),
        patch.object(
            app_module,
            "save_email",
            return_value=789,
        ) as mock_save,
        patch.object(app_module, "send_email") as mock_send,
        patch.object(app_module, "update_email_status") as mock_update,
    ):
        response = client.post(
            "/api/emails",
            json=payload,
            headers=headers,
        )

    assert response.status_code == 200
    assert response.json["status"] == "sent"
    assert response.json["duplicate"] is False

    mock_save.assert_called_once_with(
        "test@example.com",
        "New Subject",
        "New message",
        database_name=app_module.app.config["DATABASE"],
        idempotency_key="new-request-003",
    )
    mock_send.assert_called_once()
    mock_update.assert_called_once()

def test_failed_status_update_does_not_crash_api():
    client = app_module.app.test_client()

    payload = {
        "recipient_email": "test@example.com",
        "subject": "Test Subject",
        "body": "Test message",
    }

    with (
        patch.object(app_module, "save_email", return_value=901),
        patch.object(
            app_module,
            "send_email",
            side_effect=Exception("SMTP connection failed"),
        ),
        patch.object(
            app_module,
            "update_email_status",
            side_effect=RuntimeError("Database unavailable"),
        ),
    ):
        response = client.post("/api/emails", json=payload)

    assert response.status_code == 500
    assert response.is_json
    assert response.json["email_id"] == 901
    assert response.json["status"] == "failed"


def test_sent_status_update_failure_is_reported_as_unconfirmed():
    client = app_module.app.test_client()

    payload = {
        "recipient_email": "test@example.com",
        "subject": "Test Subject",
        "body": "Test message",
    }

    with (
        patch.object(app_module, "save_email", return_value=902),
        patch.object(app_module, "send_email") as mock_send,
        patch.object(
            app_module,
            "update_email_status",
            side_effect=RuntimeError("Database unavailable"),
        ),
    ):
        response = client.post("/api/emails", json=payload)

    assert response.status_code == 500
    assert response.json["email_id"] == 902
    assert response.json["status"] == "sent_status_unconfirmed"
    mock_send.assert_called_once()

def test_empty_idempotency_key_is_rejected():
    client = app_module.app.test_client()

    payload = {
        "recipient_email": "test@example.com",
        "subject": "Test Subject",
        "body": "Test message",
    }

    with (
        patch.object(app_module, "save_email") as mock_save,
        patch.object(app_module, "send_email") as mock_send,
    ):
        response = client.post(
            "/api/emails",
            json=payload,
            headers={"Idempotency-Key": "   "},
        )

    assert response.status_code == 400
    mock_save.assert_not_called()
    mock_send.assert_not_called()


def test_idempotency_key_over_200_characters_is_rejected():
    client = app_module.app.test_client()

    payload = {
        "recipient_email": "test@example.com",
        "subject": "Test Subject",
        "body": "Test message",
    }

    with (
        patch.object(app_module, "save_email") as mock_save,
        patch.object(app_module, "send_email") as mock_send,
    ):
        response = client.post(
            "/api/emails",
            json=payload,
            headers={"Idempotency-Key": "a" * 201},
        )

    assert response.status_code == 400
    mock_save.assert_not_called()
    mock_send.assert_not_called()

def test_successful_bulk_email_send():
    client = app_module.app.test_client()

    payload = {
        "recipient_emails": [
            "first@example.com",
            "second@example.com",
        ],
        "subject": "Bulk Test",
        "body": "Testing bulk email",
    }

    bulk_results = [
        {
            "recipient_email": "first@example.com",
            "status": "sent",
            "error": None,
        },
        {
            "recipient_email": "second@example.com",
            "status": "sent",
            "error": None,
        },
    ]

    with (
        patch.object(
            app_module,
            "save_email_batch",
            return_value=(100, [201, 202]),
        ) as mock_save_batch,
        patch.object(
            app_module,
            "send_bulk_email_request",
            return_value=bulk_results,
        ) as mock_send_bulk,
        patch.object(
            app_module,
            "update_email_status",
        ) as mock_update_email,
        patch.object(
            app_module,
            "update_email_batch_status",
        ) as mock_update_batch,
    ):
        response = client.post("/api/emails", json=payload)

    assert response.status_code == 200
    assert response.json["status"] == "sent"
    assert response.json["batch_id"] == 100
    assert response.json["total"] == 2
    assert response.json["sent"] == 2
    assert response.json["failed"] == 0

    mock_save_batch.assert_called_once_with(
        subject="Bulk Test",
        body="Testing bulk email",
        recipient_emails=[
            "first@example.com",
            "second@example.com",
        ],
        database_name=app_module.app.config["DATABASE"],
        idempotency_key=None,
    )

    mock_send_bulk.assert_called_once_with(
        payload["recipient_emails"],
        "Bulk Test",
        "Testing bulk email",
    )

    assert mock_update_email.call_count == 2
    mock_update_batch.assert_called_once_with(
        100,
        "sent",
        database_name=app_module.app.config["DATABASE"],
    )


def test_bulk_email_partial_failure():
    client = app_module.app.test_client()

    payload = {
        "recipient_emails": [
            "first@example.com",
            "second@example.com",
        ],
        "subject": "Bulk Test",
        "body": "Testing partial failure",
    }

    bulk_results = [
        {
            "recipient_email": "first@example.com",
            "status": "sent",
            "error": None,
        },
        {
            "recipient_email": "second@example.com",
            "status": "failed",
            "error": "SMTP connection failed",
        },
    ]

    with (
        patch.object(
            app_module,
            "save_email_batch",
            return_value=(101, [301, 302]),
        ) as mock_save_batch,
        patch.object(
            app_module,
            "send_bulk_email_request",
            return_value=bulk_results,
        ),
        patch.object(
            app_module,
            "update_email_status",
        ) as mock_update_email,
        patch.object(
            app_module,
            "update_email_batch_status",
        ) as mock_update_batch,
    ):
        response = client.post("/api/emails", json=payload)

    assert response.status_code == 207
    assert response.json["status"] == "partial_failed"
    assert response.json["total"] == 2
    assert response.json["sent"] == 1
    assert response.json["failed"] == 1

    assert response.json["recipients"][0]["status"] == "sent"
    assert response.json["recipients"][1]["status"] == "failed"

    assert mock_update_email.call_count == 2
    mock_update_batch.assert_called_once_with(
        101,
        "partial_failed",
        database_name=app_module.app.config["DATABASE"],
    )


def test_bulk_email_duplicate_request_is_not_resent():
    client = app_module.app.test_client()

    payload = {
        "recipient_emails": [
            "first@example.com",
            "second@example.com",
        ],
        "subject": "Bulk Idempotency Test",
        "body": "Testing duplicate prevention",
    }

    existing_batch = {
        "id": 200,
        "subject": "Bulk Idempotency Test",
        "body": "Testing duplicate prevention",
        "status": "sent",
    }

    existing_emails = [
        {
            "id": 401,
            "recipient_email": "first@example.com",
            "status": "sent",
        },
        {
            "id": 402,
            "recipient_email": "second@example.com",
            "status": "sent",
        },
    ]

    headers = {"Idempotency-Key": "bulk-test-key-001"}

    with (
        patch.object(
            app_module,
            "get_email_batch_by_idempotency_key",
            return_value=existing_batch,
        ),
        patch.object(
            app_module,
            "get_emails_by_batch_id",
            return_value=existing_emails,
        ),
        patch.object(
            app_module,
            "create_email_batch",
        ) as mock_create_batch,
        patch.object(
            app_module,
            "send_bulk_email_request",
        ) as mock_send_bulk,
    ):
        response = client.post(
            "/api/emails",
            json=payload,
            headers=headers,
        )

    assert response.status_code == 200
    assert response.json["duplicate"] is True
    assert response.json["status"] == "sent"
    assert response.json["batch_id"] == 200

    mock_create_batch.assert_not_called()
    mock_send_bulk.assert_not_called()



def test_bulk_email_same_key_with_different_data_returns_conflict():
    client = app_module.app.test_client()

    payload = {
        "recipient_emails": [
            "different@example.com",
        ],
        "subject": "Changed Subject",
        "body": "Changed body",
    }

    existing_batch = {
        "id": 200,
        "subject": "Original Subject",
        "body": "Original body",
        "status": "sent",
    }

    headers = {"Idempotency-Key": "bulk-test-key-001"}

    with (
        patch.object(
            app_module,
            "get_email_batch_by_idempotency_key",
            return_value=existing_batch,
        ),
        patch.object(
            app_module,
            "get_emails_by_batch_id",
            return_value=[
                {
                    "id": 401,
                    "recipient_email": "first@example.com",
                    "status": "sent",
                },
                {
                    "id": 402,
                    "recipient_email": "second@example.com",
                    "status": "sent",
                },
            ],
        ),
        patch.object(
            app_module,
            "create_email_batch",
        ) as mock_create_batch,
        patch.object(
            app_module,
            "send_bulk_email_request",
        ) as mock_send_bulk,
    ):
        response = client.post(
            "/api/emails",
            json=payload,
            headers=headers,
        )

    assert response.status_code == 409
    assert "already used" in response.json["error"]

    mock_create_batch.assert_not_called()
    mock_send_bulk.assert_not_called()



def test_bulk_email_all_recipients_fail():
    client = app_module.app.test_client()

    payload = {
        "recipient_emails": [
            "first@example.com",
            "second@example.com",
        ],
        "subject": "Bulk Failure Test",
        "body": "Testing total failure",
    }

    bulk_results = [
        {
            "recipient_email": "first@example.com",
            "status": "failed",
            "error": "SMTP connection failed",
        },
        {
            "recipient_email": "second@example.com",
            "status": "failed",
            "error": "SMTP connection failed",
        },
    ]

    with (
        patch.object(
            app_module,
            "save_email_batch",
            return_value=(102, [501, 502]),
        ) as mock_save_batch,
        patch.object(
            app_module,
            "send_bulk_email_request",
            return_value=bulk_results,
        ),
        patch.object(
            app_module,
            "update_email_status",
        ) as mock_update_email,
        patch.object(
            app_module,
            "update_email_batch_status",
        ) as mock_update_batch,
    ):
        response = client.post("/api/emails", json=payload)

    assert response.status_code == 500
    assert response.json["status"] == "failed"
    assert response.json["total"] == 2
    assert response.json["sent"] == 0
    assert response.json["failed"] == 2

    assert all(
        recipient["status"] == "failed"
        for recipient in response.json["recipients"]
    )

    assert mock_update_email.call_count == 2
    mock_update_batch.assert_called_once_with(
        102,
        "failed",
        database_name=app_module.app.config["DATABASE"],
    )


def test_bulk_email_rejects_more_than_150_recipients():
    client = app_module.app.test_client()

    payload = {
        "recipient_emails": [
            f"user{i}@example.com"
            for i in range(151)
        ],
        "subject": "Bulk Limit Test",
        "body": "Testing recipient limit",
    }

    with patch.object(
        app_module,
        "send_bulk_email_request",
    ) as mock_send_bulk:
        response = client.post("/api/emails", json=payload)

    assert response.status_code == 400
    mock_send_bulk.assert_not_called()


def test_bulk_email_rejects_duplicate_recipients():
    client = app_module.app.test_client()

    payload = {
        "recipient_emails": [
            "first@example.com",
            "FIRST@example.com",
        ],
        "subject": "Duplicate Recipient Test",
        "body": "Testing duplicate recipients",
    }

    with patch.object(
        app_module,
        "send_bulk_email_request",
    ) as mock_send_bulk:
        response = client.post("/api/emails", json=payload)

    assert response.status_code == 400
    mock_send_bulk.assert_not_called()


def test_bulk_email_stops_sending_if_saving_recipient_fails():
    client = app_module.app.test_client()

    payload = {
        "recipient_emails": [
            "first@example.com",
            "second@example.com",
        ],
        "subject": "Database Failure Test",
        "body": "Testing database save failure",
    }

    with (
        patch.object(
            app_module,
            "save_email_batch",
            side_effect=Exception("Database write failed"),
        ) as mock_save_batch,
        patch.object(
            app_module,
            "send_bulk_email_request",
        ) as mock_send_bulk,
    ):
        response = client.post("/api/emails", json=payload)

    assert response.status_code == 500
    assert response.json["error"] == (
        "Could not save the batch recipients"
    )

    mock_save_batch.assert_called_once()
    mock_send_bulk.assert_not_called()

import pytest


@pytest.fixture(autouse=True)
def use_test_database(tmp_path):
    original_database = app_module.app.config["DATABASE"]
    test_database = str(tmp_path / "test_emails.db")

    app_module.app.config["DATABASE"] = test_database
    app_module.database.initialize_database(test_database)

    yield

    app_module.app.config["DATABASE"] = original_database



def test_bulk_email_rejects_mismatched_result_count():
    client = app_module.app.test_client()

    payload = {
        "recipient_emails": [
            "first@example.com",
            "second@example.com",
        ],
        "subject": "Bulk Test",
        "body": "Testing result count mismatch",
    }

    # Two recipients were saved, but only one result was returned.
    with (
        patch.object(
            app_module,
            "save_email_batch",
            return_value=(103, [601, 602]),
        ),
        patch.object(
            app_module,
            "send_bulk_email_request",
            return_value=[
                {
                    "recipient_email": "first@example.com",
                    "status": "sent",
                    "error": None,
                },
            ],
        ) as mock_send_bulk,
        patch.object(
            app_module,
            "update_email_status",
        ) as mock_update_email,
        patch.object(
            app_module,
            "update_email_batch_status",
        ) as mock_update_batch,
    ):
        response = client.post("/api/emails", json=payload)

    assert response.status_code == 500
    mock_send_bulk.assert_called_once()

    assert mock_update_email.call_count == 2
    mock_update_email.assert_any_call(
        601,
        "sent",
        database_name=app_module.app.config["DATABASE"],
    )
    mock_update_email.assert_any_call(
        602,
        "unknown",
        database_name=app_module.app.config["DATABASE"],
    )

    mock_update_batch.assert_called_once_with(
        103,
        "sending_status_unconfirmed",
        database_name=app_module.app.config["DATABASE"],
    )



def test_bulk_unknown_status_is_saved_and_not_resent():
    client = app_module.app.test_client()
    idempotency_key = "unknown-delivery-test-001"

    payload = {
        "recipient_emails": [
            "first@example.com",
            "second@example.com",
        ],
        "subject": "Unknown Status Test",
        "body": "Testing persisted delivery status",
    }

    with (
        patch.object(
            app_module,
            "send_bulk_email_request",
            return_value=[
                {
                    "recipient_email": "first@example.com",
                    "status": "sent",
                    "error": None,
                },
            ],
        ) as mock_send_bulk,
    ):
        response = client.post(
            "/api/emails",
            json=payload,
            headers={"Idempotency-Key": idempotency_key},
        )

        assert response.status_code == 500

        batch_id = response.get_json()["batch_id"]

        emails = app_module.get_emails_by_batch_id(
            batch_id,
            database_name=app_module.app.config["DATABASE"],
        )

        batch = app_module.get_email_batch_by_idempotency_key(
            idempotency_key,
            database_name=app_module.app.config["DATABASE"],
        )

        assert [email["status"] for email in emails] == [
            "sent",
            "unknown",
        ]
        assert batch["status"] == "sending_status_unconfirmed"

        # Repeating the same request must not send the emails again.
        duplicate_response = client.post(
            "/api/emails",
            json=payload,
            headers={"Idempotency-Key": idempotency_key},
        )

        assert duplicate_response.status_code == 409
        assert duplicate_response.get_json()["duplicate"] is True
        mock_send_bulk.assert_called_once()



def test_bulk_unexpected_exception_marks_status_unconfirmed():
    client = app_module.app.test_client()

    payload = {
        "recipient_emails": [
            "first@example.com",
            "second@example.com",
        ],
        "subject": "Unexpected Error Test",
        "body": "Testing uncertain bulk sending",
    }

    with (
        patch.object(
            app_module,
            "send_bulk_email_request",
            side_effect=RuntimeError("Unexpected sending error"),
        ) as mock_send,
    ):
        response = client.post(
            "/api/emails",
            json=payload,
            headers={
                "Idempotency-Key": "unexpected-bulk-error-001",
            },
        )

    assert response.status_code == 500

    data = response.get_json()
    assert data["status"] == "sending_status_unconfirmed"
    assert data["batch_id"] is not None

    emails = app_module.get_emails_by_batch_id(
        data["batch_id"],
        database_name=app_module.app.config["DATABASE"],
    )

    assert len(emails) == 2
    assert all(
        email["status"] == "unknown"
        for email in emails
    )

    batch = app_module.get_email_batch_by_idempotency_key(
        "unexpected-bulk-error-001",
        database_name=app_module.app.config["DATABASE"],
    )

    assert batch["status"] == "sending_status_unconfirmed"
    mock_send.assert_called_once()



def test_bulk_status_update_failure_is_reported_as_unconfirmed():
    client = app_module.app.test_client()

    payload = {
        "recipient_emails": [
            "first@example.com",
            "second@example.com",
        ],
        "subject": "Status Update Failure Test",
        "body": "Testing bulk status update failure",
    }

    send_results = [
        {
            "email": "first@example.com",
            "status": "sent",
        },
        {
            "email": "second@example.com",
            "status": "sent",
        },
    ]

    with (
        patch.object(
            app_module,
            "send_bulk_email_request",
            return_value=send_results,
        ) as mock_send,
        patch.object(
            app_module,
            "update_email_status",
            side_effect=RuntimeError("Database status update failed"),
        ),
    ):
        response = client.post(
            "/api/emails",
            json=payload,
            headers={
                "Idempotency-Key": "bulk-status-update-failure-001",
            },
        )

    assert response.status_code == 500

    data = response.get_json()
    assert data["status"] == "status_update_failed"
    assert data["batch_id"] is not None

    batch = app_module.get_email_batch_by_idempotency_key(
        "bulk-status-update-failure-001",
        database_name=app_module.app.config["DATABASE"],
    )

    assert batch["status"] == "status_update_failed"
    mock_send.assert_called_once()
