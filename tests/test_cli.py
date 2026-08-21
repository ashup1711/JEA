"""Tests for CLI commands."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from jea.cli import cli
from jea.db import init_db, insert_email, insert_rule, insert_template, log_reply, update_email_status
from jea.models import Email, EmailStatus, EmailType, FilterRule, ReplyTemplate


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click test runner."""
    return CliRunner()


@pytest.fixture
def initialized_db(tmp_path: Path) -> str:
    """Create an initialized database with sample data."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    # Insert sample email
    email = Email(
        message_id="test-123",
        subject="Interview Scheduled - Software Engineer at Google",
        sender="recruiter@google.com",
        to="me@gmail.com",
        date=datetime(2025, 1, 15, 10, 0),
        body_text="We would like to schedule an interview.",
    )
    insert_email(db_path, email)

    # Insert sample rule
    rule = FilterRule(
        name="interview",
        keywords=["interview", "schedule"],
        sender_domains=["google.com"],
    )
    insert_rule(db_path, rule)

    # Insert sample template
    template = ReplyTemplate(
        name="interview_ack",
        subject_template="Re: {{ subject }}",
        body_template="Thank you for the interview opportunity.",
        email_types=[EmailType.INTERVIEW_SCHEDULED],
    )
    insert_template(db_path, template)

    return db_path


@pytest.fixture
def config_file(tmp_path: Path, initialized_db: str) -> str:
    """Create a temp YAML config pointing to the test DB."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"db_path: {initialized_db}\n"
        f"log_level: DEBUG\n"
        f"log_file: null\n"
    )
    return str(config_path)


@pytest.fixture
def minimal_config_file(tmp_path: Path) -> str:
    """Create a minimal temp YAML config for tests that don't need initialized_db."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"db_path: {tmp_path / 'minimal.db'}\n"
        f"log_level: DEBUG\n"
        f"log_file: null\n"
    )
    return str(config_path)


@pytest.fixture
def multi_email_db(tmp_path: Path) -> tuple[str, str]:
    """Create a DB with multiple emails sharing prefixes for resolution tests."""
    db_path = str(tmp_path / "multi.db")
    init_db(db_path)

    # Emails with shared prefix 'alpha'
    emails = [
        Email(
            message_id="alpha-001-interview",
            subject="Interview at Alpha Corp",
            sender="hr@alpha.com",
            to="me@gmail.com",
            date=datetime(2025, 2, 1, 10, 0),
            body_text="Interview details.",
        ),
        Email(
            message_id="alpha-002-offer",
            subject="Offer from Alpha Corp",
            sender="hr@alpha.com",
            to="me@gmail.com",
            date=datetime(2025, 2, 2, 10, 0),
            body_text="Offer details.",
        ),
        Email(
            message_id="beta-001-jd",
            subject="JD at Beta Inc",
            sender="hr@beta.com",
            to="me@gmail.com",
            date=datetime(2025, 2, 3, 10, 0),
            body_text="Job description.",
        ),
    ]
    for email in emails:
        insert_email(db_path, email)

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"db_path: {db_path}\n"
        f"log_level: DEBUG\n"
        f"log_file: null\n"
    )
    return db_path, str(config_path)


class TestCLI:
    """Test CLI commands."""

    def test_cli_help(self, runner: CliRunner) -> None:
        """Test CLI help command."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Job Email Assistant" in result.output

    def test_list_command(self, runner: CliRunner, initialized_db: str, config_file: str) -> None:
        """Test list command."""
        result = runner.invoke(
            cli,
            ["--config", config_file, "list"],
        )
        assert result.exit_code == 0

    def test_list_command_with_type_filter(self, runner: CliRunner, initialized_db: str, config_file: str) -> None:
        """Test list command with type filter."""
        result = runner.invoke(
            cli,
            ["--config", config_file, "list", "--type", "other"],
        )
        assert result.exit_code == 0

    def test_list_command_with_status_filter(self, runner: CliRunner, initialized_db: str, config_file: str) -> None:
        """Test list command with status filter."""
        result = runner.invoke(
            cli,
            ["--config", config_file, "list", "--status", "pending"],
        )
        assert result.exit_code == 0

    def test_show_command(self, runner: CliRunner, initialized_db: str, config_file: str) -> None:
        """Test show command."""
        result = runner.invoke(
            cli,
            ["--config", config_file, "show", "test-123"],
        )
        assert result.exit_code == 0

    def test_show_command_not_found(self, runner: CliRunner, initialized_db: str, config_file: str) -> None:
        """Test show command with non-existent email."""
        result = runner.invoke(
            cli,
            ["--config", config_file, "show", "nonexistent"],
        )
        assert result.exit_code == 0
        assert "not found" in result.output.lower() or "no emails" in result.output.lower()

    def test_reject_command(self, runner: CliRunner, initialized_db: str, config_file: str) -> None:
        """Test reject command."""
        result = runner.invoke(
            cli,
            ["--config", config_file, "reject", "test-123"],
        )
        assert result.exit_code == 0

    def test_approve_command_no_reply(self, runner: CliRunner, initialized_db: str, config_file: str) -> None:
        """Test approve command without reply."""
        result = runner.invoke(
            cli,
            ["--config", config_file, "approve", "test-123", "--no-reply"],
        )
        assert result.exit_code == 0

    def test_config_command(self, runner: CliRunner, initialized_db: str, config_file: str) -> None:
        """Test config command."""
        result = runner.invoke(
            cli,
            ["--config", config_file, "config"],
        )
        assert result.exit_code == 0

    def test_export_command_json(self, runner: CliRunner, initialized_db: str, config_file: str, tmp_path: Path) -> None:
        """Test export command with JSON format."""
        output_file = str(tmp_path / "export.json")
        result = runner.invoke(
            cli,
            ["--config", config_file, "export", "--format", "json", "--output", output_file],
        )
        assert result.exit_code == 0

    def test_export_command_csv(self, runner: CliRunner, initialized_db: str, config_file: str, tmp_path: Path) -> None:
        """Test export command with CSV format."""
        output_file = str(tmp_path / "export.csv")
        result = runner.invoke(
            cli,
            ["--config", config_file, "export", "--format", "csv", "--output", output_file],
        )
        assert result.exit_code == 0

    def test_rule_command(self, runner: CliRunner, initialized_db: str, config_file: str) -> None:
        """Test rule command."""
        result = runner.invoke(
            cli,
            [
                "--config", config_file,
                "rule", "test_rule",
                "--keywords", "interview,schedule",
                "--domains", "google.com",
            ],
        )
        assert result.exit_code == 0

    def test_template_command(self, runner: CliRunner, initialized_db: str, config_file: str, tmp_path: Path) -> None:
        """Test template command."""
        template_file = tmp_path / "template.txt"
        template_file.write_text("Thank you for the interview opportunity.")

        result = runner.invoke(
            cli,
            [
                "--config", config_file,
                "template", "test_template",
                "--subject", "Re: {{ subject }}",
                "--body-file", str(template_file),
                "--for-types", "interview_scheduled",
            ],
        )
        assert result.exit_code == 0

    def test_init_command(self, runner: CliRunner, tmp_path: Path, minimal_config_file: str) -> None:
        """Test init command."""
        result = runner.invoke(
            cli,
            ["--config", minimal_config_file, "init"],
        )
        assert result.exit_code == 0

    def test_acknowledge_command(
        self, runner: CliRunner, initialized_db: str, config_file: str
    ) -> None:
        """Test acknowledge command sends reply for interview email."""
        mock_client = MagicMock()
        mock_client.send_reply.return_value = True

        with patch("jea.cli.create_client", return_value=mock_client), \
             patch("jea.cli.send_templated_reply", return_value=True):
            result = runner.invoke(
                cli,
                ["--config", config_file, "acknowledge", "test-123"],
            )
            assert result.exit_code == 0
            assert "acknowledged" in result.output.lower() or "reply sent" in result.output.lower()

    def test_acknowledge_command_not_interview(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test acknowledge command rejects non-interview emails."""
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        # Insert a non-interview email (JD_RECEIVED)
        jd_email = Email(
            message_id="jd-001",
            subject="Job Description - Backend Engineer",
            sender="hr@company.com",
            to="me@gmail.com",
            date=datetime(2025, 3, 1, 10, 0),
            body_text="Here is the job description.",
            email_type=EmailType.JD_RECEIVED,
        )
        insert_email(db_path, jd_email)

        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            f"db_path: {db_path}\n"
            f"log_level: DEBUG\n"
            f"log_file: null\n"
        )

        result = runner.invoke(
            cli,
            ["--config", str(config_path), "acknowledge", "jd-001"],
        )
        assert result.exit_code == 0
        assert "not interview_scheduled" in result.output.lower() or "not interview" in result.output.lower()

    def test_acknowledge_command_not_found(
        self, runner: CliRunner, initialized_db: str, config_file: str
    ) -> None:
        """Test acknowledge command with non-existent email."""
        result = runner.invoke(
            cli,
            ["--config", config_file, "acknowledge", "nonexistent_id"],
        )
        assert result.exit_code == 0
        assert "not found" in result.output.lower()

    def test_acknowledge_command_duplicate_reply(
        self, runner: CliRunner, initialized_db: str, config_file: str
    ) -> None:
        """Test acknowledge command rejects duplicate replies."""
        # Mark the email as REPLIED and log a reply
        update_email_status(initialized_db, "test-123", EmailStatus.REPLIED)
        log_reply(initialized_db, "test-123", "interview_ack")

        result = runner.invoke(
            cli,
            ["--config", config_file, "acknowledge", "test-123"],
        )
        assert result.exit_code == 0
        assert "already sent" in result.output.lower() or "reply already" in result.output.lower()

    # --- Prefix resolution tests ---

    def test_show_prefix_unique_match(
        self, runner: CliRunner, multi_email_db: tuple[str, str]
    ) -> None:
        """Test show command resolves a unique prefix match."""
        db_path, config_file = multi_email_db
        # 'beta-001-jd' uniquely matches prefix 'beta'
        result = runner.invoke(
            cli,
            ["--config", config_file, "show", "beta"],
        )
        assert result.exit_code == 0
        assert "JD at Beta Inc" in result.output

    def test_show_prefix_full_id_still_works(
        self, runner: CliRunner, multi_email_db: tuple[str, str]
    ) -> None:
        """Test show command still works with full message ID."""
        db_path, config_file = multi_email_db
        result = runner.invoke(
            cli,
            ["--config", config_file, "show", "alpha-001-interview"],
        )
        assert result.exit_code == 0
        assert "Interview at Alpha Corp" in result.output

    def test_show_prefix_ambiguous(
        self, runner: CliRunner, multi_email_db: tuple[str, str]
    ) -> None:
        """Test show command with ambiguous prefix prints warning."""
        db_path, config_file = multi_email_db
        # 'alpha' matches both alpha-001 and alpha-002
        result = runner.invoke(
            cli,
            ["--config", config_file, "show", "alpha"],
        )
        assert result.exit_code == 0
        assert "multiple" in result.output.lower() or "alpha-001" in result.output

    def test_show_prefix_no_match(
        self, runner: CliRunner, multi_email_db: tuple[str, str]
    ) -> None:
        """Test show command with non-existent prefix prints not found."""
        db_path, config_file = multi_email_db
        result = runner.invoke(
            cli,
            ["--config", config_file, "show", "zzz-nonexistent"],
        )
        assert result.exit_code == 0
        assert "not found" in result.output.lower()

    def test_reject_prefix_unique_match(
        self, runner: CliRunner, multi_email_db: tuple[str, str]
    ) -> None:
        """Test reject command resolves a unique prefix match."""
        db_path, config_file = multi_email_db
        result = runner.invoke(
            cli,
            ["--config", config_file, "reject", "beta"],
        )
        assert result.exit_code == 0
        assert "rejected" in result.output.lower()

    def test_approve_prefix_unique_match(
        self, runner: CliRunner, multi_email_db: tuple[str, str]
    ) -> None:
        """Test approve command resolves a unique prefix match."""
        db_path, config_file = multi_email_db
        result = runner.invoke(
            cli,
            ["--config", config_file, "approve", "beta", "--no-reply"],
        )
        assert result.exit_code == 0
        assert "approved" in result.output.lower()

    def test_acknowledge_prefix_unique_match(
        self, runner: CliRunner, multi_email_db: tuple[str, str]
    ) -> None:
        """Test acknowledge command resolves a unique prefix match for interview email."""
        db_path, config_file = multi_email_db
        # Insert an interview template for the DB
        insert_template(db_path, ReplyTemplate(
            name="interview_ack",
            subject_template="Re: {{ subject }}",
            body_template="Thanks for the interview.",
            email_types=[EmailType.INTERVIEW_SCHEDULED],
        ))
        with patch("jea.cli.create_client") as mock_create, \
             patch("jea.cli.send_templated_reply", return_value=True):
            mock_create.return_value = MagicMock()
            result = runner.invoke(
                cli,
                ["--config", config_file, "acknowledge", "alpha-001"],
            )
            assert result.exit_code == 0
            assert "acknowledged" in result.output.lower() or "reply sent" in result.output.lower()

    def test_reject_prefix_ambiguous(
        self, runner: CliRunner, multi_email_db: tuple[str, str]
    ) -> None:
        """Test reject command with ambiguous prefix does not reject."""
        db_path, config_file = multi_email_db
        result = runner.invoke(
            cli,
            ["--config", config_file, "reject", "alpha"],
        )
        assert result.exit_code == 0
        # Should NOT contain 'rejected' since resolution failed
        assert "rejected" not in result.output.lower() or "multiple" in result.output.lower()

    def test_approve_prefix_no_match(
        self, runner: CliRunner, multi_email_db: tuple[str, str]
    ) -> None:
        """Test approve command with non-existent prefix does not approve."""
        db_path, config_file = multi_email_db
        result = runner.invoke(
            cli,
            ["--config", config_file, "approve", "zzz", "--no-reply"],
        )
        assert result.exit_code == 0
        assert "approved" not in result.output.lower()
