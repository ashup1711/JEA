# Job Email Assistant (JEA)

A Python CLI tool that monitors your Gmail inbox for job-related emails (interviews, job descriptions, offers, rejections), extracts structured data, classifies them, stores in SQLite, and can send templated acknowledgment replies.

## Features

- **Email Monitoring**: Poll Gmail inbox for new job-related emails
- **Smart Classification**: Automatically classify emails as interviews, offers, rejections, JDs, or follow-ups
- **Data Extraction**: Extract company names, job roles, interview dates, meeting links, and platforms
- **Filter Rules**: Configure rules to match specific senders, keywords, and patterns
- **Templated Replies**: Send Jinja2-based acknowledgment replies
- **SQLite Storage**: Persistent storage with full CRUD operations
- **Export**: Export data to CSV or JSON formats
- **Dual Backend**: Support for Gmail API (OAuth 2.0) and IMAP/SMTP fallback

## Installation

```bash
# Install in development mode
pip install -e ".[dev]"

# Or install from PyPI (when published)
pip install jea
```

## Quick Start

1. **Initialize JEA**:
   ```bash
   jea init
   ```

2. **Configure Gmail credentials**:
   - Place your `credentials.json` (from Google Cloud Console) in the project root
   - On first run, OAuth flow will open in browser

3. **Add filter rules**:
   ```bash
   jea rule interview_emails \
     --keywords "interview,schedule,technical round" \
     --domains "google.com,microsoft.com,greenhouse.io"
   ```

4. **Add reply templates**:
   ```bash
   jea template interview_ack \
     --subject "Re: {{ subject }}" \
     --body-file template.txt \
     --for-types interview_scheduled
   ```

5. **Start monitoring**:
   ```bash
   jea run
   ```

## Usage

### CLI Commands

| Command | Description |
|---------|-------------|
| `jea init` | Initialize database and configuration |
| `jea run` | Start email polling loop |
| `jea run --once` | Fetch once and exit |
| `jea list` | List emails in database |
| `jea list --type interview_scheduled` | Filter by type |
| `jea list --status pending` | Filter by status |
| `jea show <message_id>` | Show full email details |
| `jea approve <message_id>` | Approve and send reply |
| `jea approve <message_id> --no-reply` | Approve without reply |
| `jea reject <message_id>` | Reject email |
| `jea template <name> --subject "..." --body-file template.txt` | Add reply template |
| `jea rule <name> --keywords "..." --domains "..."` | Add filter rule |
| `jea config` | Show current configuration |
| `jea export --format json --output emails.json` | Export emails |
| `jea export --format csv --output emails.csv` | Export to CSV |

### Email Types

- `interview_scheduled` - Interview invitations and calendar invites
- `jd_received` - Job descriptions and role postings
- `offer` - Job offers and compensation details
- `rejection` - Rejection notifications
- `follow_up` - Follow-up and status update emails
- `other` - Uncategorized emails

### Template Variables

| Variable | Description |
|----------|-------------|
| `{{ company }}` | Company name |
| `{{ role }}` | Job role/title |
| `{{ sender_name }}` | Sender's display name |
| `{{ interview_datetime }}` | Interview date/time |
| `{{ platform }}` | Meeting platform (Zoom, Teams, etc.) |
| `{{ subject }}` | Original email subject |
| `{{ message_id }}` | Email message ID |

## Configuration

Copy `config.example.yaml` to `~/.jea/config.yaml` and update:

```yaml
email_backend: gmail  # or imap

gmail:
  credentials_file: credentials.json
  token_file: token.json
  poll_interval_seconds: 60

db_path: jea.db
log_level: INFO
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=jea

# Lint
ruff check src/

# Type check
mypy src/jea/
```

## Architecture

```
jea/
├── cli.py           # Click CLI commands
├── config.py        # Pydantic settings + YAML loader
├── db.py            # SQLite schema + CRUD operations
├── models.py        # Pydantic models
├── email_client.py  # Gmail API + IMAP/SMTP abstraction
├── oauth.py         # OAuth 2.0 flow
├── fetcher.py       # Email polling with deduplication
├── filter.py        # Rule-based filtering
├── extractor.py     # Data extraction (regex + heuristics)
├── classifier.py    # Email classification
├── replier.py       # Templated reply sending
├── exporter.py      # CSV/JSON export
├── logger.py        # Structured logging
└── exceptions.py    # Custom exceptions
```

## License

MIT
