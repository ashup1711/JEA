"""Tests for email filtering."""


from jea.filter import filter_emails, matches_rule
from jea.models import Email, FilterRule


class TestFilter:
    """Test email filtering logic."""

    def test_matches_rule_keywords(self, sample_email: Email) -> None:
        """Test matching by keywords."""
        rule = FilterRule(
            name="test",
            keywords=["interview", "schedule"],
        )
        assert matches_rule(sample_email, rule) is True

    def test_matches_rule_no_keyword_match(self, sample_email: Email) -> None:
        """Test no match when keywords don't match."""
        rule = FilterRule(
            name="test",
            keywords=["python", "java"],
        )
        assert matches_rule(sample_email, rule) is False

    def test_matches_rule_sender_domain(self, sample_email: Email) -> None:
        """Test matching by sender domain."""
        rule = FilterRule(
            name="test",
            sender_domains=["google.com"],
        )
        assert matches_rule(sample_email, rule) is True

    def test_matches_rule_sender_domain_no_match(self, sample_email: Email) -> None:
        """Test no match when sender domain doesn't match."""
        rule = FilterRule(
            name="test",
            sender_domains=["microsoft.com"],
        )
        assert matches_rule(sample_email, rule) is False

    def test_matches_rule_subject_pattern(self, sample_email: Email) -> None:
        """Test matching by subject pattern."""
        rule = FilterRule(
            name="test",
            subject_patterns=[r"Interview.*at.*Google"],
        )
        assert matches_rule(sample_email, rule) is True

    def test_matches_rule_exclude_keywords(self, sample_email: Email) -> None:
        """Test excluding by keywords."""
        rule = FilterRule(
            name="test",
            keywords=["interview"],
            exclude_keywords=["cancelled"],
        )
        assert matches_rule(sample_email, rule) is True

        # Test with exclude keyword present
        email_with_exclude = Email(
            message_id="test-456",
            subject="Interview Cancelled",
            sender="test@example.com",
            to="me@gmail.com",
            date=sample_email.date,
            body_text="The interview has been cancelled.",
        )
        assert matches_rule(email_with_exclude, rule) is False

    def test_matches_rule_empty_criteria(self, sample_email: Email) -> None:
        """Test that empty criteria matches everything."""
        rule = FilterRule(name="test")
        assert matches_rule(sample_email, rule) is True

    def test_matches_rule_all_criteria(self, sample_email: Email) -> None:
        """Test matching all criteria together."""
        rule = FilterRule(
            name="test",
            keywords=["interview"],
            sender_domains=["google.com"],
            subject_patterns=[r"Interview"],
        )
        assert matches_rule(sample_email, rule) is True

    def test_matches_rule_partial_criteria_fail(self, sample_email: Email) -> None:
        """Test that failing one criteria fails the match."""
        rule = FilterRule(
            name="test",
            keywords=["interview"],
            sender_domains=["microsoft.com"],  # Wrong domain
        )
        assert matches_rule(sample_email, rule) is False

    def test_filter_emails(self, sample_email: Email, sample_rules: list[FilterRule]) -> None:
        """Test filtering multiple emails."""
        from datetime import datetime

        other_email = Email(
            message_id="other-123",
            subject="Newsletter",
            sender="newsletter@example.com",
            to="me@gmail.com",
            date=datetime(2025, 1, 16, 10, 0),
            body_text="This is a newsletter.",
        )

        emails = [sample_email, other_email]
        filtered = filter_emails(emails, sample_rules)

        assert len(filtered) == 1
        assert filtered[0].message_id == sample_email.message_id

    def test_filter_emails_no_rules(self, sample_email: Email) -> None:
        """Test that no rules returns all emails."""
        filtered = filter_emails([sample_email], [])
        assert len(filtered) == 1

    def test_matches_rule_case_insensitive(self) -> None:
        """Test case-insensitive matching."""
        from datetime import datetime

        email = Email(
            message_id="test-789",
            subject="INTERVIEW SCHEDULED",
            sender="RECRUITER@GOOGLE.COM",
            to="me@gmail.com",
            date=datetime(2025, 1, 15, 10, 0),
            body_text="We would like to schedule an INTERVIEW.",
        )

        rule = FilterRule(
            name="test",
            keywords=["interview"],
            sender_domains=["google.com"],
        )
        assert matches_rule(email, rule) is True

    def test_matches_rule_sender_pattern(self, sample_email: Email) -> None:
        """Test matching by sender regex pattern."""
        rule = FilterRule(
            name="test",
            sender_patterns=[r"@google\.com$"],
        )
        assert matches_rule(sample_email, rule) is True

    def test_matches_rule_sender_pattern_no_match(self, sample_email: Email) -> None:
        """Test no match when sender pattern doesn't match."""
        rule = FilterRule(
            name="test",
            sender_patterns=[r"@microsoft\.com$"],
        )
        assert matches_rule(sample_email, rule) is False
