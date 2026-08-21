"""Click CLI commands for Job Email Assistant."""

import time
from datetime import UTC, datetime
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from jea.config import AppConfig
from jea.db import (
    get_email,
    get_rules,
    get_template_for_type,
    get_templates,
    has_reply_been_sent,
    init_db,
    insert_rule,
    insert_template,
    list_emails,
    reclassify_all_emails,
    update_email_status,
)
from jea.email_client import create_client
from jea.exporter import export_to_csv, export_to_json
from jea.fetcher import fetch_new_emails
from jea.filter import filter_emails
from jea.logger import setup_logging
from jea.models import Email, EmailStatus, EmailType, FilterRule, ReplyTemplate
from jea.replier import send_auto_reply, send_templated_reply

console = Console()


def _resolve_email(db_path: str, message_id: str) -> Email | None:
    """Resolve an email by exact message ID or prefix match.

    Tries exact match first, then falls back to prefix match.
    If multiple emails match the prefix, returns None and prints ambiguity.

    Args:
        db_path: Path to the SQLite database.
        message_id: Full or truncated message ID.

    Returns:
        Email if uniquely resolved, None otherwise.
    """
    # Try exact match first
    email = get_email(db_path, message_id)
    if email:
        return email

    # Fall back to prefix match
    all_emails = list_emails(db_path, limit=10000)
    matches = [e for e in all_emails if e.message_id.startswith(message_id)]

    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        console.print(f"[yellow]Multiple emails match '{message_id}':[/yellow]")
        for m in matches:
            console.print(f"  {m.message_id}: {m.subject[:50]}")
        return None
    else:
        console.print(f"[red]Email not found: {message_id}[/red]")
        return None


def _sync_templates_from_config(config: AppConfig) -> None:
    """Load reply templates from config into the database if not already present.

    Args:
        config: Application configuration containing reply_templates.
    """
    init_db(config.db_path)
    existing = get_templates(config.db_path)
    existing_names = {t.name for t in existing}

    for tmpl_config in config.reply_templates:
        if tmpl_config.name not in existing_names:
            email_types = [EmailType(t) for t in tmpl_config.email_types]
            tmpl = ReplyTemplate(
                name=tmpl_config.name,
                subject_template=tmpl_config.subject_template,
                body_template=tmpl_config.body_template,
                email_types=email_types,
            )
            insert_template(config.db_path, tmpl)


@click.group()
@click.option("--config", "-c", default="~/.jea/config.yaml", help="Config file path")
@click.pass_context
def cli(ctx: click.Context, config: str) -> None:
    """Job Email Assistant - Monitor and manage job-related emails."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = AppConfig.from_yaml(config)
    ctx.obj["logger"] = setup_logging(
        level=ctx.obj["config"].log_level,
        log_file=ctx.obj["config"].log_file,
    )
    # Sync templates from config to database
    _sync_templates_from_config(ctx.obj["config"])


@cli.command()
@click.option("--once", is_flag=True, help="Fetch once and exit")
@click.option("--since", help="Fetch emails since this date (YYYY-MM-DD)")
@click.option("--auto-acknowledge", is_flag=True, help="Auto-acknowledge interview emails")
@click.pass_context
def run(ctx: click.Context, once: bool, since: str | None, auto_acknowledge: bool) -> None:
    """Start email polling loop."""
    config: AppConfig = ctx.obj["config"]
    logger = ctx.obj["logger"]

    # Parse since date if provided
    since_date: datetime | None = None
    if since:
        try:
            since_date = datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            console.print("[red]Invalid date format. Use YYYY-MM-DD[/red]")
            return

    # Resolve auto-acknowledge: CLI flag overrides config
    auto_ack = auto_acknowledge or config.auto_acknowledge

    # Initialize database
    init_db(config.db_path)
    logger.info("Database initialized at %s", config.db_path)

    # Create email client
    try:
        client = create_client(config)
        logger.info("Email client created (backend: %s)", config.email_backend)
    except Exception as e:
        console.print(f"[red]Failed to create email client: {e}[/red]")
        return

    # Load filter rules
    rules = get_rules(config.db_path)
    if not rules:
        console.print("[yellow]No filter rules configured. All emails will be processed.[/yellow]")

    console.print("[green]Starting email polling...[/green]")

    while True:
        try:
            # Fetch new emails
            new_emails = fetch_new_emails(
                client,
                config.db_path,
                since=since_date,
                lookback_days=config.gmail.fetch_lookback_days,
            )

            if new_emails:
                # Apply filters if rules exist
                if rules:
                    new_emails = filter_emails(new_emails, rules)

                # Display summary
                console.print(f"\n[bold green]Found {len(new_emails)} new emails[/bold green]")
                for email in new_emails:
                    type_color = {
                        EmailType.INTERVIEW_SCHEDULED: "cyan",
                        EmailType.OFFER: "green",
                        EmailType.REJECTION: "red",
                        EmailType.JD_RECEIVED: "blue",
                        EmailType.FOLLOW_UP: "yellow",
                        EmailType.JOB_PROVIDER: "magenta",
                        EmailType.NEWSLETTER: "bright_blue",
                        EmailType.SOCIAL: "bright_green",
                        EmailType.BLOG: "bright_yellow",
                        EmailType.OTHER: "white",
                    }.get(email.email_type, "white")

                    console.print(
                        f"  [{type_color}]{email.email_type.value:20}[/{type_color}] "
                        f"{email.subject[:60]:60} | {email.sender[:30]}"
                    )

                # Auto-acknowledge INTERVIEW_SCHEDULED emails if enabled
                if auto_ack:
                    try:
                        client_ack = create_client(config)
                        for email in new_emails:
                            if (
                                email.email_type == EmailType.INTERVIEW_SCHEDULED
                                and email.status == EmailStatus.PENDING
                            ):
                                if has_reply_been_sent(config.db_path, email.message_id):
                                    logger.info(
                                        "Skipping auto-acknowledge (reply already sent): %s",
                                        email.message_id,
                                    )
                                    continue

                                template = get_template_for_type(
                                    config.db_path, email.email_type
                                )
                                if not template:
                                    logger.warning(
                                        "No template for INTERVIEW_SCHEDULED, skipping: %s",
                                        email.message_id,
                                    )
                                    continue

                                try:
                                    send_templated_reply(
                                        client_ack, email, template, config.db_path,
                                        sender_email=config.sender_email,
                                    )
                                    update_email_status(
                                        config.db_path,
                                        email.message_id,
                                        EmailStatus.REPLIED,
                                    )
                                    console.print(
                                        f"[green]Auto-acknowledged: "
                                        f"{email.subject[:50]}[/green]"
                                    )
                                    logger.info(
                                        "Auto-acknowledged interview email: %s",
                                        email.message_id,
                                    )
                                except Exception as e:
                                    console.print(
                                        f"[red]Auto-acknowledge failed for "
                                        f"{email.message_id}: {e}[/red]"
                                    )
                                    logger.exception(
                                        "Auto-acknowledge failed for %s",
                                        email.message_id,
                                    )
                    except Exception as e:
                        console.print(
                            f"[red]Failed to initialize client for auto-acknowledge: "
                            f"{e}[/red]"
                        )
            else:
                console.print(".", end="")

            if once:
                break

            # Wait for next poll
            time.sleep(config.gmail.poll_interval_seconds)

        except KeyboardInterrupt:
            console.print("\n[yellow]Polling stopped by user[/yellow]")
            break
        except Exception:
            logger.exception("Error during polling")
            if once:
                break
            time.sleep(config.gmail.poll_interval_seconds)


@cli.command("list")
@click.option("--type", "email_type", help="Filter by email type")
@click.option("--status", help="Filter by status")
@click.option("--days", type=int, help="Only show emails from the last N days")
@click.option("--subject", help="Filter by subject (substring match)")
@click.option("--limit", "-n", default=50, help="Max results")
@click.pass_context
def list_cmd(ctx: click.Context, email_type: str | None, status: str | None, days: int | None, subject: str | None, limit: int) -> None:
    """List emails in database."""
    config: AppConfig = ctx.obj["config"]

    # Validate email_type if provided
    if email_type:
        try:
            EmailType(email_type)
        except ValueError:
            console.print(f"[red]Invalid email type: {email_type}[/red]")
            console.print(f"Valid types: {', '.join(t.value for t in EmailType)}")
            return

    # Validate status if provided
    if status:
        try:
            EmailStatus(status)
        except ValueError:
            console.print(f"[red]Invalid status: {status}[/red]")
            console.print(f"Valid statuses: {', '.join(s.value for s in EmailStatus)}")
            return

    emails = list_emails(config.db_path, email_type=email_type, status=status, days=days, subject=subject, limit=limit)

    if not emails:
        console.print("[yellow]No emails found[/yellow]")
        return

    # Create rich table
    table = Table(title="Job Emails")
    table.add_column("ID", style="dim", width=8)
    table.add_column("Type", width=20)
    table.add_column("Status", width=12)
    table.add_column("Subject", width=50)
    table.add_column("Sender", width=30)
    table.add_column("Date", width=20)
    table.add_column("Company", width=15)

    for email in emails:
        type_style = {
            EmailType.INTERVIEW_SCHEDULED: "cyan",
            EmailType.OFFER: "green",
            EmailType.REJECTION: "red",
            EmailType.JD_RECEIVED: "blue",
            EmailType.FOLLOW_UP: "yellow",
            EmailType.JOB_PROVIDER: "magenta",
            EmailType.NEWSLETTER: "bright_blue",
            EmailType.SOCIAL: "bright_green",
            EmailType.BLOG: "bright_yellow",
            EmailType.OTHER: "white",
        }.get(email.email_type, "white")

        status_style = {
            EmailStatus.PENDING: "yellow",
            EmailStatus.APPROVED: "green",
            EmailStatus.REJECTED: "red",
            EmailStatus.REPLIED: "blue",
        }.get(email.status, "white")

        table.add_row(
            email.message_id[:8],
            f"[{type_style}]{email.email_type.value}[/{type_style}]",
            f"[{status_style}]{email.status.value}[/{status_style}]",
            email.subject[:50],
            email.sender[:30],
            email.date.strftime("%Y-%m-%d %H:%M"),
            email.extracted.company or "-",
        )

    console.print(table)
    console.print(f"\n[dim]Showing {len(emails)} emails[/dim]")


@cli.command()
@click.argument("message_id")
@click.pass_context
def show(ctx: click.Context, message_id: str) -> None:
    """Show full email details."""
    config: AppConfig = ctx.obj["config"]
    email = _resolve_email(config.db_path, message_id)

    if not email:
        return

    # Display email details
    console.print("\n[bold]Email Details[/bold]")
    console.print(f"  Message ID:  {email.message_id}")
    console.print(f"  Thread ID:   {email.thread_id or '-'}")
    console.print(f"  Subject:     {email.subject}")
    console.print(f"  From:        {email.sender}")
    console.print(f"  To:          {email.to}")
    console.print(f"  Date:        {email.date.strftime('%Y-%m-%d %H:%M:%S')}")
    type_color = _type_color(email.email_type)
    console.print(f"  Type:        [{type_color}]{email.email_type.value}[/{type_color}]")
    status_color = _status_color(email.status)
    console.print(f"  Status:      [{status_color}]{email.status.value}[/{status_color}]")

    console.print("\n[bold]Extracted Data[/bold]")
    console.print(f"  Company:     {email.extracted.company or '-'}")
    console.print(f"  Role:        {email.extracted.role or '-'}")
    console.print(f"  Interview:   {email.extracted.interview_datetime or '-'}")
    console.print(f"  Platform:    {email.extracted.platform or '-'}")
    console.print(f"  Meeting:     {email.extracted.meeting_link or '-'}")
    console.print(f"  JD Link:     {email.extracted.jd_link or '-'}")

    if email.labels:
        console.print("\n[bold]Labels[/bold]")
        console.print(f"  {', '.join(email.labels)}")

    console.print("\n[bold]Body Preview[/bold]")
    body_preview = email.body_text[:500] + ("..." if len(email.body_text) > 500 else "")
    console.print(f"  {body_preview}")


@cli.command()
@click.argument("message_id")
@click.option("--no-reply", is_flag=True, help="Skip sending reply")
@click.pass_context
def approve(ctx: click.Context, message_id: str, no_reply: bool) -> None:
    """Mark email as approved and optionally send reply."""
    config: AppConfig = ctx.obj["config"]
    email = _resolve_email(config.db_path, message_id)

    if not email:
        return

    if email.status != EmailStatus.PENDING:
        console.print(f"[yellow]Email is already {email.status.value}[/yellow]")
        return

    # Update status
    update_email_status(config.db_path, email.message_id, EmailStatus.APPROVED)
    console.print(f"[green]Email approved: {email.subject[:50]}[/green]")

    # Send reply if requested
    if not no_reply:
        try:
            client = create_client(config)
            success = send_auto_reply(client, email, config.db_path,
                                       sender_email=config.sender_email)
            if success:
                update_email_status(config.db_path, email.message_id, EmailStatus.REPLIED)
                console.print("[green]Reply sent successfully[/green]")
            else:
                console.print("[yellow]No matching template found for reply[/yellow]")
        except Exception as e:
            console.print(f"[red]Failed to send reply: {e}[/red]")


@cli.command()
@click.argument("message_id")
@click.pass_context
def reject(ctx: click.Context, message_id: str) -> None:
    """Mark email as rejected."""
    config: AppConfig = ctx.obj["config"]
    email = _resolve_email(config.db_path, message_id)

    if not email:
        return

    if email.status != EmailStatus.PENDING:
        console.print(f"[yellow]Email is already {email.status.value}[/yellow]")
        return

    update_email_status(config.db_path, email.message_id, EmailStatus.REJECTED)
    console.print(f"[green]Email rejected: {email.subject[:50]}[/green]")


@cli.command()
@click.argument("message_id")
@click.pass_context
def acknowledge(ctx: click.Context, message_id: str) -> None:
    """Acknowledge an interview email by sending a templated reply."""
    config: AppConfig = ctx.obj["config"]
    email = _resolve_email(config.db_path, message_id)

    if not email:
        return

    if email.email_type != EmailType.INTERVIEW_SCHEDULED:
        console.print(
            f"[red]Email is not INTERVIEW_SCHEDULED (type: {email.email_type.value})[/red]"
        )
        return

    if has_reply_been_sent(config.db_path, email.message_id):
        console.print(
            f"[yellow]Reply already sent for this email: {email.subject[:50]}[/yellow]"
        )
        return

    template = get_template_for_type(config.db_path, email.email_type)
    if not template:
        console.print(
            f"[yellow]No matching template found for type: {email.email_type.value}[/yellow]"
        )
        return

    try:
        client = create_client(config)
        send_templated_reply(client, email, template, config.db_path,
                             sender_email=config.sender_email)
        update_email_status(config.db_path, email.message_id, EmailStatus.REPLIED)
        console.print(
            f"[green]Interview acknowledged and reply sent: {email.subject[:50]}[/green]"
        )
    except Exception as e:
        console.print(f"[red]Failed to send acknowledgement reply: {e}[/red]")


@cli.command()
@click.argument("name")
@click.option("--subject", required=True, help="Subject template (Jinja2)")
@click.option("--body-file", type=click.File("r"), required=True, help="Body template file")
@click.option("--for-types", help="Comma-separated email types")
@click.pass_context
def template(
    ctx: click.Context,
    name: str,
    subject: str,
    body_file: click.File,
    for_types: str | None,
) -> None:
    """Add or update a reply template."""
    config: AppConfig = ctx.obj["config"]
    init_db(config.db_path)

    # Parse email types
    email_types: list[EmailType] = []
    if for_types:
        for t in for_types.split(","):
            t = t.strip()
            try:
                email_types.append(EmailType(t))
            except ValueError:
                console.print(f"[red]Invalid email type: {t}[/red]")
                console.print(f"Valid types: {', '.join(et.value for et in EmailType)}")
                return

    # Read body template
    body_template = body_file.read()  # type: ignore

    # Create template
    tmpl = ReplyTemplate(
        name=name,
        subject_template=subject,
        body_template=body_template,
        email_types=email_types,
    )

    # Store template
    insert_template(config.db_path, tmpl)
    console.print(f"[green]Template '{name}' saved successfully[/green]")
    if email_types:
        console.print(f"  For types: {', '.join(t.value for t in email_types)}")


@cli.command("config")
@click.pass_context
def config_cmd(ctx: click.Context) -> None:
    """Show current configuration."""
    config: AppConfig = ctx.obj["config"]

    table = Table(title="JEA Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value")

    table.add_row("Email Backend", config.email_backend)
    table.add_row("Database Path", config.db_path)
    table.add_row("Log Level", config.log_level)
    table.add_row("Log File", config.log_file or "-")
    table.add_row("Config Dir", config.config_dir)

    if config.email_backend == "gmail":
        table.add_row("Gmail Credentials", config.gmail.credentials_file)
        table.add_row("Gmail Token", config.gmail.token_file)
        table.add_row("Poll Interval", f"{config.gmail.poll_interval_seconds}s")
        table.add_row("Max Results", str(config.gmail.max_results))
        table.add_row("Fetch Lookback Days", str(config.gmail.fetch_lookback_days))
    elif config.email_backend == "imap":
        table.add_row("IMAP Host", config.imap.host)
        table.add_row("IMAP Port", str(config.imap.port))
        table.add_row("IMAP Username", config.imap.username)
        table.add_row("SMTP Host", config.smtp.host)
        table.add_row("SMTP Port", str(config.smtp.port))

    console.print(table)

    # Show rules
    rules = get_rules(config.db_path)
    if rules:
        console.print(f"\n[bold]Filter Rules ({len(rules)})[/bold]")
        for rule in rules:
            console.print(f"  - {rule.name}: {len(rule.keywords)} keywords, {len(rule.sender_domains)} domains")

    # Show templates
    templates = get_templates(config.db_path)
    if templates:
        console.print(f"\n[bold]Reply Templates ({len(templates)})[/bold]")
        for tmpl in templates:
            types = ", ".join(t.value for t in tmpl.email_types) or "all"
            console.print(f"  - {tmpl.name} ({types})")


@cli.command()
@click.option("--format", "fmt", type=click.Choice(["csv", "json"]), default="json", help="Export format")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option("--type", "email_type", help="Filter by email type")
@click.option("--status", help="Filter by status")
@click.pass_context
def export(
    ctx: click.Context,
    fmt: str,
    output: str | None,
    email_type: str | None,
    status: str | None,
) -> None:
    """Export emails to CSV or JSON."""
    config: AppConfig = ctx.obj["config"]

    if fmt == "json":
        export_to_json(config.db_path, output, email_type=email_type, status=status)
    else:
        export_to_csv(config.db_path, output, email_type=email_type, status=status)

    if output:
        console.print(f"[green]Exported to {output}[/green]")


@cli.command()
@click.argument("rule_name")
@click.option("--keywords", help="Comma-separated keywords")
@click.option("--domains", help="Comma-separated sender domains")
@click.option("--sender-patterns", help="Comma-separated sender regex patterns")
@click.option("--subject-patterns", help="Comma-separated subject regex patterns")
@click.option("--exclude", help="Comma-separated exclude keywords")
@click.pass_context
def rule(
    ctx: click.Context,
    rule_name: str,
    keywords: str | None,
    domains: str | None,
    sender_patterns: str | None,
    subject_patterns: str | None,
    exclude: str | None,
) -> None:
    """Add or update a filter rule."""
    config: AppConfig = ctx.obj["config"]
    init_db(config.db_path)

    filter_rule = FilterRule(
        name=rule_name,
        keywords=[k.strip() for k in keywords.split(",")] if keywords else [],
        sender_domains=[d.strip() for d in domains.split(",")] if domains else [],
        sender_patterns=[p.strip() for p in sender_patterns.split(",")] if sender_patterns else [],
        subject_patterns=[p.strip() for p in subject_patterns.split(",")] if subject_patterns else [],
        exclude_keywords=[e.strip() for e in exclude.split(",")] if exclude else [],
    )

    insert_rule(config.db_path, filter_rule)
    console.print(f"[green]Rule '{rule_name}' saved successfully[/green]")


@cli.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Initialize JEA database and configuration."""
    config: AppConfig = ctx.obj["config"]

    # Create config directory
    config_dir = Path(config.config_dir).expanduser()
    config_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"[green]Config directory: {config_dir}[/green]")

    # Initialize database
    init_db(config.db_path)
    console.print(f"[green]Database initialized: {config.db_path}[/green]")

    console.print("\n[bold]JEA initialized successfully![/bold]")
    console.print("\nNext steps:")
    console.print("  1. Place your Gmail credentials.json in the current directory")
    console.print("  2. Add filter rules: jea rule <name> --keywords=interview,schedule")
    console.print("  3. Add reply templates: jea template <name> --subject='Re: ...' --body-file=template.txt")
    console.print("  4. Start polling: jea run")


@cli.command()
@click.option("--db-path", default=None, help="Path to database file")
@click.pass_context
def reclassify(ctx: click.Context, db_path: str | None = None) -> None:
    """Reclassify all emails using current classification logic.

    This command re-runs the classifier on all emails in the database
    and updates their email_type if the classification has changed.
    Useful after updating classification rules or fixing misclassifications.
    """
    # Use provided db_path or fall back to config
    if db_path:
        resolved_db_path = str(Path(db_path))
    else:
        config: AppConfig = ctx.obj["config"]
        resolved_db_path = config.db_path

    resolved_path = Path(resolved_db_path)
    if not resolved_path.exists():
        console.print(f"[red]Database not found: {resolved_path}[/red]")
        return

    console.print("[bold blue]Reclassifying emails...[/bold blue]")
    result = reclassify_all_emails(resolved_db_path)

    # Display results
    console.print(f"\n[bold green]Reclassification Complete![/bold green]")
    console.print(f"  Total emails: {result['total']}")
    console.print(f"  Changed: {result['changed']}")

    by_type = result.get('by_type')
    if by_type and isinstance(by_type, dict):
        console.print("\n[bold]Classification Summary:[/bold]")
        for email_type, count in sorted(by_type.items()):
            console.print(f"  {email_type}: {count}")


def _type_color(email_type: EmailType) -> str:
    """Get color for email type display."""
    return {
        EmailType.INTERVIEW_SCHEDULED: "cyan",
        EmailType.OFFER: "green",
        EmailType.REJECTION: "red",
        EmailType.JD_RECEIVED: "blue",
        EmailType.FOLLOW_UP: "yellow",
        EmailType.JOB_PROVIDER: "magenta",
        EmailType.NEWSLETTER: "bright_blue",
        EmailType.SOCIAL: "bright_green",
        EmailType.BLOG: "bright_yellow",
        EmailType.OTHER: "white",
    }.get(email_type, "white")


def _status_color(status: EmailStatus) -> str:
    """Get color for status display."""
    return {
        EmailStatus.PENDING: "yellow",
        EmailStatus.APPROVED: "green",
        EmailStatus.REJECTED: "red",
        EmailStatus.REPLIED: "blue",
    }.get(status, "white")
