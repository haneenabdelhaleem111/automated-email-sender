import os
import smtplib
import csv
from email.message import EmailMessage #for the email
from dotenv import load_dotenv
#load contacts from .env file
from validation import validate_recipient
from datetime import datetime
from scheduler import schedule_email_job

load_dotenv()

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

def send_email(receiver_email, subject, body):
    message = EmailMessage()
    message["From"] = SENDER_EMAIL
    message["To"] = receiver_email
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
            # server.set_debuglevel(1)
            print("Step 1: Connecting...")
            server.ehlo()

            print("Step 2: Starting TLS...")
            server.starttls()

            print("Step 3: Checking server capabilities...")
            server.ehlo()

            print("Step 4: Logging in...")
            server.login(SENDER_EMAIL, SENDER_PASSWORD)

            print("Step 5: Sending email...")
            server.send_message(message)

            print("Email sent successfully!")

    except (smtplib.SMTPException, OSError) as error:
        print(f"Email failed: {type(error).__name__}: {error}")


def load_recipients(filename):
    recipients = []

    with open(filename, "r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            recipients.append(row)

    return recipients


def process_recipients(recipients):
    valid_recipients = []
    invalid_recipients = []
    seen_emails = set()

    for recipient in recipients:
        errors = validate_recipient(recipient)

        email = recipient.get("email", "").strip().lower()

        if errors:
            invalid_recipients.append({
                "recipient": recipient,
                "errors": errors
            })

        elif email in seen_emails:
            invalid_recipients.append({
                "recipient": recipient,
                "errors": ["Duplicate email address"]
            })

        else:
            seen_emails.add(email)
            valid_recipients.append(recipient)

    return valid_recipients, invalid_recipients


def send_scheduled_emails(recipients, subject, body):
    for recipient in recipients:
        name = recipient["name"].strip()
        email = recipient["email"].strip()

        personalized_body = f"Hello {name}!\n\n{body}"

        send_email(
            receiver_email=email,
            subject=subject,
            body=personalized_body
        )


if __name__ == "__main__":
    recipients = load_recipients("recipients.csv")

    valid_recipients, invalid_recipients = process_recipients(
        recipients
    )

    print(f"\nValid recipients: {len(valid_recipients)}")
    print(f"Invalid recipients: {len(invalid_recipients)}")

    for item in invalid_recipients:
        print(
            f"Recipient: {item['recipient']}"
        )
        print(f"Errors: {', '.join(item['errors'])}")

    if not valid_recipients:
        print("No valid recipients found. No emails were scheduled.")

    else:
        subject = input("\nEnter email subject: ")
        body = input("Enter email body: ")

        date_input = input("Enter the date (YYYY-MM-DD): ")
        time_input = input("Enter the time (HH:MM): ")

        try:
            scheduled_datetime = datetime.strptime(
                f"{date_input} {time_input}",
                "%Y-%m-%d %H:%M"
            )

            schedule_email_job(
                lambda: send_scheduled_emails(
                    valid_recipients,
                    subject,
                    body
                ),
                scheduled_datetime
            )

        except ValueError:
            print("Invalid date or time format.")
