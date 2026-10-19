# Automated Email Sender

A full-stack email automation application that combines **Python-based email processing** with a **React dashboard** to simplify sending, scheduling, and tracking emails.

The application provides a web interface for composing emails, sending messages to multiple recipients, scheduling future deliveries, and reviewing email history. A Flask REST API handles backend operations, while SQLite stores email records and delivery statuses.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Running the Application](#running-the-application)
- [API Documentation](#api-documentation)
- [Running Tests](#running-tests)
- [Security](#security)
- [Future Improvements](#future-improvements)

## Overview

The Automated Email Sender was built to make email automation more accessible through an interactive web application.

Instead of relying exclusively on command-line scripts, users can interact with a dashboard to manage email operations while the backend handles validation, delivery, persistence, and scheduling.

The project brings together frontend development, backend API design, database management, and Python automation in one practical application.

## Features

### Email Management

- **Single email delivery:** Compose and send an email through the dashboard.
- **Multiple recipients:** Send emails to multiple recipients through a bulk-email workflow.
- **Email scheduling:** Schedule messages for future delivery.
- **Time validation:** Reject scheduling requests for past dates and times.
- **Email history:** Review recorded emails and their statuses through the dashboard.
- **Delivery feedback:** Display success and validation messages to help users understand the outcome of an operation.

### Backend and Automation

- **Flask REST API:** Provides endpoints for email operations and communication with the frontend.
- **SMTP integration:** Handles email delivery through an SMTP server.
- **Input validation:** Validates email addresses and request data before processing.
- **SQLite persistence:** Stores email records and related delivery information.
- **Structured request validation:** Uses Pydantic schemas to validate incoming API data.
- **Logging and error handling:** Records operational information and errors to support debugging.
- **Duplicate-request protection:** Supports idempotency keys for applicable email requests.
- **API documentation:** Provides interactive API documentation through Swagger.
- **Automated testing:** Uses pytest to test backend functionality and API behavior.

## Tech Stack

| Layer | Technologies |
|---|---|
| Frontend | React, JavaScript, CSS |
| Backend | Python, Flask |
| API | REST API, JSON |
| Email Automation | SMTP |
| Database | SQLite |
| Validation | Pydantic |
| API Documentation | Flasgger / Swagger |
| Testing | pytest |
| Configuration | Environment variables, python-dotenv |

## Architecture

The application follows a frontend-backend architecture:

1. **React frontend:** Provides the dashboard, email composition interface, scheduling forms, and history views.
2. **Flask backend:** Receives API requests, validates input, coordinates email operations, and returns responses.
3. **Email service:** Handles SMTP-based message delivery.
4. **SQLite database:** Persists email records and delivery statuses.
5. **Scheduling component:** Supports future email delivery through the project's scheduling workflow.

This separation keeps the user interface independent from the backend logic and makes the application easier to maintain and extend.

## Project Structure

```text
automated-email-sender/
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── ...
├── app.py
├── database.py
├── email_service.py
├── logger_config.py
├── main.py
├── scheduler.py
├── schemas.py
├── validation.py
├── recipients.example.csv
├── requirements.txt
├── test_app.py
├── test_database.py
├── test_email_service.py
├── test_logger.py
├── test_schema.py
├── .gitignore
└── README.md
```

*Note: The structure above highlights the main application files. Additional scheduling or worker files may be present in newer local versions.*

## Getting Started

### Prerequisites

Make sure you have the following installed:

- Python 3
- Node.js and npm
- Git
- SMTP account credentials for sending email

### 1. Clone the Repository

```bash
git clone https://github.com/haneenabdelhaleem111/automated-email-sender.git
cd automated-email-sender
```

### 2. Set Up the Backend

Create a virtual environment:

**Windows PowerShell**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the Python dependencies:

```powershell
py -m pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a local `.env` file in the backend project root.

Add the SMTP credentials and any other configuration required by the application. Use the exact environment variable names referenced in `email_service.py`.

Keep all credentials private. Never commit real passwords, SMTP credentials, or API secrets to GitHub.

### 4. Set Up the Frontend

Open a separate terminal in the frontend directory:

```powershell
cd frontend
npm install
```

Create or update the local frontend environment configuration, if required by the application:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:5000
```

This value points the frontend to the local Flask API. Update it if your backend uses a different address or port.

## Running the Application

Run the backend and frontend in **separate terminals**.

### Terminal 1: Start the Flask Backend

From the project root, with the virtual environment activated:

```powershell
py app.py
```

The API should be available at:

```text
http://127.0.0.1:5000
```

You can verify the API is running by opening the root URL in your browser. The application should return a successful health-check response.

### Terminal 2: Start the React Frontend

From the `frontend` directory:

```powershell
npm run dev
```

Open the local URL printed by Vite in the terminal.

You can then explore the dashboard, compose emails, use the bulk-email workflow, schedule messages, and review the available history views.

**Important:** If scheduled delivery depends on a separate worker or scheduler process in your current version, start that process as documented by its entry point. Scheduling a message and executing it at the scheduled time are separate operations.

## API Documentation

The Flask backend uses Flasgger to expose interactive API documentation.

With the backend running, visit:

[http://127.0.0.1:5000/apidocs/](http://127.0.0.1:5000/apidocs/)

The documented API includes email operations such as:

- Submitting email requests
- Retrieving recorded emails
- Validating request data
- Handling delivery errors and duplicate requests

Refer to the running Swagger documentation for the current endpoints, request schemas, and response formats.

## Running Tests

With the backend virtual environment activated, run:

```powershell
py -m pytest -v
```

The test suite covers backend components such as API behavior, database operations, email-service logic, logging, and schema validation.

Run the tests after making changes to verify that existing functionality continues to work.

## Security

The project follows several basic security practices:

- Store credentials in local environment variables rather than hardcoding them.
- Keep `.env` files out of version control.
- Do not upload real recipient lists or private email data.
- Keep local databases and sensitive logs out of the public repository.
- Validate incoming data before processing requests.
- Avoid retrying an email blindly when the delivery outcome is uncertain.

Before publishing updates, verify that no credentials or sensitive data have been committed to the repository or its Git history.

## Future Improvements

Potential next steps include:

- Deployment with environment-specific configuration.
- Improved background scheduling and retry management.
- Enhanced delivery monitoring and reporting.
- Additional automated tests for scheduling workflows.
- More detailed operational logs and status tracking.

## Project Status

This is a portfolio project demonstrating full-stack development and Python automation. It is intended to run locally with the required backend, frontend, and email-service configuration.

The project is not presented as a production-hosted service.

## Author

**Haneen Abdelhaleem**

[GitHub Repository](https://github.com/haneenabdelhaleem111/automated-email-sender)
