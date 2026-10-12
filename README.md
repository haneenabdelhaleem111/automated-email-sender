# Automated Email Sender

A Python-based email automation project that sends emails, validates recipient data, stores email records in a database, and exposes API endpoints for managing email operations.

## Features

- Email sending automation
- Recipient data validation
- CSV-based recipient input
- SQLite database integration
- Flask REST API
- Interactive API documentation using Swagger
- Logging and error handling
- Automated scheduling
- Unit and API tests using pytest

## Tech Stack

- Python
- Flask
- SQLite
- Pydantic
- Flasgger / Swagger
- pytest
- python-dotenv
- schedule

## Project Structure

```text
automated_email_sender/
+-- app.py
+-- database.py
+-- email_service.py
+-- logger_config.py
+-- main.py
+-- scheduler.py
+-- schemas.py
+-- validation.py
+-- recipients.example.csv
+-- requirements.txt
+-- tests/
+-- README.md
```

The test files are currently located in the project root.

## Getting Started

### 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd automated_email_sender
```

### 2. Create and activate a virtual environment

Windows PowerShell:

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
py -m pip install -r requirements.txt
```

### 4. Configure environment variables

Create a local `.env` file in the project root. Add the environment variables required by the application, using the names expected by `email_service.py`.

Never commit your `.env` file or real email credentials.

### 5. Run the application

```powershell
py app.py
```

Open the API documentation at:

http://127.0.0.1:5000/apidocs/

### 6. Run tests

```powershell
py -m pytest -v
```

## Recipient CSV Format

Use `recipients.example.csv` as a template. The CSV should contain the required columns, such as:

```csv
name,email
Alex,alex@example.com
Sam,sam@example.com
```

Replace example values with your own data locally. Do not upload private recipient information.

## Security

- Keep credentials in `.env`.
- Do not commit real recipient lists.
- Keep local databases and logs out of version control.

## Status

This project is being developed as a practical Python automation project.
