from fastapi import HTTPException

from pathlib import Path
from io import BytesIO
from fastapi.responses import FileResponse

from database import get_connection, init_db
from zipfile import ZipFile, ZIP_DEFLATED
import re

from io import BytesIO
from datetime import date

from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

CERTIFICATE_OUTPUT_DIR = (
    Path(__file__).resolve().parent / "generated_certificates"
)

app = FastAPI(title="Bulk Certificate Generator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


def create_certificate_pdf(name: str, event_name: str) -> bytes:
    pdf_buffer = BytesIO()
    pdf = canvas.Canvas(pdf_buffer, pagesize=A4)

    width, height = A4

    pdf.setTitle("Certificate of Participation")

    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawCentredString(
        width / 2, height - 120,
        "CERTIFICATE OF PARTICIPATION"
    )

    pdf.setFont("Helvetica", 14)
    pdf.drawCentredString(
        width / 2, height - 190,
        "This certificate is proudly presented to"
    )

    pdf.setFont("Helvetica-Bold", 28)
    pdf.drawCentredString(
        width / 2, height - 245, name
    )

    pdf.setFont("Helvetica", 14)
    pdf.drawCentredString(
        width / 2, height - 300,
        f"for participating in {event_name}"
    )

    pdf.drawCentredString(
        width / 2, height - 360,
        f"Issued on: {date.today()}"
    )

    pdf.save()
    return pdf_buffer.getvalue()


class Recipient(BaseModel):
    name: str
    email: EmailStr


class CertificateRequest(BaseModel):
    event_name: str
    recipients: list[Recipient]


@app.get("/")
def home():
    return {
        "message": "Welcome to the Bulk Certificate Generator!",
        "status": "running"
    }


@app.post("/api/certificates/")
def create_certificate_job(request: CertificateRequest):
    return {
        "message": "Recipient details received successfully",
        "event_name": request.event_name,
        "total_recipients": len(request.recipients),
        "recipients": [
            {
                "name": recipient.name,
                "email": str(recipient.email)
            }
            for recipient in request.recipients
        ]
    }

@app.post("/api/certificates/preview/")
def generate_certificate(request: CertificateRequest):
    # Use the first recipient for our first PDF
    recipient = request.recipients[0]

    # Create a temporary PDF in memory
    pdf_buffer = BytesIO()
    pdf = canvas.Canvas(pdf_buffer, pagesize=A4)

    # Get the dimensions of an A4 page
    width, height = A4

    # Draw the certificate content
    pdf.setTitle("Workshop Certificate")
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawCentredString(
        width / 2, height - 120, "CERTIFICATE OF PARTICIPATION"
    )

    pdf.setFont("Helvetica", 14)
    pdf.drawCentredString(
        width / 2, height - 190, "This certificate is proudly presented to"
    )

    pdf.setFont("Helvetica-Bold", 28)
    pdf.drawCentredString(
        width / 2, height - 245, recipient.name
    )

    pdf.setFont("Helvetica", 14)
    pdf.drawCentredString(
        width / 2, height - 300, f"for participating in {request.event_name}"
    )

    pdf.drawCentredString(
        width / 2, height - 360, f"Issued on: {date.today()}"
    )

    # Finish the PDF
    pdf.save()
    pdf_buffer.seek(0)

    # Return the generated PDF to the client
    filename = "certificate.pdf"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"'
    }

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers=headers
    )

@app.post("/api/certificates/bulk/")
def generate_bulk_certificates(request: CertificateRequest):
    zip_buffer = BytesIO()
    successful_count = 0

    with ZipFile(zip_buffer, "w", ZIP_DEFLATED) as zip_file:
        for index, recipient in enumerate(request.recipients, start=1):
            try:
                # Create a PDF in memory
                pdf_buffer = BytesIO()
                pdf = canvas.Canvas(pdf_buffer, pagesize=A4)

                width, height = A4

                # Add certificate content
                pdf.setTitle("Certificate of Participation")
                pdf.setFont("Helvetica-Bold", 24)
                pdf.drawCentredString(
                    width / 2,
                    height - 120,
                    "CERTIFICATE OF PARTICIPATION"
                )

                pdf.setFont("Helvetica", 14)
                pdf.drawCentredString(
                    width / 2,
                    height - 190,
                    "This certificate is proudly presented to"
                )

                pdf.setFont("Helvetica-Bold", 28)
                pdf.drawCentredString(
                    width / 2,
                    height - 245,
                    recipient.name
                )

                pdf.setFont("Helvetica", 14)
                pdf.drawCentredString(
                    width / 2,
                    height - 300,
                    f"for participating in {request.event_name}"
                )

                pdf.drawCentredString(
                    width / 2,
                    height - 360,
                    f"Issued on: {date.today()}"
                )

                pdf.save()

                # Get the completed PDF bytes
                pdf_bytes = pdf_buffer.getvalue()

                # Create a safe, unique filename
                safe_name = re.sub(
                    r"[^A-Za-z0-9_-]",
                    "_",
                    recipient.name
                )

                filename = f"{index}_{safe_name}.pdf"

                # Add the PDF to the ZIP file
                zip_file.writestr(filename, pdf_bytes)
                successful_count += 1

            except Exception as error:
                # Log the failure; we'll add persistent
                # per-recipient status tracking later.
                print(f"Failed to generate certificate for "
                      f"{recipient.name}: {error}")

    zip_buffer.seek(0)

    headers = {
        "Content-Disposition":
            'attachment; filename="certificates.zip"'
    }

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers=headers
    )


@app.post("/api/jobs/")
def create_job(request: CertificateRequest):
    if not request.recipients:
        raise HTTPException(
            status_code=400,
            detail="At least one recipient is required."
        )

    connection = get_connection()

    try:
        # 1. Create the job and its recipient records
        cursor = connection.execute(
            """
            INSERT INTO jobs (event_name, status, total_recipients)
            VALUES (?, ?, ?)
            """,
            (
                request.event_name,
                "PROCESSING",
                len(request.recipients)
            )
        )

        job_id = cursor.lastrowid

        for recipient in request.recipients:
            connection.execute(
                """
                INSERT INTO recipients (job_id, name, email, status)
                VALUES (?, ?, ?, ?)
                """,
                (job_id, recipient.name, str(recipient.email), "PENDING")
            )

        connection.commit()

        # 2. Prepare a folder for this job's PDF files
        output_dir = CERTIFICATE_OUTPUT_DIR / f"job_{job_id}"
        output_dir.mkdir(parents=True, exist_ok=True)

        # 3. Process each recipient independently
        rows = connection.execute(
            "SELECT * FROM recipients WHERE job_id = ?",
            (job_id,)
        ).fetchall()

        for row in rows:
            try:
                pdf_bytes = create_certificate_pdf(
                    row["name"],
                    request.event_name
                )

                safe_name = re.sub(
                    r"[^A-Za-z0-9_-]",
                    "_",
                    row["name"]
                )[:60] or "recipient"

                filename = f"recipient_{row['id']}_{safe_name}.pdf"
                file_path = output_dir / filename
                file_path.write_bytes(pdf_bytes)

                connection.execute(
                    """
                    UPDATE recipients
                    SET status = ?, certificate_filename = ?,
                        error_message = NULL
                    WHERE id = ?
                    """,
                    ("SUCCESS", str(file_path), row["id"])
                )

            except Exception as error:
                connection.execute(
                    """
                    UPDATE recipients
                    SET status = ?, error_message = ?
                    WHERE id = ?
                    """,
                    ("FAILED", str(error)[:500], row["id"])
                )

            # Save each result so completed work is recorded
            connection.commit()

        # 4. Calculate the final results
        counts = connection.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END)
                    AS successful,
                SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END)
                    AS failed
            FROM recipients
            WHERE job_id = ?
            """,
            (job_id,)
        ).fetchone()

        successful = counts["successful"] or 0
        failed = counts["failed"] or 0

        if failed == 0:
            final_status = "COMPLETED"
        elif successful == 0:
            final_status = "FAILED"
        else:
            final_status = "PARTIAL"

        connection.execute(
            """
            UPDATE jobs
            SET status = ?, successful_count = ?, failed_count = ?
            WHERE id = ?
            """,
            (final_status, successful, failed, job_id)
        )
        connection.commit()

        return {
            "message": "Certificate generation finished",
            "job_id": job_id,
            "event_name": request.event_name,
            "status": final_status,
            "total_recipients": counts["total"],
            "successful_count": successful,
            "failed_count": failed
        }

    finally:
        connection.close()


@app.get("/api/jobs/")
def list_jobs():
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT
                id,
                event_name,
                status,
                total_recipients,
                successful_count,
                failed_count,
                created_at
            FROM jobs
            ORDER BY id DESC
            """
        ).fetchall()

        return [
            {
                "job_id": row["id"],
                "event_name": row["event_name"],
                "status": row["status"],
                "total_recipients": row["total_recipients"],
                "successful_count": row["successful_count"],
                "failed_count": row["failed_count"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]
    finally:
        connection.close()

@app.get("/api/jobs/{job_id}/")
def get_job_status(job_id: int):
    connection = get_connection()

    try:
        # Find the requested job
        job = connection.execute(
            "SELECT * FROM jobs WHERE id = ?",
            (job_id,)
        ).fetchone()

        # Return 404 if the job does not exist
        if job is None:
            raise HTTPException(
                status_code=404,
                detail="Generation job not found"
            )

        # Count the recipient results stored for this job
        counts = connection.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END)
                    AS successful,
                SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END)
                    AS failed
            FROM recipients
            WHERE job_id = ?
            """,
            (job_id,)
        ).fetchone()

        return {
            "job_id": job["id"],
            "event_name": job["event_name"],
            "status": job["status"],
            "total_recipients": counts["total"],
            "successful_count": counts["successful"],
            "failed_count": counts["failed"],
            "created_at": job["created_at"]
        }

    finally:
        connection.close()


@app.get("/api/jobs/{job_id}/recipients/{recipient_id}/certificate/")
def download_certificate(job_id: int, recipient_id: int):
    connection = get_connection()

    try:
        recipient = connection.execute(
            """
            SELECT certificate_filename, name, status
            FROM recipients
            WHERE id = ? AND job_id = ?
            """,
            (recipient_id, job_id)
        ).fetchone()

        if recipient is None:
            raise HTTPException(
                status_code=404,
                detail="Recipient not found in this job"
            )

        if recipient["status"] != "SUCCESS":
            raise HTTPException(
                status_code=404,
                detail="Certificate has not been generated successfully"
            )

        file_path = recipient["certificate_filename"]

        if not file_path or not Path(file_path).is_file():
            raise HTTPException(
                status_code=404,
                detail="Certificate file not found"
            )

        safe_name = re.sub(
            r"[^A-Za-z0-9_-]",
            "_",
            recipient["name"]
        )[:60] or "recipient"

        return FileResponse(
            path=file_path,
            media_type="application/pdf",
            filename=f"{safe_name}_certificate.pdf"
        )

    finally:
        connection.close()


@app.get("/api/jobs/{job_id}/certificates/")
def download_job_certificates(job_id: int):
    connection = get_connection()

    try:
        job = connection.execute(
            "SELECT id FROM jobs WHERE id = ?",
            (job_id,)
        ).fetchone()

        if job is None:
            raise HTTPException(
                status_code=404,
                detail="Generation job not found"
            )

        recipients = connection.execute(
            """
            SELECT id, name, certificate_filename
            FROM recipients
            WHERE job_id = ? AND status = 'SUCCESS'
            ORDER BY id
            """,
            (job_id,)
        ).fetchall()

        zip_buffer = BytesIO()
        included_count = 0

        with ZipFile(zip_buffer, "w", ZIP_DEFLATED) as zip_file:
            for recipient in recipients:
                file_path = recipient["certificate_filename"]

                if not file_path or not Path(file_path).is_file():
                    continue

                safe_name = re.sub(
                    r"[^A-Za-z0-9_-]",
                    "_",
                    recipient["name"]
                )[:60] or "recipient"

                archive_name = (
                    f"recipient_{recipient['id']}_{safe_name}.pdf"
                )

                zip_file.write(file_path, archive_name)
                included_count += 1

        if included_count == 0:
            raise HTTPException(
                status_code=404,
                detail="No generated certificates are available"
            )

        zip_buffer.seek(0)

        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition":
                    f'attachment; filename="job_{job_id}_certificates.zip"'
            }
        )

    finally:
        connection.close()
