
import time

import database
from email_service import send_email
from logger_config import logger


POLL_INTERVAL_SECONDS = 2
BATCH_SIZE = 20


def process_due_emails():
    """Claim due emails and attempt to send each one."""
    emails = database.claim_due_scheduled_emails(
        database_name=database.DATABASE_NAME,
        limit=BATCH_SIZE,
    )

    processed = 0

    for email in emails:
        email_id = email["id"]

        try:
            send_email(
                receiver_email=email["recipient_email"],
                subject=email["subject"],
                body=email["body"],
            )

        except Exception:
            logger.exception(
                "Scheduled email sending failed. Email ID: %s",
                email_id,
            )

            try:
                database.update_email_status(
                    email_id,
                    "failed",
                    database_name=database.DATABASE_NAME,
                )
            except Exception:
                logger.exception(
                    "Could not update failed status for email ID: %s",
                    email_id,
                )

            continue

        try:
            database.update_email_status(
                email_id,
                "sent",
                database_name=database.DATABASE_NAME,
            )

            logger.info(
                "Scheduled email sent successfully. Email ID: %s",
                email_id,
            )
            processed += 1

        except Exception:
            logger.exception(
                "Email may have been sent, but its status update failed. "
                "Email ID: %s. Manual review is required; do not resend blindly.",
                email_id,
            )

    return processed


def run_worker():
    """Poll the database until the worker is stopped."""
    logger.info("Scheduled email worker started.")

    while True:
        try:
            process_due_emails()
        except Exception:
            logger.exception("Unexpected scheduled worker error.")

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_worker()
