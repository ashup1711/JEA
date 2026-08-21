"""Tests for email classification."""

from datetime import datetime

from jea.classifier import classify_email
from jea.models import Email, EmailType


class TestClassifier:
    """Test email classification logic."""

    def test_classify_interview(self, sample_email: Email) -> None:
        """Test classifying interview email."""
        result = classify_email(sample_email)
        assert result == EmailType.INTERVIEW_SCHEDULED

    def test_classify_offer(self, sample_offer_email: Email) -> None:
        """Test classifying offer email."""
        result = classify_email(sample_offer_email)
        assert result == EmailType.OFFER

    def test_classify_rejection(self, sample_rejection_email: Email) -> None:
        """Test classifying rejection email."""
        result = classify_email(sample_rejection_email)
        assert result == EmailType.REJECTION

    def test_classify_jd(self) -> None:
        """Test classifying job description email."""
        email = Email(
            message_id="jd-123",
            subject="Job Opportunity - Software Engineer",
            sender="recruiter@company.com",
            to="me@gmail.com",
            date=datetime(2025, 1, 15, 10, 0),
            body_text="We are hiring! Check out this exciting opportunity for a Software Engineer.",
        )
        result = classify_email(email)
        assert result == EmailType.JD_RECEIVED

    def test_classify_follow_up(self) -> None:
        """Test classifying follow-up email."""
        email = Email(
            message_id="followup-123",
            subject="Following up on your application",
            sender="recruiter@company.com",
            to="me@gmail.com",
            date=datetime(2025, 1, 15, 10, 0),
            body_text="Just checking in on the status of your application.",
        )
        result = classify_email(email)
        assert result == EmailType.FOLLOW_UP

    def test_classify_other(self) -> None:
        """Test classifying other email."""
        email = Email(
            message_id="other-123",
            subject="Hello",
            sender="friend@email.com",
            to="me@gmail.com",
            date=datetime(2025, 1, 15, 10, 0),
            body_text="Just saying hello.",
        )
        result = classify_email(email)
        assert result == EmailType.OTHER

    def test_classify_interview_variations(self) -> None:
        """Test various interview email patterns."""
        test_cases = [
            ("Interview Invite - Technical Round", "You are invited for a technical interview."),
            ("Calendar Invite: Phone Screen", "Please join the calendar invite for your phone screen."),
            ("Zoom Interview Confirmation", "Your Zoom interview has been confirmed."),
            ("Technical Interview Scheduled", "We have scheduled your technical interview."),
        ]

        for subject, body in test_cases:
            email = Email(
                message_id=f"test-{subject[:10]}",
                subject=subject,
                sender="recruiter@company.com",
                to="me@gmail.com",
                date=datetime(2025, 1, 15, 10, 0),
                body_text=body,
            )
            result = classify_email(email)
            assert result == EmailType.INTERVIEW_SCHEDULED, f"Failed for: {subject}"

    def test_classify_offer_variations(self) -> None:
        """Test various offer email patterns."""
        test_cases = [
            ("Job Offer - Congratulations!", "We are pleased to offer you the position."),
            ("Offer Letter Attached", "Please find your offer letter attached."),
            ("Compensation Package Details", "Here are the details of your compensation package."),
        ]

        for subject, body in test_cases:
            email = Email(
                message_id=f"test-{subject[:10]}",
                subject=subject,
                sender="hr@company.com",
                to="me@gmail.com",
                date=datetime(2025, 1, 15, 10, 0),
                body_text=body,
            )
            result = classify_email(email)
            assert result == EmailType.OFFER, f"Failed for: {subject}"

    def test_classify_rejection_variations(self) -> None:
        """Test various rejection email patterns."""
        test_cases = [
            ("Application Update", "We regret to inform you that we have decided not to proceed."),
            ("Status Update", "Unfortunately, we are moving forward with other candidates."),
            ("Thank You", "After careful consideration, we have decided to pursue other candidates."),
        ]

        for subject, body in test_cases:
            email = Email(
                message_id=f"test-{subject[:10]}",
                subject=subject,
                sender="hr@company.com",
                to="me@gmail.com",
                date=datetime(2025, 1, 15, 10, 0),
                body_text=body,
            )
            result = classify_email(email)
            assert result == EmailType.REJECTION, f"Failed for: {subject}"

    def test_classify_newsletter(self, sample_newsletter_email: Email) -> None:
        result = classify_email(sample_newsletter_email)
        assert result == EmailType.NEWSLETTER

    def test_classify_social(self, sample_social_email: Email) -> None:
        result = classify_email(sample_social_email)
        assert result == EmailType.SOCIAL

    def test_classify_blog(self, sample_blog_email: Email) -> None:
        result = classify_email(sample_blog_email)
        assert result == EmailType.BLOG

    def test_classify_job_provider(self, sample_job_provider_email: Email) -> None:
        result = classify_email(sample_job_provider_email)
        assert result == EmailType.JOB_PROVIDER

    def test_classify_newsletter_variations(self) -> None:
        test_cases = [
            ("Your Weekly Tech Digest", "This week in tech: AI advances and more. Unsubscribe here."),
            ("Developer Newsletter #42", "Latest developer newsletter with tips and tutorials."),
            ("TLDR Newsletter", "Your daily digest of tech news. TLDR for busy developers."),
        ]
        for subject, body in test_cases:
            email = Email(
                message_id=f"test-newsletter-{subject[:10]}",
                subject=subject, sender="newsletter@test.com",
                to="me@gmail.com", date=datetime(2025, 1, 15, 10, 0),
                body_text=body,
            )
            result = classify_email(email)
            assert result == EmailType.NEWSLETTER, f"Failed for: {subject}"

    def test_classify_social_variations(self) -> None:
        test_cases = [
            ("LinkedIn: You have a new connection request", "John wants to connect with you on LinkedIn."),
            ("GitHub Notification", "Someone mentioned you in a GitHub issue."),
            ("New follower on Twitter", "@user started following you on Twitter."),
        ]
        for subject, body in test_cases:
            email = Email(
                message_id=f"test-social-{subject[:10]}",
                subject=subject, sender="notification@test.com",
                to="me@gmail.com", date=datetime(2025, 1, 15, 10, 0),
                body_text=body,
            )
            result = classify_email(email)
            assert result == EmailType.SOCIAL, f"Failed for: {subject}"

    def test_classify_blog_variations(self) -> None:
        test_cases = [
            ("New Article Published", "A new article has been published on our blog about microservices."),
            ("Medium Story: Python Best Practices", "Read our latest story on Medium about Python best practices."),
        ]
        for subject, body in test_cases:
            email = Email(
                message_id=f"test-blog-{subject[:10]}",
                subject=subject, sender="blog@test.com",
                to="me@gmail.com", date=datetime(2025, 1, 15, 10, 0),
                body_text=body,
            )
            result = classify_email(email)
            assert result == EmailType.BLOG, f"Failed for: {subject}"

    def test_classify_job_provider_variations(self) -> None:
        test_cases = [
            ("Indeed Job Alert: Python Developer", "New jobs matching your search. Recommended jobs for you."),
            ("Glassdoor Job Alert", "New jobs match your preferences. Daily job digest."),
            ("Your Daily Job Digest", "Personalized job picks based on your profile."),
        ]
        for subject, body in test_cases:
            email = Email(
                message_id=f"test-jp-{subject[:10]}",
                subject=subject, sender="jobs@test.com",
                to="me@gmail.com", date=datetime(2025, 1, 15, 10, 0),
                body_text=body,
            )
            result = classify_email(email)
            assert result == EmailType.JOB_PROVIDER, f"Failed for: {subject}"

    def test_job_related_takes_priority_over_newsletter(self) -> None:
        email = Email(
            message_id="priority-newsletter",
            subject="Interview Scheduled - Software Engineer",
            sender="recruiter@company.com",
            to="me@gmail.com",
            date=datetime(2025, 1, 15, 10, 0),
            body_text="We have scheduled your interview. Also, check out our weekly newsletter.",
        )
        result = classify_email(email)
        assert result == EmailType.INTERVIEW_SCHEDULED

    def test_job_related_takes_priority_over_social(self) -> None:
        email = Email(
            message_id="priority-social",
            subject="Job Offer - Congratulations!",
            sender="hr@company.com",
            to="me@gmail.com",
            date=datetime(2025, 1, 15, 10, 0),
            body_text="We are pleased to offer you the position. Connect with us on LinkedIn.",
        )
        result = classify_email(email)
        assert result == EmailType.OFFER

    def test_job_provider_priority_over_newsletter(self) -> None:
        email = Email(
            message_id="jp-over-newsletter",
            subject="LinkedIn Job Alert: Engineer roles",
            sender="jobs@linkedin.com",
            to="me@gmail.com",
            date=datetime(2025, 1, 15, 10, 0),
            body_text="Recommended jobs for you. Also subscribe to our weekly newsletter digest.",
        )
        result = classify_email(email)
        assert result == EmailType.JOB_PROVIDER

    def test_classify_priority(self) -> None:
        """Test that classification follows priority order."""
        # Email that could match multiple types - interview should take priority
        email = Email(
            message_id="priority-test",
            subject="Interview and Offer Discussion",
            sender="recruiter@company.com",
            to="me@gmail.com",
            date=datetime(2025, 1, 15, 10, 0),
            body_text="We would like to schedule an interview to discuss the offer.",
        )
        result = classify_email(email)
        assert result == EmailType.INTERVIEW_SCHEDULED

    def test_classify_sender_based_job_provider(self) -> None:
        """Test that emails from known job platforms are classified as JOB_PROVIDER."""
        test_cases = [
            ("jobs@indeed.com", "New Job Matches", "Check out these new jobs."),
            ("jobs@linkedin.com", "LinkedIn Job Alert", "Recommended for you."),
            ("alerts@glassdoor.com", "Job Alert", "New positions available."),
            ("jobs@naukri.com", "Job Recommendations", "Top jobs for you."),
            ("notifications@monster.com", "Job Alert", "New opportunities."),
            ("jobs@ziprecruiter.com", "Job Matches", "Found 10 new jobs."),
            ("alerts@bebee.com", "Job Alert", "New jobs for you."),
            ("notify@mg.flexjobs.com", "Job Alert", "Remote jobs available."),
        ]

        for sender, subject, body in test_cases:
            email = Email(
                message_id=f"platform-{sender}",
                subject=subject,
                sender=sender,
                to="me@gmail.com",
                date=datetime(2025, 1, 15, 10, 0),
                body_text=body,
            )
            result = classify_email(email)
            assert result == EmailType.JOB_PROVIDER, f"Failed for sender: {sender}"

    def test_platform_alerts_not_misclassified(self) -> None:
        """Test that platform alerts with job-related text are not misclassified."""
        # Indeed email with 'offer' text in body should still be JOB_PROVIDER
        email = Email(
            message_id="indeed-offer",
            subject="Job Alert: Senior Developer",
            sender="jobs@indeed.com",
            to="me@gmail.com",
            date=datetime(2025, 1, 15, 10, 0),
            body_text="We have an exciting opportunity with great offer. Check these jobs.",
        )
        result = classify_email(email)
        assert result == EmailType.JOB_PROVIDER

        # LinkedIn email with 'interview' text should still be JOB_PROVIDER
        email = Email(
            message_id="linkedin-interview",
            subject="Job Alert: Interview Prep Tips",
            sender="jobs@linkedin.com",
            to="me@gmail.com",
            date=datetime(2025, 1, 15, 10, 0),
            body_text="Prepare for your next interview with these tips.",
        )
        result = classify_email(email)
        assert result == EmailType.JOB_PROVIDER

    def test_legitimate_company_emails_not_affected(self) -> None:
        """Test that legitimate company emails still use text-based classification."""
        # Google interview email should be INTERVIEW_SCHEDULED
        email = Email(
            message_id="google-interview",
            subject="Interview Scheduled - Software Engineer",
            sender="recruiter@google.com",
            to="me@gmail.com",
            date=datetime(2025, 1, 15, 10, 0),
            body_text="We would like to schedule an interview for the position.",
        )
        result = classify_email(email)
        assert result == EmailType.INTERVIEW_SCHEDULED

        # Microsoft offer email should be OFFER
        email = Email(
            message_id="ms-offer",
            subject="Job Offer - Senior Developer",
            sender="hr@microsoft.com",
            to="me@gmail.com",
            date=datetime(2025, 1, 15, 10, 0),
            body_text="We are delighted to extend an offer for the position.",
        )
        result = classify_email(email)
        assert result == EmailType.OFFER

    def test_sender_domain_extraction_edge_cases(self) -> None:
        """Test classification with various sender formats."""
        # Sender with display name
        email = Email(
            message_id="named-sender",
            subject="Job Opportunity",
            sender="John Doe <jobs@indeed.com>",
            to="me@gmail.com",
            date=datetime(2025, 1, 15, 10, 0),
            body_text="Check out this opportunity.",
        )
        result = classify_email(email)
        assert result == EmailType.JOB_PROVIDER

        # Sender without angle brackets
        email = Email(
            message_id="plain-sender",
            subject="Job Alert",
            sender="alerts@linkedin.com",
            to="me@gmail.com",
            date=datetime(2025, 1, 15, 10, 0),
            body_text="New jobs available.",
        )
        result = classify_email(email)
        assert result == EmailType.JOB_PROVIDER

        # Unknown sender should use text-based classification
        email = Email(
            message_id="unknown-sender",
            subject="Interview Scheduled",
            sender="recruiter@unknown-company.com",
            to="me@gmail.com",
            date=datetime(2025, 1, 15, 10, 0),
            body_text="We would like to schedule an interview.",
        )
        result = classify_email(email)
        assert result == EmailType.INTERVIEW_SCHEDULED

    def test_job_platform_senders_coverage(self) -> None:
        """Test that all known platforms are covered."""
        from jea.classifier import JOB_PLATFORM_SENDERS

        required_platforms = ["indeed", "linkedin", "glassdoor", "naukri", "monster"]
        for platform in required_platforms:
            assert any(platform in domain for domain in JOB_PLATFORM_SENDERS), \
                f"Platform {platform} not found in JOB_PLATFORM_SENDERS"

    def test_naukri_truncated_sender_classified(self) -> None:
        """Test that Naukri emails with truncated sender are classified as JOB_PROVIDER."""
        test_cases = [
            # Truncated domain
            ("Naukri Alerts <naukrialerts@na>", "Job Alert", "New jobs for you"),
            # Partial domain
            ("Naukri <alerts@nauk>", "Job Alert", "Top jobs matching your profile"),
            # Full domain (should still work)
            ("Naukri <alerts@naukri.com>", "Job Alert", "New jobs available"),
        ]
        for sender, subject, body in test_cases:
            email = Email(
                message_id=f"naukri-trunc-{sender[:10]}",
                subject=subject, sender=sender,
                to="me@gmail.com", date=datetime(2025, 1, 15, 10, 0),
                body_text=body,
            )
            result = classify_email(email)
            assert result == EmailType.JOB_PROVIDER, f"Failed for sender: {sender}"

    def test_naukri_text_pattern_classified(self) -> None:
        """Test that Naukri emails are classified by text patterns as fallback."""
        test_cases = [
            ("Naukri Job Alert: Python Developer", "New jobs matching your search on Naukri."),
            ("Your Naukri Alert", "Naukri has new job recommendations for you."),
            ("Jobs on Naukri", "Check out these jobs on jobs.naukri.com"),
        ]
        for subject, body in test_cases:
            email = Email(
                message_id=f"naukri-text-{subject[:10]}",
                subject=subject, sender="alerts@unknown.com",
                to="me@gmail.com", date=datetime(2025, 1, 15, 10, 0),
                body_text=body,
            )
            result = classify_email(email)
            assert result == EmailType.JOB_PROVIDER, f"Failed for: {subject}"
