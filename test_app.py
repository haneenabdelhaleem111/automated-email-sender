
from unittest.mock import patch

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



import pytest


@pytest.fixture(autouse=True)
def use_test_database(tmp_path):
    original_database = app_module.app.config["DATABASE"]
    test_database = str(tmp_path / "test_emails.db")

    app_module.app.config["DATABASE"] = test_database
    app_module.database.initialize_database(test_database)

    yield

    app_module.app.config["DATABASE"] = original_database
