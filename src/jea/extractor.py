"""Extract structured data from email body using regex and heuristics."""

import logging
import re
from datetime import datetime

import html2text
from bs4 import BeautifulSoup

from jea.models import Email, ExtractedData

logger = logging.getLogger("jea.extractor")

# Common job title patterns
JOB_TITLE_PATTERNS = [
    (
        r"(?:senior|sr\.?|junior|jr\.?|lead|principal|staff)?\s*"
        r"(?:software|systems?|frontend|backend|full[\s-]?stack|devops|data|ml|ai|"
        r"machine learning|cloud|platform|security|mobile|ios|android|web|qa|test|product|project)\s*"
        r"(?:engineer|developer|architect|scientist|analyst|manager|designer|administrator|specialist|consultant)"
    ),
    r"(?:director|vp|head)\s+of\s+[\w\s]+",
    r"(?:cto|ceo|cfo|coo|vp)",
]

# Meeting platform detection
PLATFORM_KEYWORDS = {
    "zoom": ["zoom.us", "zoom.com", "zoom meeting"],
    "google meet": ["meet.google.com", "google meet", "hangouts"],
    "microsoft teams": ["teams.microsoft.com", "microsoft teams", "ms teams"],
    "webex": ["webex.com", "cisco webex"],
    "gotomeeting": ["gotomeeting.com", "goto meeting"],
    "skype": ["skype.com", "skype meeting"],
}

# Meeting link patterns
MEETING_LINK_PATTERNS = [
    r"https?://[\w.-]*zoom\.us/j/\S+",
    r"https?://meet\.google\.com/\S+",
    r"https?://teams\.microsoft\.com/l/meetup-join/\S+",
    r"https?://[\w.-]*webex\.com/\S+",
    r"https?://[\w.-]*gotomeeting\.com/\S+",
]

# JD link patterns
JD_LINK_PATTERNS = [
    r"https?://[\w.-]*(?:greenhouse\.io|lever\.co|workday\.com|icims\.com|smartrecruiters\.com|jobvite\.com)/\S+",
    r"https?://[\w.-]*(?:jobs?|careers?|positions?|hiring)/\S+",
]

# Date/time patterns
DATETIME_PATTERNS = [
    # "Jan 15, 2025 at 2:00 PM"
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2},?\s+\d{4}\s+(?:at\s+)?\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)",
    # "15/01/2025 14:00" or "01/15/2025 2:00 PM"
    r"\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?",
    # "2025-01-15 14:00"
    r"\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2}",
    # "January 15, 2025"
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2},?\s+\d{4}",
]


def _extract_company_from_sender(sender: str) -> str | None:
    """Extract company name from sender email domain.

    Args:
        sender: Sender email address (may include display name).

    Returns:
        Company name or None.
    """
    # Extract email from "Name <email>" format
    email_match = re.search(r"@([\w.-]+)", sender)
    if not email_match:
        return None

    domain = email_match.group(1).lower()
    # Remove common TLDs and subdomains
    parts = domain.split(".")
    if len(parts) >= 2:
        # Skip common email providers
        skip_domains = {"gmail", "yahoo", "hotmail", "outlook", "aol", "icloud", "mail", "email", "protonmail"}
        if parts[0] in skip_domains:
            return None
        # Return the main domain part
        return parts[-2].capitalize()
    return None


def _extract_company_from_subject(subject: str) -> str | None:
    """Extract company name from subject line.

    Args:
        subject: Email subject line.

    Returns:
        Company name or None.
    """
    # Look for "at Company" or "- Company" patterns
    patterns = [
        r"(?:at|@)\s+([A-Z][\w\s&]+?)(?:\s*[-–|]|\s*$)",
        r"[-–|]\s*([A-Z][\w\s&]+?)(?:\s*[-–|]|\s*$)",
        r"(?:from|regarding)\s+([A-Z][\w\s&]+?)(?:\s*[-–|]|\s*$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, subject)
        if match:
            company = match.group(1).strip()
            if len(company) > 2 and company[0].isupper():
                return company
    return None


def _extract_role(text: str) -> str | None:
    """Extract job role/title from text.

    Args:
        text: Text to search for job titles.

    Returns:
        Job title or None.
    """
    text_lower = text.lower()
    for pattern in JOB_TITLE_PATTERNS:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            return match.group(0).strip().title()
    return None


def _extract_datetime(text: str) -> datetime | None:
    """Extract date/time from text.

    Args:
        text: Text containing date/time information.

    Returns:
        Parsed datetime or None.
    """
    for pattern in DATETIME_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            date_str = match.group(0)
            # Try multiple formats
            formats = [
                "%B %d, %Y at %I:%M %p",
                "%B %d, %Y %I:%M %p",
                "%b %d, %Y at %I:%M %p",
                "%b %d, %Y %I:%M %p",
                "%m/%d/%Y %I:%M %p",
                "%m/%d/%Y %H:%M",
                "%d/%m/%Y %I:%M %p",
                "%d/%m/%Y %H:%M",
                "%Y-%m-%d %H:%M",
                "%B %d, %Y",
                "%b %d, %Y",
                "%B %d %Y",
                "%b %d %Y",
            ]
            for fmt in formats:
                try:
                    return datetime.strptime(date_str.strip(), fmt)
                except ValueError:
                    continue
    return None


def _extract_platform(text: str) -> str | None:
    """Detect meeting platform from text.

    Args:
        text: Text to search for platform keywords.

    Returns:
        Platform name or None.
    """
    text_lower = text.lower()
    for platform, keywords in PLATFORM_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return platform.title()
    return None


def _extract_meeting_link(text: str) -> str | None:
    """Extract meeting link from text.

    Args:
        text: Text containing meeting URLs.

    Returns:
        Meeting URL or None.
    """
    for pattern in MEETING_LINK_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).rstrip(".,;:)")
    return None


def _extract_jd_link(text: str) -> str | None:
    """Extract job description link from text.

    Args:
        text: Text containing JD URLs.

    Returns:
        JD URL or None.
    """
    for pattern in JD_LINK_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).rstrip(".,;:)")
    return None


def _html_to_text(html: str) -> str:
    """Convert HTML to plain text.

    Args:
        html: HTML content.

    Returns:
        Plain text content.
    """
    try:
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        return h.handle(html)
    except Exception:
        # Fallback to BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text(separator=" ", strip=True)


def extract_data(email: Email) -> ExtractedData:
    """Extract structured data from an email.

    Args:
        email: The email to extract data from.

    Returns:
        ExtractedData model with extracted fields.
    """
    # Use body_text, or convert body_html to text
    text = email.body_text
    if not text and email.body_html:
        text = _html_to_text(email.body_html)

    # Combine subject and body for extraction
    full_text = f"{email.subject}\n{text}"

    # Extract company (try sender first, then subject)
    company = _extract_company_from_sender(email.sender)
    if not company:
        company = _extract_company_from_subject(email.subject)

    # Extract role
    role = _extract_role(full_text)

    # Extract datetime
    interview_datetime = _extract_datetime(full_text)

    # Extract platform
    platform = _extract_platform(full_text)

    # Extract meeting link
    meeting_link = _extract_meeting_link(full_text)

    # Extract JD link
    jd_link = _extract_jd_link(full_text)

    # Get raw snippet (first 200 chars of body)
    raw_snippet = text[:200].strip() if text else None

    extracted = ExtractedData(
        company=company,
        role=role,
        interview_datetime=interview_datetime,
        platform=platform,
        meeting_link=meeting_link,
        jd_link=jd_link,
        raw_snippet=raw_snippet,
    )

    logger.debug(
        "Extracted data for %s: company=%s, role=%s, platform=%s",
        email.message_id,
        company,
        role,
        platform,
    )
    return extracted
