
import pytest
from pydantic import ValidationError

from schemas import EmailRequest


def test_valid_email_request():
    data = {
        "recipient_email": "test@example.com",
        "subject": "Meeting Reminder",
        "body": "Hello! This is a test.",
    }

    email = EmailRequest(**data)

    assert str(email.recipient_email) == "test@example.com"
    assert email.subject == "Meeting Reminder"
    assert email.body == "Hello! This is a test."


def test_invalid_email_is_rejected():
    data = {
        "recipient_email": "not-an-email",
        "subject": "Meeting Reminder",
        "body": "Hello!",
    }

    with pytest.raises(ValidationError):
        EmailRequest(**data)


@pytest.mark.parametrize(
    "field",
    ["subject", "body"],
)
def test_empty_required_text_is_rejected(field):
    data = {
        "recipient_email": "test@example.com",
        "subject": "Meeting Reminder",
        "body": "Hello!",
    }
    data[field] = ""

    with pytest.raises(ValidationError):
        EmailRequest(**data)
