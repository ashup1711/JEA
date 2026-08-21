"""Tests for database operations."""

from datetime import datetime, timedelta, timezone

from jea.db import (
    get_email,
    get_pending_emails,
    get_rules,
    get_template_for_type,
    get_templates,
    has_reply_been_sent,
    insert_email,
    insert_rule,
    insert_template,
    list_emails,
    log_reply,
    update_email_status,
)
from jea.models import Email, EmailStatus, EmailType, FilterRule, ReplyTemplate


class TestDatabase:
    """Test database CRUD operations."""

    def test_init_db(self, tmp_db: str) -> None:
        """Test database initialization."""
        # Database should be initialized by the fixture
        import sqlite3
        conn = sqlite3.connect(tmp_db)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert "emails" in tables
        assert "filter_rules" in tables
        assert "reply_templates" in tables
        assert "reply_log" in tables

    def test_insert_and_get_email(self, tmp_db: str, sample_email: Email) -> None:
        """Test inserting and retrieving an email."""
        insert_email(tmp_db, sample_email)
        retrieved = get_email(tmp_db, sample_email.message_id)

        assert retrieved is not None
        assert retrieved.message_id == sample_email.message_id
        assert retrieved.subject == sample_email.subject
        assert retrieved.sender == sample_email.sender
        assert retrieved.email_type == EmailType.OTHER

    def test_insert_duplicate_email(self, tmp_db: str, sample_email: Email) -> None:
        """Test inserting duplicate email is ignored."""
        insert_email(tmp_db, sample_email)
        insert_email(tmp_db, sample_email)  # Should not raise

        emails = list_emails(tmp_db)
        assert len(emails) == 1

    def test_get_nonexistent_email(self, tmp_db: str) -> None:
        """Test getting non-existent email returns None."""
        result = get_email(tmp_db, "nonexistent-id")
        assert result is None

    def test_list_emails(self, tmp_db: str, sample_email: Email, sample_offer_email: Email) -> None:
        """Test listing emails."""
        insert_email(tmp_db, sample_email)
        insert_email(tmp_db, sample_offer_email)

        emails = list_emails(tmp_db)
        assert len(emails) == 2

    def test_list_emails_with_type_filter(self, tmp_db: str, sample_email: Email, sample_offer_email: Email) -> None:
        """Test listing emails with type filter."""
        insert_email(tmp_db, sample_email)
        insert_email(tmp_db, sample_offer_email)

        # Update one email type
        update_email_status(tmp_db, sample_email.message_id, EmailStatus.APPROVED)

        emails = list_emails(tmp_db, status="approved")
        assert len(emails) == 1
        assert emails[0].message_id == sample_email.message_id

    def test_list_emails_with_limit(self, tmp_db: str, sample_email: Email, sample_offer_email: Email) -> None:
        """Test listing emails with limit."""
        insert_email(tmp_db, sample_email)
        insert_email(tmp_db, sample_offer_email)

        emails = list_emails(tmp_db, limit=1)
        assert len(emails) == 1

    def test_update_email_status(self, tmp_db: str, sample_email: Email) -> None:
        """Test updating email status."""
        insert_email(tmp_db, sample_email)

        update_email_status(tmp_db, sample_email.message_id, EmailStatus.APPROVED)
        updated = get_email(tmp_db, sample_email.message_id)

        assert updated is not None
        assert updated.status == EmailStatus.APPROVED

    def test_get_pending_emails(self, tmp_db: str, sample_email: Email, sample_offer_email: Email) -> None:
        """Test getting pending emails."""
        insert_email(tmp_db, sample_email)
        insert_email(tmp_db, sample_offer_email)

        # Mark one as approved
        update_email_status(tmp_db, sample_email.message_id, EmailStatus.APPROVED)

        pending = get_pending_emails(tmp_db)
        assert len(pending) == 1
        assert pending[0].message_id == sample_offer_email.message_id

    def test_insert_and_get_rules(self, tmp_db: str) -> None:
        """Test inserting and retrieving filter rules."""
        rule = FilterRule(
            name="test_rule",
            keywords=["interview", "offer"],
            sender_domains=["google.com"],
        )

        insert_rule(tmp_db, rule)
        rules = get_rules(tmp_db)

        assert len(rules) == 1
        assert rules[0].name == "test_rule"
        assert rules[0].keywords == ["interview", "offer"]
        assert rules[0].sender_domains == ["google.com"]

    def test_insert_and_get_templates(self, tmp_db: str) -> None:
        """Test inserting and retrieving reply templates."""
        template = ReplyTemplate(
            name="interview_ack",
            subject_template="Re: {{ subject }}",
            body_template="Thank you for the interview opportunity.",
            email_types=[EmailType.INTERVIEW_SCHEDULED],
        )

        insert_template(tmp_db, template)
        templates = get_templates(tmp_db)

        assert len(templates) == 1
        assert templates[0].name == "interview_ack"
        assert EmailType.INTERVIEW_SCHEDULED in templates[0].email_types

    def test_get_template_for_type(self, tmp_db: str) -> None:
        """Test getting template for specific email type."""
        template = ReplyTemplate(
            name="interview_ack",
            subject_template="Re: {{ subject }}",
            body_template="Thank you!",
            email_types=[EmailType.INTERVIEW_SCHEDULED],
        )

        insert_template(tmp_db, template)

        # Should find template for interview type
        found = get_template_for_type(tmp_db, EmailType.INTERVIEW_SCHEDULED)
        assert found is not None
        assert found.name == "interview_ack"

        # Should not find template for other type
        not_found = get_template_for_type(tmp_db, EmailType.OFFER)
        assert not_found is None

    def test_log_reply(self, tmp_db: str, sample_email: Email) -> None:
        """Test logging a reply."""
        insert_email(tmp_db, sample_email)
        log_reply(tmp_db, sample_email.message_id, "test_template")

        import sqlite3
        conn = sqlite3.connect(tmp_db)
        row = conn.execute(
            "SELECT * FROM reply_log WHERE message_id = ?",
            (sample_email.message_id,),
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[1] == sample_email.message_id
        assert row[2] == "test_template"

    def test_list_emails_with_subject_filter(self, tmp_db: str, sample_email: Email, sample_offer_email: Email) -> None:
        """Test listing emails filtered by subject substring."""
        insert_email(tmp_db, sample_email)
        insert_email(tmp_db, sample_offer_email)

        emails = list_emails(tmp_db, subject="Interview")
        assert len(emails) == 1
        assert emails[0].message_id == sample_email.message_id
        assert "Interview" in emails[0].subject

    def test_list_emails_with_days_filter(self, tmp_db: str) -> None:
        """Test listing emails filtered by days (recent vs old)."""
        now = datetime.now(timezone.utc)

        recent_email = Email(
            message_id="recent-1",
            thread_id="thread-recent",
            subject="Recent update",
            sender="sender@example.com",
            to="me@gmail.com",
            date=now - timedelta(days=3),
            body_text="This is recent.",
        )
        old_email = Email(
            message_id="old-1",
            thread_id="thread-old",
            subject="Old update",
            sender="sender@example.com",
            to="me@gmail.com",
            date=now - timedelta(days=10),
            body_text="This is old.",
        )
        insert_email(tmp_db, recent_email)
        insert_email(tmp_db, old_email)

        emails = list_emails(tmp_db, days=7)
        assert len(emails) == 1
        assert emails[0].message_id == "recent-1"

    def test_list_emails_with_subject_and_days_combined(self, tmp_db: str) -> None:
        """Test listing emails filtered by both subject and days together."""
        now = datetime.now(timezone.utc)

        matching_recent = Email(
            message_id="match-recent",
            thread_id="thread-1",
            subject="Interview Scheduled at Google",
            sender="recruiter@google.com",
            to="me@gmail.com",
            date=now - timedelta(days=2),
            body_text="Interview scheduled.",
        )
        non_matching_recent = Email(
            message_id="no-match-recent",
            thread_id="thread-2",
            subject="Job Offer at Amazon",
            sender="hr@amazon.com",
            to="me@gmail.com",
            date=now - timedelta(days=2),
            body_text="Offer details.",
        )
        matching_old = Email(
            message_id="match-old",
            thread_id="thread-3",
            subject="Interview Feedback from Microsoft",
            sender="hr@microsoft.com",
            to="me@gmail.com",
            date=now - timedelta(days=30),
            body_text="Feedback.",
        )
        insert_email(tmp_db, matching_recent)
        insert_email(tmp_db, non_matching_recent)
        insert_email(tmp_db, matching_old)

        # Only the recent email with "Interview" in the subject should match
        emails = list_emails(tmp_db, subject="Interview", days=7)
        assert len(emails) == 1
        assert emails[0].message_id == "match-recent"

    def test_list_emails_subject_case_insensitive(self, tmp_db: str, sample_email: Email, sample_offer_email: Email) -> None:
        """Test that subject filter is case-insensitive (SQLite LIKE default for ASCII)."""
        insert_email(tmp_db, sample_email)
        insert_email(tmp_db, sample_offer_email)

        # Lowercase filter should match the capitalized subject
        emails = list_emails(tmp_db, subject="interview")
        assert len(emails) == 1
        assert emails[0].message_id == sample_email.message_id

    def test_has_reply_been_sent(self, tmp_db: str, sample_email: Email) -> None:
        """Test has_reply_been_sent detects reply log entries correctly."""
        insert_email(tmp_db, sample_email)

        # Empty database: no reply sent yet
        assert has_reply_been_sent(tmp_db, sample_email.message_id) is False

        # Log a reply for the sample email
        log_reply(tmp_db, sample_email.message_id, "test_template")
        assert has_reply_been_sent(tmp_db, sample_email.message_id) is True

        # Different message_id should return False
        assert has_reply_been_sent(tmp_db, "nonexistent-id") is False

    def test_has_reply_been_sent_empty_database(self, tmp_db: str) -> None:
        """Test has_reply_been_sent on empty database returns False."""
        assert has_reply_been_sent(tmp_db, "any-message-id") is False
