"""Send templated replies using Jinja2."""

import logging

from jinja2 import Template

from jea.db import get_template_for_type, log_reply
from jea.email_client import EmailClient
from jea.exceptions import ReplySendError
from jea.models import Email, ReplyTemplate

logger = logging.getLogger("jea.replier")


def send_templated_reply(
    client: EmailClient,
    email: Email,
    template: ReplyTemplate,
    db_path: str,
    extra_context: dict[str, str] | None = None,
    sender_email: str = "",
) -> bool:
    """Render a Jinja2 template and send as a reply.

    Args:
        client: Email client instance.
        email: The email to reply to.
        template: Reply template to use.
        db_path: Path to the database for logging.
        extra_context: Additional template variables.
        sender_email: Sender's email address for template rendering.

    Returns:
        True if reply was sent successfully.

    Raises:
        ReplySendError: If sending fails.
    """
    # Build template context
    context = {
        "company": email.extracted.company or "",
        "role": email.extracted.role or "",
        "sender_name": email.sender.split("<")[0].strip(),
        "interview_datetime": email.extracted.interview_datetime,
        "platform": email.extracted.platform or "",
        "subject": email.subject,
        "message_id": email.message_id,
        "sender_email": sender_email,
        **(extra_context or {}),
    }

    try:
        # Render templates
        subject = Template(template.subject_template).render(**context)
        body = Template(template.body_template).render(**context)

        # Send reply
        success = client.send_reply(
            thread_id=email.thread_id or email.message_id,
            to=email.sender,
            subject=subject,
            body=body,
            in_reply_to=email.message_id,
        )

        if success:
            # Log the reply
            log_reply(db_path, email.message_id, template.name)
            logger.info("Sent reply to %s using template %s", email.sender, template.name)

        return success

    except Exception as e:
        raise ReplySendError(f"Failed to send templated reply: {e}") from e


def send_auto_reply(
    client: EmailClient,
    email: Email,
    db_path: str,
    extra_context: dict[str, str] | None = None,
    sender_email: str = "",
) -> bool:
    """Send an automatic reply using the best matching template.

    Args:
        client: Email client instance.
        email: The email to reply to.
        db_path: Path to the database.
        extra_context: Additional template variables.
        sender_email: Sender's email address for template rendering.

    Returns:
        True if reply was sent, False if no matching template found.
    """
    template = get_template_for_type(db_path, email.email_type)
    if not template:
        logger.debug("No template found for email type %s", email.email_type.value)
        return False

    return send_templated_reply(client, email, template, db_path, extra_context, sender_email)
