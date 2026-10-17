
import os
import database
import smtplib
import sqlite3

from flask import Flask, jsonify, request
from validation import validate_email
from email_service import send_email, send_bulk_emails
from pydantic import ValidationError
from schemas import EmailRequest
from logger_config import logger
from flasgger import Swagger

from database import (
    initialize_database,
    save_email,
    save_email_batch,
    update_email_status,
    get_all_emails,
    get_email_by_idempotency_key,
    create_email_batch,
    get_email_batch_by_idempotency_key,
    get_emails_by_batch_id,
    update_email_batch_status,
)

app = Flask(__name__)
app.config["DATABASE"] = database.DATABASE_NAME
swagger = Swagger(app)
database.initialize_database(app.config["DATABASE"])


@app.route("/", methods=["GET"])
def home():
    """
    Check if the API is running.
    ---
    tags:
      - Health Check
    responses:
      200:
        description: API is running successfully
    """
    return jsonify({
        "message": "Automated Email Sender API is running!",
        "status": "success",
    }), 200


@app.route("/api/emails", methods=["POST"])
def create_email():
    """
    Validate, save, and send an email or a bulk email batch.
    ---
    tags:
      - Emails
    parameters:
      - in: header
        name: Idempotency-Key
        type: string
        required: false
        description: Optional unique key to prevent duplicate processing.
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            recipient_email:
              type: string
              example: patient@example.com
            recipient_emails:
              type: array
              items:
                type: string
              example:
                - first@example.com
                - second@example.com
            subject:
              type: string
              example: Pharmacy Order Confirmation
            body:
              type: string
              example: Your pharmacy order has been received.
    responses:
      200:
        description: Email or batch processed successfully.
      207:
        description: Batch partially failed.
      400:
        description: Invalid request data.
      409:
        description: Idempotency conflict or existing request.
      500:
        description: Sending or status update failed.
    """

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "Request body must be a JSON object",
        }), 400

    try:
        email_data = EmailRequest.model_validate(data)
    except ValidationError as error:
        return jsonify({
            "error": "Invalid email data",
            "details": error.errors(
                include_url=False,
                include_input=False,
                include_context=False,
            ),
        }), 400

    recipient_email = (
        str(email_data.recipient_email).strip()
        if email_data.recipient_email is not None
        else None
    )

    recipient_emails = (
        [str(email).strip() for email in email_data.recipient_emails]
        if email_data.recipient_emails
        else None
    )

    subject = email_data.subject.strip()
    body = email_data.body.strip()

    if not subject or not body:
        return jsonify({
            "error": "Subject and body are required",
        }), 400

    if recipient_email and not validate_email(recipient_email):
        return jsonify({
            "error": "Invalid email address",
        }), 400

    if recipient_emails:
        invalid_emails = [
            email for email in recipient_emails
            if not validate_email(email)
        ]

        if invalid_emails:
            return jsonify({
                "error": "One or more email addresses are invalid",
                "invalid_emails": invalid_emails,
            }), 400

    idempotency_key = request.headers.get("Idempotency-Key")

    if idempotency_key is not None:
        idempotency_key = idempotency_key.strip()

        if not idempotency_key or len(idempotency_key) > 200:
            return jsonify({
                "error": "Idempotency-Key must contain 1-200 characters",
            }), 400

    database_name = app.config["DATABASE"]

    # Handle bulk email requests.
    if recipient_emails:
        existing_batch = None

        if idempotency_key:
            existing_batch = get_email_batch_by_idempotency_key(
                idempotency_key,
                database_name=database_name,
            )

        if existing_batch is not None:
            existing_emails = get_emails_by_batch_id(
                existing_batch["id"],
                database_name=database_name,
            )

            same_recipients = [
                email["recipient_email"].casefold()
                for email in existing_emails
            ] == [
                email.casefold()
                for email in recipient_emails
            ]

            same_payload = (
                existing_batch["subject"] == subject
                and existing_batch["body"] == body
                and same_recipients
            )

            if not same_payload:
                return jsonify({
                    "error": (
                        "Idempotency-Key was already used "
                        "with different data"
                    ),
                }), 409

            if (
                existing_emails
                and all(
                    email["status"] == "sent"
                    for email in existing_emails
                )
            ):
                return jsonify({
                    "message": "This batch was already processed",
                    "status": "sent",
                    "batch_id": existing_batch["id"],
                    "duplicate": True,
                    "recipients": existing_emails,
                }), 200

            return jsonify({
                "message": (
                    "This batch already exists and was not resent"
                ),
                "status": existing_batch["status"],
                "batch_id": existing_batch["id"],
                "duplicate": True,
            }), 409

        # Save the batch and all recipients in one transaction.
        try:
            batch_id, email_ids = save_email_batch(
                subject=subject,
                body=body,
                recipient_emails=recipient_emails,
                database_name=database_name,
                idempotency_key=idempotency_key,
            )

        except sqlite3.IntegrityError:
            if not idempotency_key:
                raise

            return jsonify({
                "error": (
                    "This Idempotency-Key already exists. "
                    "Retry the request to retrieve its status."
                ),
            }), 409

        except Exception:
            logger.exception("Could not save bulk email batch")

            return jsonify({
                "error": "Could not save the batch recipients",
            }), 500

        # Send one separate email to each recipient.
        try:
            results = send_bulk_email_request(
                recipient_emails,
                subject,
                body,
            )
        except Exception:
            # Sending may have partially completed before the exception.
            # Mark all recipients as uncertain and never resend automatically.
            logger.exception(
                "Unexpected error during bulk email sending. "
                "Batch ID: %s",
                batch_id,
            )

            status_update_failed = False

            for email_id in email_ids:
                try:
                    update_email_status(
                        email_id,
                        "unknown",
                        database_name=database_name,
                    )
                except Exception:
                    status_update_failed = True
                    logger.exception(
                        "Could not mark email ID %s as unknown",
                        email_id,
                    )

            batch_status = (
                "status_update_failed"
                if status_update_failed
                else "sending_status_unconfirmed"
            )

            try:
                update_email_batch_status(
                    batch_id,
                    batch_status,
                    database_name=database_name,
                )
            except Exception:
                status_update_failed = True
                logger.exception(
                    "Could not update status for batch ID %s",
                    batch_id,
                )

            return jsonify({
                "error": (
                    "Bulk sending stopped unexpectedly. "
                    "Some emails may have been sent. "
                    "Do not retry blindly."
                ),
                "batch_id": batch_id,
                "status": (
                    "status_update_failed"
                    if status_update_failed
                    else "sending_status_unconfirmed"
                ),
                "duplicate": False,
            }), 500



        # Validate the result collection before processing it.
        if not isinstance(results, list):
            logger.error(
                "Bulk sender returned an invalid result type: %s",
                type(results).__name__,
            )
            results = []

        if len(results) != len(email_ids):
            logger.error(
                "Bulk result count mismatch: expected %s, received %s",
                len(email_ids),
                len(results),
            )

        sent_count = 0
        failed_count = 0
        unknown_count = 0
        recipient_results = []

        for index, email_id in enumerate(email_ids):
            expected_recipient = str(recipient_emails[index])

            result = (
                results[index]
                if index < len(results)
                else None
            )

            # A missing or invalid result does not prove delivery failed.
            if (
                not isinstance(result, dict)
                or result.get("recipient_email") != expected_recipient
                or result.get("status") not in ("sent", "failed")
            ):
                logger.error(
                    "Missing or invalid result for email ID %s, "
                    "recipient %s",
                    email_id,
                    expected_recipient,
                )
                status = "unknown"
                error = (
                    "Missing or invalid sending result. "
                    "Delivery status is unconfirmed. "
                    "Do not retry blindly."
                )
            else:
                status = result["status"]
                error = result.get("error")

            try:
                update_email_status(
                    email_id,
                    status,
                    database_name=database_name,
                )

            except Exception:
                logger.exception(
                    "Could not update status for email ID %s",
                    email_id,
                )

                try:
                    update_email_batch_status(
                        batch_id,
                        "status_update_failed",
                        database_name=database_name,
                    )
                except Exception:
                    logger.exception(
                        "Could not mark batch ID %s as "
                        "status_update_failed",
                        batch_id,
                    )

                return jsonify({
                    "error": (
                        "One or more email statuses could not be saved. "
                        "Some emails may have been sent. "
                        "Do not retry blindly."
                    ),
                    "batch_id": batch_id,
                    "status": "status_update_failed",
                }), 500


            if status == "sent":
                sent_count += 1
            elif status == "failed":
                failed_count += 1
            else:
                unknown_count += 1

            recipient_results.append({
                "email_id": email_id,
                "recipient_email": expected_recipient,
                "status": status,
                "error": error,
            })

        # Unconfirmed delivery takes precedence over ordinary failures.
        if unknown_count > 0:
            batch_status = "sending_status_unconfirmed"
        elif failed_count == 0:
            batch_status = "sent"
        elif sent_count == 0:
            batch_status = "failed"
        else:
            batch_status = "partial_failed"

        try:
            update_email_batch_status(
                batch_id,
                batch_status,
                database_name=database_name,
            )
        except Exception:
            logger.exception(
                "Could not update status for batch ID %s",
                batch_id,
            )

            return jsonify({
                "error": (
                    "Recipient results were processed, but the batch "
                    "status could not be saved."
                ),
                "batch_id": batch_id,
                "status": "status_update_failed",
                "sent": sent_count,
                "failed": failed_count,
                "unknown": unknown_count,
            }), 500

        if unknown_count > 0:
            response_status = 500
        elif failed_count == 0:
            response_status = 200
        elif sent_count == 0:
            response_status = 500
        else:
            response_status = 207

        return jsonify({
            "message": "Bulk email processing completed",
            "batch_id": batch_id,
            "status": batch_status,
            "total": len(recipient_emails),
            "sent": sent_count,
            "failed": failed_count,
            "unknown": unknown_count,
            "duplicate": False,
            "recipients": recipient_results,
        }), response_status

    # Single-email requests require a recipient_email.
    if not recipient_email:
        return jsonify({
            "error": "recipient_email is required for a single email",
        }), 400

    # Check whether this single request was already processed.
    if idempotency_key:
        existing_email = get_email_by_idempotency_key(
            idempotency_key,
            database_name=database_name,
        )

        if existing_email is not None:
            same_payload = (
                existing_email["recipient_email"] == recipient_email
                and existing_email["subject"] == subject
                and existing_email["body"] == body
            )

            if not same_payload:
                return jsonify({
                    "error": (
                        "Idempotency-Key was already used "
                        "with different data"
                    ),
                }), 409

            if existing_email["status"] == "sent":
                return jsonify({
                    "message": "This request was already processed",
                    "status": "sent",
                    "email_id": existing_email["id"],
                    "recipient_email": recipient_email,
                    "duplicate": True,
                }), 200

            return jsonify({
                "message": (
                    "This request already exists and was not resent"
                ),
                "status": existing_email["status"],
                "email_id": existing_email["id"],
                "duplicate": True,
            }), 409

    try:
        email_id = save_email(
            recipient_email,
            subject,
            body,
            database_name=database_name,
            idempotency_key=idempotency_key,
        )
    except sqlite3.IntegrityError:
        if not idempotency_key:
            raise

        existing_email = get_email_by_idempotency_key(
            idempotency_key,
            database_name=database_name,
        )

        if existing_email is None:
            raise

        same_payload = (
            existing_email["recipient_email"] == recipient_email
            and existing_email["subject"] == subject
            and existing_email["body"] == body
        )

        if not same_payload:
            return jsonify({
                "error": (
                    "Idempotency-Key was already used "
                    "with different data"
                ),
            }), 409

        return jsonify({
            "message": "This request already exists",
            "status": existing_email["status"],
            "email_id": existing_email["id"],
            "duplicate": True,
        }), 409

    try:
        send_email(
            receiver_email=recipient_email,
            subject=subject,
            body=body,
        )
    except Exception:
        logger.exception(
            "Email sending failed. Email ID: %s",
            email_id,
        )

        try:
            update_email_status(
                email_id,
                "failed",
                database_name=database_name,
            )
        except Exception:
            logger.exception(
                "Could not update email status to failed. Email ID: %s",
                email_id,
            )

        return jsonify({
            "error": "Failed to send email",
            "email_id": email_id,
            "status": "failed",
        }), 500

    try:
        update_email_status(
            email_id,
            "sent",
            database_name=database_name,
        )
    except Exception:
        logger.exception(
            "Email may have been sent, but its status update failed. "
            "Email ID: %s",
            email_id,
        )

        return jsonify({
            "error": (
                "Email may have been sent, but its status "
                "could not be saved. Do not retry blindly."
            ),
            "email_id": email_id,
            "status": "sent_status_unconfirmed",
        }), 500

    logger.info("Email sent successfully. Email ID: %s", email_id)

    return jsonify({
        "message": "Email sent successfully",
        "status": "sent",
        "email_id": email_id,
        "recipient_email": recipient_email,
        "duplicate": False,
    }), 200


@app.route("/api/emails", methods=["GET"])
def list_emails():
    """
    Retrieve all recorded emails.
    ---
    tags:
      - Emails
    responses:
      200:
        description: List of recorded emails retrieved successfully.
    """

    emails = get_all_emails(
        database_name=app.config["DATABASE"],
    )

    return jsonify({
        "status": "success",
        "count": len(emails),
        "emails": emails,
    }), 200


def send_bulk_email_request(recipient_emails, subject, body):
    """Send one separate email to each recipient."""
    return send_bulk_emails(
        recipient_emails=recipient_emails,
        subject=subject,
        body=body,
    )


if __name__ == "__main__":
    app.run(debug=True)
