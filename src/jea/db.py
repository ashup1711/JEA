"""SQLite database schema and CRUD operations."""

import json
import logging
import sqlite3
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from jea.exceptions import DatabaseError
from jea.models import Email, EmailStatus, EmailType, ExtractedData, FilterRule, ReplyTemplate

logger = logging.getLogger("jea.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT UNIQUE NOT NULL,
    thread_id TEXT,
    subject TEXT NOT NULL,
    sender TEXT NOT NULL,
    "to" TEXT NOT NULL,
    date TEXT NOT NULL,
    body_text TEXT NOT NULL,
    body_html TEXT,
    email_type TEXT NOT NULL DEFAULT 'other',
    status TEXT NOT NULL DEFAULT 'pending',
    company TEXT,
    role TEXT,
    interview_datetime TEXT,
    platform TEXT,
    meeting_link TEXT,
    jd_link TEXT,
    attachments TEXT,
    raw_snippet TEXT,
    labels TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_emails_message_id ON emails(message_id);
CREATE INDEX IF NOT EXISTS idx_emails_date ON emails(date);
CREATE INDEX IF NOT EXISTS idx_emails_email_type ON emails(email_type);
CREATE INDEX IF NOT EXISTS idx_emails_status ON emails(status);

CREATE TABLE IF NOT EXISTS filter_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    rules_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reply_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    subject_template TEXT NOT NULL,
    body_template TEXT NOT NULL,
    email_types TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reply_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL,
    template_name TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    FOREIGN KEY (message_id) REFERENCES emails(message_id)
);

CREATE INDEX IF NOT EXISTS idx_reply_log_message_id ON reply_log(message_id);
"""


def init_db(db_path: str) -> None:
    """Initialize the SQLite database with required tables and indexes.

    Args:
        db_path: Path to the SQLite database file.
    """
    try:
        conn = sqlite3.connect(db_path)
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        conn.close()
        logger.info("Database initialized at %s", db_path)
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to initialize database: {e}") from e


def _get_connection(db_path: str) -> sqlite3.Connection:
    """Get a database connection with row factory enabled."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_email(row: sqlite3.Row) -> Email:
    """Convert a database row to an Email model."""
    attachments = json.loads(row["attachments"]) if row["attachments"] else []
    labels = json.loads(row["labels"]) if row["labels"] else []

    extracted = ExtractedData(
        company=row["company"],
        role=row["role"],
        interview_datetime=(
            datetime.fromisoformat(row["interview_datetime"])
            if row["interview_datetime"]
            else None
        ),
        platform=row["platform"],
        meeting_link=row["meeting_link"],
        jd_link=row["jd_link"],
        attachments=attachments,
        raw_snippet=row["raw_snippet"],
    )

    return Email(
        message_id=row["message_id"],
        thread_id=row["thread_id"],
        subject=row["subject"],
        sender=row["sender"],
        to=row["to"],
        date=datetime.fromisoformat(row["date"]),
        body_text=row["body_text"],
        body_html=row["body_html"],
        email_type=EmailType(row["email_type"]),
        status=EmailStatus(row["status"]),
        extracted=extracted,
        labels=labels,
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def insert_email(db_path: str, email: Email) -> None:
    """Insert an email into the database.

    Args:
        db_path: Path to the SQLite database file.
        email: Email model to insert.

    Raises:
        DatabaseError: If the insertion fails.
    """
    sql = """
    INSERT OR IGNORE INTO emails (
        message_id, thread_id, subject, sender, "to", date, body_text, body_html,
        email_type, status, company, role, interview_datetime, platform,
        meeting_link, jd_link, attachments, raw_snippet, labels, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    try:
        conn = _get_connection(db_path)
        conn.execute(
            sql,
            (
                email.message_id,
                email.thread_id,
                email.subject,
                email.sender,
                email.to,
                email.date.isoformat(),
                email.body_text,
                email.body_html,
                email.email_type.value,
                email.status.value,
                email.extracted.company,
                email.extracted.role,
                email.extracted.interview_datetime.isoformat()
                if email.extracted.interview_datetime
                else None,
                email.extracted.platform,
                email.extracted.meeting_link,
                email.extracted.jd_link,
                json.dumps(email.extracted.attachments),
                email.extracted.raw_snippet,
                json.dumps(email.labels),
                email.created_at.isoformat(),
            ),
        )
        conn.commit()
        conn.close()
        logger.debug("Inserted email: %s", email.message_id)
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to insert email {email.message_id}: {e}") from e


def get_email(db_path: str, message_id: str) -> Email | None:
    """Retrieve an email by message ID.

    Args:
        db_path: Path to the SQLite database file.
        message_id: The unique message identifier.

    Returns:
        Email model if found, None otherwise.
    """
    try:
        conn = _get_connection(db_path)
        row = conn.execute(
            'SELECT * FROM emails WHERE message_id = ?', (message_id,)
        ).fetchone()
        conn.close()
        if row:
            return _row_to_email(row)
        return None
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to get email {message_id}: {e}") from e


def list_emails(
    db_path: str,
    email_type: str | None = None,
    status: str | None = None,
    days: int | None = None,
    subject: str | None = None,
    limit: int = 20,
) -> list[Email]:
    """List emails with optional filtering.

    Args:
        db_path: Path to the SQLite database file.
        email_type: Filter by email type.
        status: Filter by status.
        days: Only include emails from the last N days.
        subject: Filter by subject (case-insensitive substring match).
        limit: Maximum number of results.

    Returns:
        List of Email models.
    """
    try:
        conn = _get_connection(db_path)
        query = 'SELECT * FROM emails WHERE 1=1'
        params: list[Any] = []

        if email_type:
            query += ' AND email_type = ?'
            params.append(email_type)
        if status:
            query += ' AND status = ?'
            params.append(status)
        if days is not None:
            cutoff_iso = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            query += " AND CAST(strftime('%s', date) AS INTEGER) >= CAST(strftime('%s', ?) AS INTEGER)"
            params.append(cutoff_iso)
        if subject:
            query += ' AND subject LIKE ?'
            params.append(f'%{subject}%')

        query += ' ORDER BY date DESC LIMIT ?'
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [_row_to_email(row) for row in rows]
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to list emails: {e}") from e


def update_email_status(db_path: str, message_id: str, status: EmailStatus) -> None:
    """Update the status of an email.

    Args:
        db_path: Path to the SQLite database file.
        message_id: The unique message identifier.
        status: New status value.
    """
    try:
        conn = _get_connection(db_path)
        conn.execute(
            'UPDATE emails SET status = ? WHERE message_id = ?',
            (status.value, message_id),
        )
        conn.commit()
        conn.close()
        logger.debug("Updated email %s status to %s", message_id, status.value)
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to update email status: {e}") from e


def update_email_type(db_path: str, message_id: str, email_type: EmailType) -> None:
    """Update the email type of an email.

    Args:
        db_path: Path to the SQLite database file.
        message_id: The unique message identifier.
        email_type: New email type value.
    """
    try:
        conn = _get_connection(db_path)
        conn.execute(
            'UPDATE emails SET email_type = ? WHERE message_id = ?',
            (email_type.value, message_id),
        )
        conn.commit()
        conn.close()
        logger.debug("Updated email %s type to %s", message_id, email_type.value)
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to update email type: {e}") from e


def reclassify_all_emails(db_path: str) -> dict[str, int | dict[str, int]]:
    """Reclassify all emails in the database using current classification logic.

    Returns:
        Dictionary with counts: {'total': int, 'changed': int, 'by_type': dict[str, int]}
    """
    from jea.classifier import classify_email
    
    try:
        # Get all emails
        emails = list_emails(db_path, limit=100000)
        
        changed_count = 0
        by_type: dict[str, int] = {}
        
        for email in emails:
            # Get new classification
            new_type = classify_email(email)
            
            # Track by type
            type_key = new_type.value
            by_type[type_key] = by_type.get(type_key, 0) + 1
            
            # Update if changed
            if new_type != email.email_type:
                update_email_type(db_path, email.message_id, new_type)
                changed_count += 1
                logger.info(
                    "Reclassified email %s: %s -> %s",
                    email.message_id,
                    email.email_type.value,
                    new_type.value,
                )
        
        return {
            'total': len(emails),
            'changed': changed_count,
            'by_type': by_type,
        }
    except Exception as e:
        raise DatabaseError(f"Failed to reclassify emails: {e}") from e


def get_pending_emails(db_path: str) -> list[Email]:
    """Get all emails with pending status.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        List of pending Email models.
    """
    return list_emails(db_path, status="pending", limit=1000)


def insert_rule(db_path: str, rule: FilterRule) -> None:
    """Insert or update a filter rule.

    Args:
        db_path: Path to the SQLite database file.
        rule: FilterRule model to store.
    """
    sql = """
    INSERT OR REPLACE INTO filter_rules (name, rules_json, created_at)
    VALUES (?, ?, ?)
    """
    try:
        conn = _get_connection(db_path)
        conn.execute(sql, (rule.name, rule.model_dump_json(), datetime.now(UTC).isoformat()))
        conn.commit()
        conn.close()
        logger.debug("Inserted rule: %s", rule.name)
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to insert rule: {e}") from e


def get_rules(db_path: str) -> list[FilterRule]:
    """Retrieve all filter rules.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        List of FilterRule models.
    """
    try:
        conn = _get_connection(db_path)
        rows = conn.execute('SELECT rules_json FROM filter_rules').fetchall()
        conn.close()
        return [FilterRule.model_validate_json(row["rules_json"]) for row in rows]
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to get rules: {e}") from e


def insert_template(db_path: str, template: ReplyTemplate) -> None:
    """Insert or update a reply template.

    Args:
        db_path: Path to the SQLite database file.
        template: ReplyTemplate model to store.
    """
    sql = """
    INSERT OR REPLACE INTO reply_templates (name, subject_template, body_template, email_types, created_at)
    VALUES (?, ?, ?, ?, ?)
    """
    try:
        conn = _get_connection(db_path)
        email_types_json = json.dumps([t.value for t in template.email_types])
        conn.execute(
            sql,
            (
                template.name,
                template.subject_template,
                template.body_template,
                email_types_json,
                datetime.now(UTC).isoformat(),
            ),
        )
        conn.commit()
        conn.close()
        logger.debug("Inserted template: %s", template.name)
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to insert template: {e}") from e


def get_templates(db_path: str) -> list[ReplyTemplate]:
    """Retrieve all reply templates.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        List of ReplyTemplate models.
    """
    try:
        conn = _get_connection(db_path)
        rows = conn.execute('SELECT * FROM reply_templates').fetchall()
        conn.close()
        templates = []
        for row in rows:
            email_types = [EmailType(t) for t in json.loads(row["email_types"])] if row["email_types"] else []
            templates.append(
                ReplyTemplate(
                    name=row["name"],
                    subject_template=row["subject_template"],
                    body_template=row["body_template"],
                    email_types=email_types,
                )
            )
        return templates
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to get templates: {e}") from e


def get_template_for_type(db_path: str, email_type: EmailType) -> ReplyTemplate | None:
    """Get a reply template matching the given email type.

    Args:
        db_path: Path to the SQLite database file.
        email_type: The email type to match.

    Returns:
        ReplyTemplate if found, None otherwise.
    """
    templates = get_templates(db_path)
    for template in templates:
        if email_type in template.email_types:
            return template
    return None


def log_reply(db_path: str, message_id: str, template_name: str) -> None:
    """Log a sent reply.

    Args:
        db_path: Path to the SQLite database file.
        message_id: The message that was replied to.
        template_name: Name of the template used.
    """
    sql = "INSERT INTO reply_log (message_id, template_name, sent_at) VALUES (?, ?, ?)"
    try:
        conn = _get_connection(db_path)
        conn.execute(sql, (message_id, template_name, datetime.now(UTC).isoformat()))
        conn.commit()
        conn.close()
        logger.debug("Logged reply for %s using template %s", message_id, template_name)
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to log reply: {e}") from e


def has_reply_been_sent(db_path: str, message_id: str) -> bool:
    """Check if a reply has already been sent for a given message.

    Args:
        db_path: Path to the SQLite database file.
        message_id: The message identifier to check.

    Returns:
        True if a reply record exists for the message_id, False otherwise.
    """
    try:
        conn = _get_connection(db_path)
        row = conn.execute(
            'SELECT 1 FROM reply_log WHERE message_id = ? LIMIT 1', (message_id,)
        ).fetchone()
        conn.close()
        return row is not None
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to check reply status for {message_id}: {e}") from e
