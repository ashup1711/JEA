"""Tests for configuration management."""

from pathlib import Path

import yaml

from jea.config import AppConfig


class TestAppConfig:
    """Test AppConfig class."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = AppConfig()
        assert config.email_backend == "gmail"
        assert config.db_path == "jea.db"
        assert config.log_level == "INFO"
        assert config.log_file == "jea.log"
        assert config.gmail.poll_interval_seconds == 60
        assert config.gmail.max_results == 200
        assert config.imap.host == "imap.gmail.com"
        assert config.imap.port == 993
        assert config.smtp.host == "smtp.gmail.com"
        assert config.smtp.port == 587

    def test_from_yaml(self, tmp_path: Path) -> None:
        """Test loading configuration from YAML file."""
        config_data = {
            "email_backend": "imap",
            "db_path": "/tmp/test.db",
            "log_level": "DEBUG",
            "imap": {
                "host": "imap.example.com",
                "port": 993,
                "username": "test@example.com",
                "password": "secret",
            },
            "smtp": {
                "host": "smtp.example.com",
                "port": 587,
                "username": "test@example.com",
                "password": "secret",
            },
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        config = AppConfig.from_yaml(str(config_file))
        assert config.email_backend == "imap"
        assert config.db_path == "/tmp/test.db"
        assert config.log_level == "DEBUG"
        assert config.imap.host == "imap.example.com"
        assert config.imap.username == "test@example.com"

    def test_from_yaml_missing_file(self) -> None:
        """Test loading from non-existent YAML file returns defaults."""
        config = AppConfig.from_yaml("/nonexistent/config.yaml")
        assert config.email_backend == "gmail"
        assert config.db_path == "jea.db"

    def test_from_yaml_empty_file(self, tmp_path: Path) -> None:
        """Test loading from empty YAML file returns defaults."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")

        config = AppConfig.from_yaml(str(config_file))
        assert config.email_backend == "gmail"

    def test_from_yaml_partial_config(self, tmp_path: Path) -> None:
        """Test loading partial configuration."""
        config_data = {
            "email_backend": "imap",
            "db_path": "/tmp/custom.db",
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        config = AppConfig.from_yaml(str(config_file))
        assert config.email_backend == "imap"
        assert config.db_path == "/tmp/custom.db"
        assert config.log_level == "INFO"  # Default
        assert config.gmail.poll_interval_seconds == 60  # Default

    def test_config_validation(self) -> None:
        """Test configuration validation."""
        config = AppConfig(email_backend="invalid")
        assert config.email_backend == "invalid"
