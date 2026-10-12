
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
