
import os
import smtplib
import time
from email.message import EmailMessage

from dotenv import load_dotenv
from logger_config import logger

load_dotenv()

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")


def send_email(receiver_email, subject, body, max_retries=3):
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        raise RuntimeError("Email credentials are not configured.")

    if (
        not isinstance(max_retries, int)
        or isinstance(max_retries, bool)
        or max_retries < 1
    ):
        raise ValueError("max_retries must be a positive integer.")

    message = EmailMessage()
    message["From"] = SENDER_EMAIL
    message["To"] = receiver_email
    message["Subject"] = subject
    message.set_content(body)

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                "Sending email attempt %s of %s to %s",
                attempt,
                max_retries,
                receiver_email,
            )

            with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.send_message(message)

            logger.info("Email sent successfully to %s", receiver_email)
            return

        except (smtplib.SMTPAuthenticationError,
                smtplib.SMTPRecipientsRefused):
            logger.exception(
                "Permanent email error for %s; retry will not be attempted",
                receiver_email,
            )
            raise

        except smtplib.SMTPResponseException as error:
            if not 400 <= error.smtp_code < 500:
                logger.exception(
                    "Permanent SMTP response %s for %s",
                    error.smtp_code,
                    receiver_email,
                )
                raise

            retryable_error = error

        except (smtplib.SMTPException, OSError) as error:
            retryable_error = error

        if attempt == max_retries:
            logger.error(
                "Email sending failed after %s attempts to %s",
                max_retries,
                receiver_email,
                exc_info=(
                    type(retryable_error),
                    retryable_error,
                    retryable_error.__traceback__,
                ),
            )
            raise retryable_error

        delay = 2 ** attempt

        logger.warning(
            "Email attempt %s failed for %s. Retrying in %s seconds. Error: %s",
            attempt,
            receiver_email,
            delay,
            retryable_error,
        )

        time.sleep(delay)


def send_bulk_emails(recipient_emails, subject, body):
    results = []

    for recipient_email in recipient_emails:
        try:
            send_email(
                receiver_email=str(recipient_email),
                subject=subject,
                body=body,
            )
            results.append({
                "recipient_email": str(recipient_email),
                "status": "sent",
                "error": None,
            })

        except Exception as error:
            logger.exception(
                "Bulk email sending failed for %s",
                recipient_email,
            )
            results.append({
                "recipient_email": str(recipient_email),
                "status": "failed",
                "error": str(error),
            })

    return results
