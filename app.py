import os
import database
import smtplib
import sqlite3

from flask import Flask, jsonify, request
from validation import validate_email
from email_service import send_email
from pydantic import ValidationError
from schemas import EmailRequest
from logger_config import logger
from flasgger import Swagger

from database import (
    initialize_database,
    save_email,
    update_email_status,
    get_all_emails,
    get_email_by_idempotency_key,
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
        examples:
          application/json:
            message: API is running
    """
    return jsonify({
        "message": "Automated Email Sender API is running!",
        "status": "success"
    })


@app.route("/api/emails", methods=["POST"])
def create_email():
    
    """
    Validate, save, and send an email.
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
          required:
            - recipient_email
            - subject
            - body
          properties:
            recipient_email:
              type: string
              example: patient@example.com
            subject:
              type: string
              example: Pharmacy Order Confirmation
            body:
              type: string
              example: Your pharmacy order has been received.
    responses:
      200:
        description: Email sent successfully or an existing sent request was recognized.
      400:
        description: Invalid JSON, missing fields, or invalid email data.
      409:
        description: Idempotency key conflict or request already being processed.
      500:
        description: Email sending failed or the final status could not be confirmed.
    """

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "Request body must be a JSON object"
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

    recipient_email = str(email_data.recipient_email).strip()
    subject = email_data.subject.strip()
    body = email_data.body.strip()

    if not recipient_email or not subject or not body:
        return jsonify({
            "error": "Email, subject, and body are required"
        }), 400

    if not validate_email(recipient_email):
        return jsonify({
            "error": "Invalid email address"
        }), 400

    # Optional for backward compatibility.
    # Clients should send this header to prevent duplicate processing.
    idempotency_key = request.headers.get(
        "Idempotency-Key"
    )

    if idempotency_key is not None:
        idempotency_key = idempotency_key.strip()

        if not idempotency_key or len(idempotency_key) > 200:
            return jsonify({
                "error": "Idempotency-Key must contain 1-200 characters"
            }), 400

    database_name = app.config["DATABASE"]

    # If this key already exists, inspect the original request.
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
                    "error": "Idempotency-Key was already used with different data"
                }), 409

            if existing_email["status"] == "sent":
                return jsonify({
                    "message": "This request was already processed",
                    "status": "sent",
                    "email_id": existing_email["id"],
                    "recipient_email": recipient_email,
                    "duplicate": True,
                }), 200

            # Do not automatically retry pending or failed sends.
            return jsonify({
                "message": "This request already exists and was not resent",
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
        # Another concurrent request may have inserted this key.
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
                "error": "Idempotency-Key was already used with different data"
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
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            count:
              type: integer
              example: 2
            emails:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                    example: 1
                  recipient_email:
                    type: string
                    example: patient@example.com
                  subject:
                    type: string
                    example: Pharmacy Order Confirmation
                  status:
                    type: string
                    example: sent
      500:
        description: An internal server error occurred.
    """

    emails = get_all_emails(database_name=app.config["DATABASE"])

    return jsonify({
        "status": "success",
        "count": len(emails),
        "emails": emails
    }), 200




if __name__ == "__main__":
    app.run(debug=True)
