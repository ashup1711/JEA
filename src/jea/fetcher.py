"""Email fetcher with deduplication and retry logic."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from dateutil import parser as dateutil_parser

from jea.classifier import classify_email
from jea.db import get_email, insert_email, list_emails
from jea.email_client import EmailClient
from jea.exceptions import EmailFetchError
from jea.extractor import extract_data
from jea.models import Email

logger = logging.getLogger("jea.fetcher")


def _parse_date(date_str: str) -> datetime:
    """Parse email date string to datetime.

    Args:
        date_str: Date string from email headers.

    Returns:
        Parsed datetime object.
    """
    try:
        parsed: datetime = dateutil_parser.parse(date_str)
        return parsed
    except (ValueError, TypeError):
        logger.warning("Failed to parse date: %s, using current time", date_str)
        return datetime.now(UTC)


def _raw_to_email(raw: dict[str, Any]) -> Email:
    """Convert raw email dictionary to Email model.

    Args:
        raw: Raw email dictionary from email client.

    Returns:
        Email model instance.
    """
    # Parse date
    date = _parse_date(raw.get("date", ""))

    return Email(
        message_id=raw["message_id"],
        thread_id=raw.get("thread_id"),
        subject=raw.get("subject", ""),
        sender=raw.get("sender", ""),
        to=raw.get("to", ""),
        date=date,
        body_text=raw.get("body_text", ""),
        body_html=raw.get("body_html"),
        labels=raw.get("labels", []),
    )


def fetch_new_emails(
    client: EmailClient,
    db_path: str,
    since: datetime | None = None,
    lookback_days: int = 30,
) -> list[Email]:
    """Fetch emails newer than last fetch, deduplicate, and store in DB.

    Args:
        client: Email client instance.
        db_path: Path to the SQLite database.
        since: Fetch emails since this datetime. If None, uses last email date in DB.
        lookback_days: Days to look back when DB is empty and no since date provided.

    Returns:
        List of new Email objects.
    """
    # If no since datetime, get the latest email date from DB
    if since is None:
        existing = list_emails(db_path, limit=1)
        if existing:
            since = existing[0].date
        else:
            since = datetime.now(UTC) - timedelta(days=lookback_days)

    logger.info("Fetching emails since %s", since.isoformat())

    try:
        # Fetch raw emails from client
        raw_emails = client.fetch_emails(since=since)
    except EmailFetchError:
        logger.exception("Failed to fetch emails")
        return []

    new_emails: list[Email] = []

    for raw in raw_emails:
        message_id = raw["message_id"]

        # Check for duplicates
        if get_email(db_path, message_id):
            logger.debug("Skipping duplicate email: %s", message_id)
            continue

        # Convert to Email model
        email = _raw_to_email(raw)

        # Extract structured data
        email.extracted = extract_data(email)

        # Classify email type
        email.email_type = classify_email(email)

        # Insert into database
        try:
            insert_email(db_path, email)
            new_emails.append(email)
            logger.info(
                "New email: %s | Type: %s | From: %s",
                email.subject[:50],
                email.email_type.value,
                email.sender,
            )
        except Exception:
            logger.exception("Failed to insert email %s", message_id)

    logger.info("Fetched %d new emails", len(new_emails))
    return new_emails
