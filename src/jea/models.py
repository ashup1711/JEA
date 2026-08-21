"""Pydantic models for emails, rules, and templates."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class EmailType(StrEnum):
    """Classification of job-related email types."""

    # Job-related (high priority)
    INTERVIEW_SCHEDULED = "interview_scheduled"
    JD_RECEIVED = "jd_received"
    OFFER = "offer"
    REJECTION = "rejection"
    FOLLOW_UP = "follow_up"
    # Job-adjacent
    JOB_PROVIDER = "job_provider"
    # Non-job categories
    NEWSLETTER = "newsletter"
    SOCIAL = "social"
    BLOG = "blog"
    # Fallback
    OTHER = "other"


class EmailStatus(StrEnum):
    """Processing status of an email."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REPLIED = "replied"


class ExtractedData(BaseModel):
    """Structured data extracted from an email body."""

    company: str | None = None
    role: str | None = None
    interview_datetime: datetime | None = None
    platform: str | None = None  # Zoom, Teams, Google Meet, etc.
    meeting_link: str | None = None
    jd_link: str | None = None
    attachments: list[str] = Field(default_factory=list)
    raw_snippet: str | None = None


class Email(BaseModel):
    """Represents a job-related email with metadata and extracted data."""

    message_id: str
    thread_id: str | None = None
    subject: str
    sender: str
    to: str
    date: datetime
    body_text: str
    body_html: str | None = None
    email_type: EmailType = EmailType.OTHER
    status: EmailStatus = EmailStatus.PENDING
    extracted: ExtractedData = Field(default_factory=ExtractedData)
    labels: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class FilterRule(BaseModel):
    """Rule for filtering emails by keywords, senders, and patterns."""

    name: str
    keywords: list[str] = Field(default_factory=list)
    sender_domains: list[str] = Field(default_factory=list)
    sender_patterns: list[str] = Field(default_factory=list)
    subject_patterns: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)


class ReplyTemplate(BaseModel):
    """Jinja2-based reply template for email responses."""

    name: str
    subject_template: str
    body_template: str  # Jinja2 template
    email_types: list[EmailType] = Field(default_factory=list)
