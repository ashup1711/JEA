"""Export emails to CSV and JSON formats."""

import csv
import json
import logging
import sys
from io import StringIO
from pathlib import Path

from jea.db import list_emails
from jea.models import Email

logger = logging.getLogger("jea.exporter")


def _email_to_dict(email: Email) -> dict[str, str | int | float | list[str] | None]:
    """Convert Email model to dictionary for export.

    Args:
        email: Email model instance.

    Returns:
        Dictionary representation of the email.
    """
    return {
        "message_id": email.message_id,
        "thread_id": email.thread_id,
        "subject": email.subject,
        "sender": email.sender,
        "to": email.to,
        "date": email.date.isoformat(),
        "email_type": email.email_type.value,
        "status": email.status.value,
        "company": email.extracted.company,
        "role": email.extracted.role,
        "interview_datetime": email.extracted.interview_datetime.isoformat()
        if email.extracted.interview_datetime
        else None,
        "platform": email.extracted.platform,
        "meeting_link": email.extracted.meeting_link,
        "jd_link": email.extracted.jd_link,
        "labels": email.labels,
        "created_at": email.created_at.isoformat(),
    }


def export_to_json(
    db_path: str,
    output: str | None = None,
    email_type: str | None = None,
    status: str | None = None,
) -> None:
    """Export emails to JSON format.

    Args:
        db_path: Path to the SQLite database.
        output: Output file path. If None, writes to stdout.
        email_type: Filter by email type.
        status: Filter by status.
    """
    emails = list_emails(db_path, email_type=email_type, status=status, limit=10000)
    data = [_email_to_dict(e) for e in emails]

    json_str = json.dumps(data, indent=2, default=str)

    if output:
        Path(output).write_text(json_str)
        logger.info("Exported %d emails to %s", len(data), output)
    else:
        sys.stdout.write(json_str + "\n")


def export_to_csv(
    db_path: str,
    output: str | None = None,
    email_type: str | None = None,
    status: str | None = None,
) -> None:
    """Export emails to CSV format.

    Args:
        db_path: Path to the SQLite database.
        output: Output file path. If None, writes to stdout.
        email_type: Filter by email type.
        status: Filter by status.
    """
    emails = list_emails(db_path, email_type=email_type, status=status, limit=10000)
    if not emails:
        logger.warning("No emails to export")
        return

    data = [_email_to_dict(e) for e in emails]
    fieldnames = data[0].keys()

    if output:
        with open(output, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        logger.info("Exported %d emails to %s", len(data), output)
    else:
        output_buffer = StringIO()
        writer = csv.DictWriter(output_buffer, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
        sys.stdout.write(output_buffer.getvalue())
