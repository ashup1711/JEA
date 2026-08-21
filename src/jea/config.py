"""Configuration management with pydantic-settings and YAML loader."""

from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings


class GmailConfig(BaseSettings):
    """Gmail API configuration."""

    credentials_file: str = "credentials.json"
    token_file: str = "token.json"
    scopes: list[str] = ["https://www.googleapis.com/auth/gmail.modify"]
    poll_interval_seconds: int = 60
    max_results: int = 200
    fetch_lookback_days: int = 30


class ImapConfig(BaseSettings):
    """IMAP connection configuration."""

    host: str = "imap.gmail.com"
    port: int = 993
    username: str = ""
    password: str = ""
    use_ssl: bool = True


class SmtpConfig(BaseSettings):
    """SMTP connection configuration."""

    host: str = "smtp.gmail.com"
    port: int = 587
    username: str = ""
    password: str = ""
    use_tls: bool = True


class FilterRuleConfig(BaseSettings):
    """Filter rule configuration."""

    name: str
    keywords: list[str] = Field(default_factory=list)
    sender_domains: list[str] = Field(default_factory=list)
    sender_patterns: list[str] = Field(default_factory=list)
    subject_patterns: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)


class ReplyTemplateConfig(BaseSettings):
    """Reply template configuration."""

    name: str
    subject_template: str
    body_template: str
    email_types: list[str] = Field(default_factory=list)


class AppConfig(BaseSettings):
    """Main application configuration."""

    email_backend: str = "gmail"  # gmail | imap
    gmail: GmailConfig = Field(default_factory=GmailConfig)
    imap: ImapConfig = Field(default_factory=ImapConfig)
    smtp: SmtpConfig = Field(default_factory=SmtpConfig)
    db_path: str = "jea.db"
    log_level: str = "INFO"
    log_file: str | None = "jea.log"
    config_dir: str = "~/.jea"
    filter_rules: list[FilterRuleConfig] = Field(default_factory=list)
    reply_templates: list[ReplyTemplateConfig] = Field(default_factory=list)
    auto_acknowledge: bool = False
    sender_email: str = ""

    @classmethod
    def from_yaml(cls, path: str | Path) -> "AppConfig":
        """Load configuration from a YAML file.

        Args:
            path: Path to the YAML configuration file.

        Returns:
            Validated AppConfig instance.
        """
        path = Path(path).expanduser()
        if not path.exists():
            return cls()
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)
