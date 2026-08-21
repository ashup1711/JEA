"""Tests for data extraction."""

from datetime import datetime

from jea.extractor import extract_data
from jea.models import Email


class TestExtractor:
    """Test data extraction from emails."""

    def test_extract_meeting_link(self, sample_email: Email) -> None:
        """Test extracting Google Meet link."""
        extracted = extract_data(sample_email)
        assert extracted.meeting_link == "https://meet.google.com/abc-defg-hij"

    def test_extract_platform(self, sample_email: Email) -> None:
        """Test detecting meeting platform."""
        extracted = extract_data(sample_email)
        assert extracted.platform == "Google Meet"

    def test_extract_company_from_sender(self, sample_email: Email) -> None:
        """Test extracting company from sender domain."""
        extracted = extract_data(sample_email)
        assert extracted.company == "Google"

    def test_extract_role(self, sample_email: Email) -> None:
        """Test extracting job role."""
        extracted = extract_data(sample_email)
        assert extracted.role is not None
        assert "engineer" in extracted.role.lower()

    def test_extract_datetime(self) -> None:
        """Test extracting interview datetime."""
        email = Email(
            message_id="dt-test",
            subject="Interview Scheduled",
            sender="recruiter@company.com",
            to="me@gmail.com",
            date=datetime(2025, 1, 15, 10, 0),
            body_text="Your interview is scheduled for January 20, 2025 at 2:00 PM PST.",
        )
        extracted = extract_data(email)
        assert extracted.interview_datetime is not None
        assert extracted.interview_datetime.year == 2025
        assert extracted.interview_datetime.month == 1
        assert extracted.interview_datetime.day == 20

    def test_extract_zoom_meeting(self) -> None:
        """Test extracting Zoom meeting link."""
        email = Email(
            message_id="zoom-test",
            subject="Zoom Interview",
            sender="hr@company.com",
            to="me@gmail.com",
            date=datetime(2025, 1, 15, 10, 0),
            body_text="Join Zoom Meeting: https://zoom.us/j/1234567890",
        )
        extracted = extract_data(email)
        assert extracted.meeting_link is not None
        assert "zoom.us" in extracted.meeting_link
        assert extracted.platform == "Zoom"

    def test_extract_teams_meeting(self) -> None:
        """Test extracting Microsoft Teams meeting link."""
        email = Email(
            message_id="teams-test",
            subject="Teams Interview",
            sender="hr@company.com",
            to="me@gmail.com",
            date=datetime(2025, 1, 15, 10, 0),
            body_text="Join Teams Meeting: https://teams.microsoft.com/l/meetup-join/abc123",
        )
        extracted = extract_data(email)
        assert extracted.meeting_link is not None
        assert "teams.microsoft.com" in extracted.meeting_link
        assert extracted.platform == "Microsoft Teams"

    def test_extract_jd_link(self) -> None:
        """Test extracting job description link."""
        email = Email(
            message_id="jd-test",
            subject="Job Opportunity",
            sender="recruiter@greenhouse.io",
            to="me@gmail.com",
            date=datetime(2025, 1, 15, 10, 0),
            body_text="Apply here: https://boards.greenhouse.io/company/jobs/12345",
        )
        extracted = extract_data(email)
        assert extracted.jd_link is not None
        assert "greenhouse.io" in extracted.jd_link

    def test_extract_company_from_subject(self) -> None:
        """Test extracting company from subject line."""
        email = Email(
            message_id="subj-test",
            subject="Interview at Acme Corp - Senior Developer",
            sender="generic@email.com",
            to="me@gmail.com",
            date=datetime(2025, 1, 15, 10, 0),
            body_text="We would like to schedule an interview.",
        )
        extracted = extract_data(email)
        assert extracted.company == "Acme Corp"

    def test_extract_no_data(self) -> None:
        """Test extraction with no extractable data."""
        email = Email(
            message_id="empty-test",
            subject="Hello",
            sender="personal@gmail.com",
            to="me@gmail.com",
            date=datetime(2025, 1, 15, 10, 0),
            body_text="Just saying hello.",
        )
        extracted = extract_data(email)
        assert extracted.company is None
        assert extracted.meeting_link is None
        assert extracted.platform is None

    def test_extract_raw_snippet(self, sample_email: Email) -> None:
        """Test extracting raw snippet."""
        extracted = extract_data(sample_email)
        assert extracted.raw_snippet is not None
        assert len(extracted.raw_snippet) > 0
        assert len(extracted.raw_snippet) <= 200

    def test_extract_from_html(self) -> None:
        """Test extraction from HTML body."""
        email = Email(
            message_id="html-test",
            subject="Interview Scheduled",
            sender="recruiter@company.com",
            to="me@gmail.com",
            date=datetime(2025, 1, 15, 10, 0),
            body_text="",
            body_html="<p>We would like to schedule an interview via <a href='https://zoom.us/j/123'>Zoom</a></p>",
        )
        extracted = extract_data(email)
        assert extracted.platform == "Zoom"
        assert extracted.meeting_link is not None
