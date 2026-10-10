# Bulk Certificate Generator

## Overview

The Bulk Certificate Generator is a Python backend application that generates PDF certificates for multiple recipients through a single API request.

It allows an organizer to submit recipient details, generate individual certificates, track generation results, check job status, and retrieve certificates individually or as a ZIP archive.

## Features

- Bulk certificate generation from a single request.
- Input validation using FastAPI and Pydantic.
- PDF certificate generation using ReportLab.
- SQLite database for storing jobs and recipient information.
- Recipient-level status tracking (`PENDING`, `SUCCESS`, `FAILED`).
- Job-level status tracking (`PROCESSING`, `COMPLETED`, `PARTIAL`, `FAILED`).
- Individual PDF certificate downloads.
- Bulk ZIP downloads of successfully generated certificates.
- Individual failure handling so one failed certificate does not stop other recipients.
- Automated testing using Pytest.

## Technology Stack

- **Language:** Python
- **Backend framework:** FastAPI
- **Server:** Uvicorn
- **Database:** SQLite
- **PDF generation:** ReportLab
- **Testing:** Pytest and HTTPX

## Project Structure

```text
bulk-certificate-generator/
├── main.py
├── database.py
├── test_main.py
├── README.md
├── .gitignore
└── generated_certificates/
```

The `certificates.db` file is created locally when the application initializes its database. Generated PDF files are stored locally under job-specific folders.

## Setup and Installation

### 1. Clone the repository

```bash
git clone https://github.com/Shivanivnr/bulk-certificate-generator
cd bulk-certificate-generator
```

### 2. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install fastapi "uvicorn[standard]" email-validator reportlab pytest httpx
```

### 4. Start the application

```bash
python -m uvicorn main:app --reload
```

The application runs locally at:

`http://127.0.0.1:8000`

Interactive API documentation is available at:

`http://127.0.0.1:8000/docs`

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Application welcome message |
| POST | `/api/certificates/` | Preview recipient information |
| POST | `/api/certificates/preview/` | Generate a PDF for the first recipient |
| POST | `/api/certificates/bulk/` | Generate PDFs and return a ZIP archive |
| POST | `/api/jobs/` | Create a job and generate certificates |
| GET | `/api/jobs/{job_id}/` | Retrieve job status and counts |
| GET | `/api/jobs/{job_id}/recipients/{recipient_id}/certificate/` | Download an individual PDF |
| GET | `/api/jobs/{job_id}/certificates/` | Download successful certificates as a ZIP |

## Example Request

Submit a POST request to `/api/jobs/`:

```json
{
  "event_name": "Python Workshop",
  "recipients": [
    {
      "name": "Ananya",
      "email": "ananya@example.com"
    },
    {
      "name": "Priya",
      "email": "priya@example.com"
    }
  ]
}
```

The API returns the job ID, job status, total recipient count, and successful and failed certificate counts.

## Job Statuses

- `PENDING`: Job has been created but processing has not started.
- `PROCESSING`: Certificates are being generated.
- `COMPLETED`: All certificates were generated successfully.
- `PARTIAL`: Some certificates succeeded and others failed.
- `FAILED`: No certificates were generated successfully.

The application processes jobs synchronously.

## Running Tests

Run the automated test suite:

```bash
python -m pytest -v
```

The tests cover job creation, input validation, job status, PDF generation, individual and bulk certificate retrieval, and individual certificate-generation failures.

## Architecture and Design Decisions

### Application structure

`main.py` contains the API endpoints and certificate-generation logic. `database.py` manages SQLite connections and initializes the database tables. `test_main.py` contains automated tests.

### File-generation flow

The API validates the request, creates a job and recipient records, generates a PDF for each recipient, stores each result, updates job statistics, and returns the final job status.

### Database design

The application uses two relational tables:

- `jobs`: Stores event details, status, recipient totals, success and failure counts, and creation time.
- `recipients`: Stores recipient details, job association, generation status, certificate filename, and error information.

### Processing strategy

Synchronous processing was selected to keep the implementation straightforward. Each recipient is processed independently, and generation failures are recorded without unnecessarily stopping the remaining recipients.

## Learning Outcomes

This project provides practical experience with REST APIs, Python backend development, request validation, relational databases, PDF generation, file downloads, exception handling, and automated testing.

## Future Scope

- Background processing for very large certificate batches.
- Certificate template customization.
- Authentication and authorization.
- Email delivery of generated certificates.
- Improved logging, monitoring, and deployment.
- Pagination and limits for large requests.
