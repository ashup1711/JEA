"""Email client abstraction with Gmail API and IMAP/SMTP implementations."""

import abc
import base64
import email
import logging
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from typing import Any

from jea.config import AppConfig
from jea.exceptions import EmailFetchError, ReplySendError
from jea.oauth import get_gmail_service

logger = logging.getLogger("jea.email_client")


class EmailClient(abc.ABC):
    """Abstract base class for email clients."""

    @abc.abstractmethod
    def fetch_emails(self, since: datetime, max_results: int = 200) -> list[dict[str, Any]]:
        """Fetch emails since the given datetime.

        Args:
            since: Fetch emails newer than this datetime.
            max_results: Maximum number of emails to fetch.

        Returns:
            List of email dictionaries with standardized fields.
        """

    @abc.abstractmethod
    def get_email(self, message_id: str) -> dict[str, Any]:
        """Get a specific email by ID.

        Args:
            message_id: The unique message identifier.

        Returns:
            Email dictionary with standardized fields.
        """

    @abc.abstractmethod
    def send_reply(
        self,
        thread_id: str,
        to: str,
        subject: str,
        body: str,
        in_reply_to: str,
    ) -> bool:
        """Send a reply to an email.

        Args:
            thread_id: Thread identifier for grouping.
            to: Recipient email address.
            subject: Reply subject line.
            body: Reply body text.
            in_reply_to: Message-ID being replied to.

        Returns:
            True if reply was sent successfully.
        """

    @abc.abstractmethod
    def mark_as_read(self, message_id: str) -> None:
        """Mark an email as read.

        Args:
            message_id: The message to mark as read.
        """


class GmailClient(EmailClient):
    """Gmail API implementation of EmailClient."""

    def __init__(self, config: AppConfig) -> None:
        """Initialize Gmail client.

        Args:
            config: Application configuration.
        """
        self._config = config
        self._service: Any = None

    def _get_service(self) -> Any:
        """Get or create Gmail API service."""
        if self._service is None:
            self._service = get_gmail_service(
                self._config.gmail.credentials_file,
                self._config.gmail.token_file,
                self._config.gmail.scopes,
            )
        return self._service

    def fetch_emails(self, since: datetime, max_results: int = 200) -> list[dict[str, Any]]:
        """Fetch emails from Gmail API.

        Fetches emails from INBOX and SPAM folders, excluding sent emails.
        Follows nextPageToken to retrieve all available results across pages.

        Args:
            since: Fetch emails newer than this datetime.
            max_results: Maximum number of emails to fetch.

        Returns:
            List of email dictionaries.

        Raises:
            EmailFetchError: If fetching fails.
        """
        try:
            service = self._get_service()
            # Search in INBOX and SPAM, exclude sent emails
            query = f"after:{int(since.timestamp())} (in:inbox OR in:spam) -in:sent"

            # Safety limit to prevent infinite loops
            max_total_messages = 1000
            all_messages: list[dict[str, Any]] = []
            page_token: str | None = None

            while len(all_messages) < max_total_messages:
                remaining = max_results - len(all_messages)
                if remaining <= 0:
                    break

                request_kwargs: dict[str, Any] = {
                    "userId": "me",
                    "q": query,
                    "maxResults": min(100, remaining),
                }
                if page_token:
                    request_kwargs["pageToken"] = page_token

                results = (
                    service.users()
                    .messages()
                    .list(**request_kwargs)
                    .execute()
                )

                messages = results.get("messages", [])
                all_messages.extend(messages)

                page_token = results.get("nextPageToken")
                if not page_token:
                    break

            # Trim to the requested max_results
            all_messages = all_messages[:max_results]

            emails = []
            for msg in all_messages:
                email_data = self.get_email(msg["id"])
                emails.append(email_data)
            logger.info("Fetched %d emails from Gmail (inbox + spam)", len(emails))
            return emails
        except Exception as e:
            raise EmailFetchError(f"Failed to fetch emails from Gmail: {e}") from e

    def get_email(self, message_id: str) -> dict[str, Any]:
        """Get email from Gmail API.

        Args:
            message_id: Gmail message ID.

        Returns:
            Standardized email dictionary.

        Raises:
            EmailFetchError: If getting email fails.
        """
        try:
            service = self._get_service()
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )
            headers = {h["name"].lower(): h["value"] for h in msg["payload"]["headers"]}

            body_text = ""
            body_html = None
            if "parts" in msg["payload"]:
                for part in msg["payload"]["parts"]:
                    if part["mimeType"] == "text/plain":
                        body_text = base64.urlsafe_b64decode(part["body"]["data"]).decode()
                    elif part["mimeType"] == "text/html":
                        body_html = base64.urlsafe_b64decode(part["body"]["data"]).decode()
            elif "body" in msg["payload"] and "data" in msg["payload"]["body"]:
                body_text = base64.urlsafe_b64decode(msg["payload"]["body"]["data"]).decode()

            return {
                "message_id": msg["id"],
                "thread_id": msg.get("threadId"),
                "subject": headers.get("subject", ""),
                "sender": headers.get("from", ""),
                "to": headers.get("to", ""),
                "date": headers.get("date", ""),
                "body_text": body_text,
                "body_html": body_html,
                "labels": msg.get("labelIds", []),
            }
        except Exception as e:
            raise EmailFetchError(f"Failed to get email {message_id}: {e}") from e

    def send_reply(
        self,
        thread_id: str,
        to: str,
        subject: str,
        body: str,
        in_reply_to: str,
    ) -> bool:
        """Send reply via Gmail API.

        Args:
            thread_id: Gmail thread ID.
            to: Recipient.
            subject: Subject line.
            body: Body text.
            in_reply_to: Message-ID being replied to.

        Returns:
            True if sent successfully.

        Raises:
            ReplySendError: If sending fails.
        """
        try:
            service = self._get_service()
            message = MIMEText(body)
            message["to"] = to
            message["subject"] = subject
            message["In-Reply-To"] = in_reply_to
            message["References"] = in_reply_to

            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            body_dict = {"raw": raw, "threadId": thread_id}

            (
                service.users()
                .messages()
                .send(userId="me", body=body_dict)
                .execute()
            )
            logger.info("Reply sent to %s for thread %s", to, thread_id)
            return True
        except Exception as e:
            raise ReplySendError(f"Failed to send reply via Gmail: {e}") from e

    def mark_as_read(self, message_id: str) -> None:
        """Mark email as read via Gmail API.

        Args:
            message_id: Gmail message ID.
        """
        try:
            service = self._get_service()
            (
                service.users()
                .messages()
                .modify(
                    userId="me",
                    id=message_id,
                    body={"removeLabelIds": ["UNREAD"]},
                )
                .execute()
            )
            logger.debug("Marked email %s as read", message_id)
        except Exception as e:
            logger.warning("Failed to mark email %s as read: %s", message_id, e)


class ImapClient(EmailClient):
    """IMAP/SMTP implementation of EmailClient."""

    def __init__(self, config: AppConfig) -> None:
        """Initialize IMAP client.

        Args:
            config: Application configuration.
        """
        self._config = config
        self._connection: Any = None

    def _get_connection(self) -> Any:
        """Get or create IMAP connection."""
        if self._connection is None:
            try:
                import imapclient

                self._connection = imapclient.IMAPClient(
                    self._config.imap.host,
                    port=self._config.imap.port,
                    ssl=self._config.imap.use_ssl,
                )
                self._connection.login(
                    self._config.imap.username,
                    self._config.imap.password,
                )
                logger.info("Connected to IMAP server %s", self._config.imap.host)
            except Exception as e:
                raise EmailFetchError(f"Failed to connect to IMAP: {e}") from e
        return self._connection

    def fetch_emails(self, since: datetime, max_results: int = 200) -> list[dict[str, Any]]:
        """Fetch emails via IMAP from INBOX and SPAM folders, excluding sent emails.

        Args:
            since: Fetch emails newer than this datetime.
            max_results: Maximum number of emails to fetch.

        Returns:
            List of email dictionaries.

        Raises:
            EmailFetchError: If fetching fails.
        """
        try:
            conn = self._get_connection()
            
            # Gmail IMAP folder names for spam
            spam_folders = ["[Gmail]/Spam", "SPAM", "Junk", "Junk E-mail"]
            
            # Folders to search: INBOX and SPAM
            folders_to_search = ["INBOX"]
            
            # Find the correct spam folder name
            available_folders = conn.list_folders()
            for folder_name in spam_folders:
                for flags, delimiter, name in available_folders:
                    if folder_name.lower() in name.lower():
                        folders_to_search.append(name)
                        break
                else:
                    continue
                break
            
            emails = []
            seen_message_ids = set()
            
            for folder in folders_to_search:
                conn.select_folder(folder)
                messages = conn.search(["SINCE", since.date()])
                messages = messages[-max_results:]
                
                for uid in messages:
                    # Skip if already seen (deduplication)
                    if uid in seen_message_ids:
                        continue
                    seen_message_ids.add(uid)
                    
                    fetch_data = conn.fetch([uid], ["RFC822", "FLAGS", "ENVELOPE"])
                    raw_email = fetch_data[uid][b"RFC822"]
                    msg = email.message_from_bytes(raw_email)
                    
                    # Skip sent emails (check if \Sent flag is present)
                    flags = fetch_data[uid].get(b"FLAGS", [])
                    if b"\\Sent" in flags:
                        logger.debug("Skipping sent email: %s", uid)
                        continue
                    
                    # Also skip by checking From address matches configured username
                    from_addr = msg.get("From", "")
                    if self._config.imap.username.lower() in from_addr.lower():
                        logger.debug("Skipping self-sent email: %s", uid)
                        continue

                    body_text = ""
                    body_html = None
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                payload = part.get_payload(decode=True)
                                if payload is not None:
                                    body_text = payload.decode()  # type: ignore[union-attr]
                            elif part.get_content_type() == "text/html":
                                payload = part.get_payload(decode=True)
                                if payload is not None:
                                    body_html = payload.decode()  # type: ignore[union-attr]
                    else:
                        payload = msg.get_payload(decode=True)
                        if payload is not None:
                            body_text = payload.decode()  # type: ignore[union-attr]

                    # Add folder info to labels
                    labels = [folder]

                    emails.append(
                        {
                            "message_id": str(uid),
                            "thread_id": None,
                            "subject": msg.get("Subject", ""),
                            "sender": msg.get("From", ""),
                            "to": msg.get("To", ""),
                            "date": msg.get("Date", ""),
                            "body_text": body_text,
                            "body_html": body_html,
                            "labels": labels,
                        }
                    )
            
            logger.info("Fetched %d emails via IMAP (inbox + spam)", len(emails))
            return emails
        except Exception as e:
            if isinstance(e, EmailFetchError):
                raise
            raise EmailFetchError(f"Failed to fetch emails via IMAP: {e}") from e

    def get_email(self, message_id: str) -> dict[str, Any]:
        """Get email via IMAP.

        Args:
            message_id: IMAP UID.

        Returns:
            Email dictionary.

        Raises:
            EmailFetchError: If getting email fails.
        """
        try:
            conn = self._get_connection()
            fetch_data = conn.fetch([int(message_id)], ["RFC822"])
            raw_email = fetch_data[int(message_id)][b"RFC822"]
            msg = email.message_from_bytes(raw_email)

            body_text = ""
            body_html = None
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload is not None:
                            body_text = payload.decode()  # type: ignore[union-attr]
                    elif part.get_content_type() == "text/html":
                        payload = part.get_payload(decode=True)
                        if payload is not None:
                            body_html = payload.decode()  # type: ignore[union-attr]
            else:
                payload = msg.get_payload(decode=True)
                if payload is not None:
                    body_text = payload.decode()  # type: ignore[union-attr]

            return {
                "message_id": message_id,
                "thread_id": None,
                "subject": msg.get("Subject", ""),
                "sender": msg.get("From", ""),
                "to": msg.get("To", ""),
                "date": msg.get("Date", ""),
                "body_text": body_text,
                "body_html": body_html,
                "labels": [],
            }
        except Exception as e:
            raise EmailFetchError(f"Failed to get email via IMAP: {e}") from e

    def send_reply(
        self,
        thread_id: str,
        to: str,
        subject: str,
        body: str,
        in_reply_to: str,
    ) -> bool:
        """Send reply via SMTP.

        Args:
            thread_id: Thread identifier (unused for IMAP).
            to: Recipient.
            subject: Subject line.
            body: Body text.
            in_reply_to: Message-ID being replied to.

        Returns:
            True if sent successfully.

        Raises:
            ReplySendError: If sending fails.
        """
        try:
            message = MIMEText(body)
            message["to"] = to
            message["subject"] = subject
            message["In-Reply-To"] = in_reply_to
            message["References"] = in_reply_to

            if self._config.smtp.use_tls:
                server = smtplib.SMTP(self._config.smtp.host, self._config.smtp.port)
                server.starttls()
            else:
                server = smtplib.SMTP(self._config.smtp.host, self._config.smtp.port)

            server.login(self._config.smtp.username, self._config.smtp.password)
            server.send_message(message)
            server.quit()
            logger.info("Reply sent to %s via SMTP", to)
            return True
        except Exception as e:
            raise ReplySendError(f"Failed to send reply via SMTP: {e}") from e

    def mark_as_read(self, message_id: str) -> None:
        """Mark email as read via IMAP.

        Args:
            message_id: IMAP UID.
        """
        try:
            conn = self._get_connection()
            conn.add_flags([int(message_id)], ["\\Seen"])
            logger.debug("Marked email %s as read", message_id)
        except Exception as e:
            logger.warning("Failed to mark email %s as read: %s", message_id, e)


def create_client(config: AppConfig) -> EmailClient:
    """Factory function to create the appropriate email client.

    Args:
        config: Application configuration.

    Returns:
        EmailClient instance based on configured backend.
    """
    if config.email_backend == "gmail":
        return GmailClient(config)
    elif config.email_backend == "imap":
        return ImapClient(config)
    else:
        raise ValueError(f"Unknown email backend: {config.email_backend}")
