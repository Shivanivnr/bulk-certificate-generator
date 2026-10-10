
import sqlite3

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Use a separate database for testing
    db_path = tmp_path / "test_certificates.db"

    def test_connection():
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    # Create the tables in the temporary database
    connection = test_connection()

    connection.execute("""
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            total_recipients INTEGER NOT NULL DEFAULT 0,
            successful_count INTEGER NOT NULL DEFAULT 0,
            failed_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE recipients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            certificate_filename TEXT,
            error_message TEXT,
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        )
    """)

    connection.commit()
    connection.close()

    # Make API endpoints use the temporary database
    monkeypatch.setattr(main, "get_connection", test_connection)
    monkeypatch.setattr(
    main, "CERTIFICATE_OUTPUT_DIR", tmp_path / "test_generated"
)
    return TestClient(main.app)


def sample_request():
    return {
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


def test_create_job_and_generate_certificates(client):
    response = client.post("/api/jobs/", json=sample_request())

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["total_recipients"] == 2
    assert data["successful_count"] == 2
    assert data["failed_count"] == 0


def test_invalid_email_is_rejected(client):
    request_data = sample_request()
    request_data["recipients"][0]["email"] = "not-an-email"

    response = client.post("/api/jobs/", json=request_data)

    assert response.status_code == 422


def test_job_status(client):
    created = client.post(
        "/api/jobs/",
        json=sample_request()
    ).json()

    job_id = created["job_id"]

    response = client.get(f"/api/jobs/{job_id}/")

    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    assert response.json()["successful_count"] == 2


def test_individual_certificate_download(client):
    created = client.post(
        "/api/jobs/",
        json=sample_request()
    ).json()

    job_id = created["job_id"]

    connection = main.get_connection()
    try:
        recipient = connection.execute(
            """
            SELECT id FROM recipients
            WHERE job_id = ?
            ORDER BY id LIMIT 1
            """,
            (job_id,)
        ).fetchone()
    finally:
        connection.close()

    response = client.get(
        f"/api/jobs/{job_id}/recipients/"
        f"{recipient['id']}/certificate/"
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_bulk_certificate_download(client):
    created = client.post(
        "/api/jobs/",
        json=sample_request()
    ).json()

    response = client.get(
        f"/api/jobs/{created['job_id']}/certificates/"
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.content.startswith(b"PK")


def test_individual_generation_failure(client, monkeypatch):
    original_generator = main.create_certificate_pdf

    def failing_generator(name, event_name):
        if name == "Ananya":
            raise RuntimeError("Simulated PDF generation failure")

        return original_generator(name, event_name)

    monkeypatch.setattr(
        main,
        "create_certificate_pdf",
        failing_generator
    )

    response = client.post(
        "/api/jobs/",
        json=sample_request()
    )

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "PARTIAL"
    assert data["successful_count"] == 1
    assert data["failed_count"] == 1
