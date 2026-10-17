
from unittest.mock import patch

import pytest
import smtplib

import email_service


@patch("email_service.time.sleep")
@patch("email_service.smtplib.SMTP")
def test_email_retries_and_then_succeeds(mock_smtp, mock_sleep):
    mock_server = mock_smtp.return_value.__enter__.return_value

    mock_server.send_message.side_effect = [
        smtplib.SMTPException("Temporary error"),
        smtplib.SMTPException("Temporary error"),
        None,
    ]

    with (
        patch.object(email_service, "SENDER_EMAIL", "sender@example.com"),
        patch.object(email_service, "SENDER_PASSWORD", "fake-password"),
    ):
        email_service.send_email(
            "receiver@example.com",
            "Test",
            "Hello",
        )

    assert mock_smtp.call_count == 3
    assert mock_server.send_message.call_count == 3
    assert mock_sleep.call_count == 2


@patch("email_service.time.sleep")
@patch("email_service.smtplib.SMTP")
def test_email_raises_after_all_retries_fail(mock_smtp, mock_sleep):
    mock_server = mock_smtp.return_value.__enter__.return_value
    mock_server.send_message.side_effect = smtplib.SMTPException(
        "Temporary error"
    )

    with (
        patch.object(email_service, "SENDER_EMAIL", "sender@example.com"),
        patch.object(email_service, "SENDER_PASSWORD", "fake-password"),
        pytest.raises(smtplib.SMTPException),
    ):
        email_service.send_email(
            "receiver@example.com",
            "Test",
            "Hello",
        )

    assert mock_smtp.call_count == 3
    assert mock_server.send_message.call_count == 3
    assert mock_sleep.call_count == 2


from unittest.mock import patch

import email_service


@patch("email_service.time.sleep")
@patch("email_service.smtplib.SMTP")
@patch("email_service.logger")
def test_retry_logs_are_recorded(mock_logger, mock_smtp, mock_sleep):
    mock_server = mock_smtp.return_value.__enter__.return_value

    mock_server.send_message.side_effect = [
        smtplib.SMTPException("Temporary error"),
        None,
    ]

    with (
        patch.object(email_service, "SENDER_EMAIL", "sender@example.com"),
        patch.object(email_service, "SENDER_PASSWORD", "fake-password"),
    ):
        email_service.send_email(
            "receiver@example.com",
            "Test",
            "Hello",
        )

    assert mock_logger.info.call_count == 3
    mock_logger.warning.assert_called_once()
    mock_logger.exception.assert_not_called()



@patch("email_service.smtplib.SMTP")
def test_email_does_not_retry_authentication_failure(mock_smtp):
    mock_server = mock_smtp.return_value.__enter__.return_value
    mock_server.login.side_effect = smtplib.SMTPAuthenticationError(
        535, b"Authentication failed"
    )

    with (
        patch.object(email_service, "SENDER_EMAIL", "sender@example.com"),
        patch.object(email_service, "SENDER_PASSWORD", "fake-password"),
        pytest.raises(smtplib.SMTPAuthenticationError),
    ):
        email_service.send_email(
            "receiver@example.com",
            "Test",
            "Hello",
        )

    assert mock_smtp.call_count == 1
    mock_server.login.assert_called_once()
    mock_server.send_message.assert_not_called()


@pytest.mark.parametrize("invalid_retries", [0, -1, 1.5, True, "3"])
@patch("email_service.smtplib.SMTP")
def test_email_rejects_invalid_max_retries(mock_smtp, invalid_retries):
    with (
        patch.object(email_service, "SENDER_EMAIL", "sender@example.com"),
        patch.object(email_service, "SENDER_PASSWORD", "fake-password"),
        pytest.raises(ValueError, match="max_retries"),
    ):
        email_service.send_email(
            "receiver@example.com",
            "Test",
            "Hello",
            max_retries=invalid_retries,
        )

    mock_smtp.assert_not_called()


def test_bulk_email_continues_when_one_recipient_fails():
    recipients = [
        "first@example.com",
        "second@example.com",
        "third@example.com",
    ]

    with patch.object(
        email_service,
        "send_email",
        side_effect=[
            None,
            RuntimeError("Temporary test failure"),
            None,
        ],
    ) as mock_send:
        results = email_service.send_bulk_emails(
            recipients,
            "Bulk Test",
            "Hello everyone",
        )

    assert mock_send.call_count == 3
    assert [result["status"] for result in results] == [
        "sent",
        "failed",
        "sent",
    ]
    assert [result["recipient_email"] for result in results] == recipients
    assert results[1]["error"] == "Temporary test failure"


def test_bulk_email_returns_empty_list_for_no_recipients():
    with patch.object(email_service, "send_email") as mock_send:
        results = email_service.send_bulk_emails(
            [],
            "Bulk Test",
            "Hello everyone",
        )

    assert results == []
    mock_send.assert_not_called()
