"""Pytest fixtures for JEA tests."""

from datetime import datetime
from pathlib import Path

import pytest

from jea.config import AppConfig
from jea.db import init_db
from jea.models import Email, FilterRule


@pytest.fixture
def tmp_db(tmp_path: Path) -> str:
    """Create a temporary database for testing.

    Args:
        tmp_path: Pytest temporary directory fixture.

    Returns:
        Path to the temporary database file.
    """
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    return db_path


@pytest.fixture
def sample_email() -> Email:
    """Create a sample email for testing.

    Returns:
        Email model instance with sample data.
    """
    return Email(
        message_id="test-123",
        thread_id="thread-456",
        subject="Interview Scheduled - Software Engineer at Google",
        sender="recruiter@google.com",
        to="me@gmail.com",
        date=datetime(2025, 1, 15, 10, 0),
        body_text=(
            "We would like to schedule an interview for Jan 20, 2025 at 2:00 PM PST "
            "via Google Meet. Link: https://meet.google.com/abc-defg-hij\n\n"
            "This will be a technical interview for the Software Engineer position."
        ),
    )


@pytest.fixture
def sample_offer_email() -> Email:
    """Create a sample offer email for testing.

    Returns:
        Email model instance with offer data.
    """
    return Email(
        message_id="offer-789",
        thread_id="thread-789",
        subject="Job Offer - Senior Developer at Microsoft",
        sender="hr@microsoft.com",
        to="me@gmail.com",
        date=datetime(2025, 2, 1, 14, 30),
        body_text=(
            "We are delighted to extend an offer for the Senior Developer position "
            "at Microsoft. The compensation package includes a competitive salary "
            "and benefits. Please review the attached offer letter."
        ),
    )


@pytest.fixture
def sample_rejection_email() -> Email:
    """Create a sample rejection email for testing.

    Returns:
        Email model instance with rejection data.
    """
    return Email(
        message_id="rej-101",
        thread_id="thread-101",
        subject="Application Update - Amazon",
        sender="noreply@amazon.com",
        to="me@gmail.com",
        date=datetime(2025, 2, 5, 9, 0),
        body_text=(
            "Thank you for your interest in the position at Amazon. "
            "After careful consideration, we have decided to move forward "
            "with other candidates. We wish you the best in your job search."
        ),
    )


@pytest.fixture
def sample_rules() -> list[FilterRule]:
    """Create sample filter rules for testing.

    Returns:
        List of FilterRule models.
    """
    return [
        FilterRule(
            name="interview",
            keywords=["interview", "schedule", "technical round"],
            sender_domains=["google.com", "microsoft.com"],
        ),
        FilterRule(
            name="offers",
            keywords=["offer", "compensation", "delighted"],
            sender_domains=["microsoft.com", "amazon.com"],
        ),
    ]


@pytest.fixture
def sample_newsletter_email() -> Email:
    return Email(
        message_id="newsletter-001",
        subject="TLDR Newsletter - Daily Tech Digest",
        sender="newsletter@tldr.com",
        to="me@gmail.com",
        date=datetime(2025, 3, 1, 8, 0),
        body_text="Your daily tech newsletter with the latest in software engineering. Unsubscribe at the bottom.",
    )


@pytest.fixture
def sample_social_email() -> Email:
    return Email(
        message_id="social-001",
        subject="New LinkedIn Connection Request",
        sender="notifications@socialmedia.com",
        to="me@gmail.com",
        date=datetime(2025, 3, 1, 9, 0),
        body_text="John Doe wants to connect with you on LinkedIn. View their profile.",
    )


@pytest.fixture
def sample_blog_email() -> Email:
    return Email(
        message_id="blog-001",
        subject="New Blog Post: Building Scalable APIs",
        sender="blog@techblog.com",
        to="me@gmail.com",
        date=datetime(2025, 3, 1, 10, 0),
        body_text="Check out our new blog post on building scalable APIs with Python.",
    )


@pytest.fixture
def sample_job_provider_email() -> Email:
    return Email(
        message_id="jobprovider-001",
        subject="LinkedIn Job Alert: Software Engineer jobs for you",
        sender="jobs@linkedin.com",
        to="me@gmail.com",
        date=datetime(2025, 3, 1, 11, 0),
        body_text="New recommended jobs for you based on your preferences. 5 new matches today.",
    )


@pytest.fixture
def app_config(tmp_path: Path) -> AppConfig:
    """Create a test application configuration.

    Args:
        tmp_path: Pytest temporary directory fixture.

    Returns:
        AppConfig instance for testing.
    """
    return AppConfig(
        db_path=str(tmp_path / "test.db"),
        log_level="DEBUG",
        log_file=None,
        email_backend="imap",
    )
