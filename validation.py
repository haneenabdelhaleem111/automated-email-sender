import re


def validate_email(email):
    if not email:
        return False

    email = email.strip()

    pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

    return re.fullmatch(pattern, email) is not None


def validate_recipient(recipient):
    errors = []

    name = recipient.get("name", "").strip()
    email = recipient.get("email", "").strip()

    if not name:
        errors.append("Name is missing")

    if not email:
        errors.append("Email is missing")
    elif not validate_email(email):
        errors.append("Invalid email format")

    return errors
