"""Email classification based on subject and body content."""

import logging
import re

from jea.models import Email, EmailType

logger = logging.getLogger("jea.classifier")

# Known job platform sender domains for sender-based pre-classification
JOB_PLATFORM_SENDERS: list[str] = [
    "indeed.com",
    "linkedin.com",
    "glassdoor.com",
    "naukri.com",
    "monster.com",
    "ziprecruiter.com",
    "simplyhired.com",
    "careerbuilder.com",
    "dice.com",
    "bebee.com",
    "flexjobs.com",
    "lensa.com",
    "freelancer.com",
    "cutshort.io",
    "hirist.tech",
    "foundit.in",
    "jooble.org",
    "ambitionbox.com",
    "unstop.com",
]

# Classification patterns in priority order
CLASSIFICATION_PATTERNS: dict[EmailType, list[str]] = {
    EmailType.INTERVIEW_SCHEDULED: [
        r"interview.*schedule",
        r"interview.*invite",
        r"calendar.*invite",
        r"interview.*\d{1,2}/\d{1,2}",
        r"zoom.*interview",
        r"teams.*interview",
        r"interview.*confirmation",
        r"technical.*interview",
        r"phone.*screen",
        r"onsite.*interview",
        r"virtual.*interview",
        r"interview.*link",
        r"meeting.*invite",
    ],
    EmailType.OFFER: [
        r"offer.*letter",
        r"job.*offer",
        r"we.*delighted.*offer",
        r"compensation.*package",
        r"offer.*extension",
        r"pleased.*to.*offer",
        r"offer.*position",
        r"extend.*offer",
        r"offer.*details",
        r"welcome.*aboard",
    ],
    EmailType.REJECTION: [
        r"not.*moving.*forward",
        r"decided.*not.*proceed",
        r"other.*candidates",
        r"position.*filled",
        r"regret.*inform",
        r"unfortunately.*not",
        r"not.*selected",
        r"pursuing.*other.*candidates",
        r"decided.*to.*move.*forward.*with.*other",
        r"thank.*you.*for.*your.*interest.*but",
        r"we.*have.*decided",
        r"after.*careful.*consideration",
    ],
    EmailType.JD_RECEIVED: [
        r"job.*description",
        r"role.*description",
        r"position.*details",
        r"we.*hiring",
        r"open.*position",
        r"job.*opportunity",
        r"exciting.*opportunity",
        r"new.*role",
        r"job.*opening",
        r"career.*opportunity",
        r"we.*are.*looking.*for",
        r"join.*our.*team",
    ],
    EmailType.FOLLOW_UP: [
        r"follow.*up",
        r"checking.*in",
        r"next.*steps",
        r"status.*update",
        r"any.*updates",
        r"touching.*base",
        r"wanted.*to.*follow",
        r"any.*news",
        r"application.*status",
        r"recruiting.*process",
    ],
    EmailType.JOB_PROVIDER: [
        r"linkedin.*job.*alert",
        r"indeed.*job.*recommendation",
        r"glassdoor.*job.*alert",
        r"ziprecruiter.*job.*alert",
        r"monster.*job.*alert",
        r"simplyhired",
        r"careerbuilder",
        r"dice\.com",
        r"naukri.*job.*alert",
        r"naukri.*job.*recommendation",
        r"jobs?\.naukri\.com",
        r"naukri.*new.*jobs",
        r"naukri.*matching.*jobs",
        r"naukri.*alert",
        r"recommended.*jobs.*for.*you",
        r"jobs.*you.*may.*be.*interested",
        r"new.*jobs.*match.*your.*preferences",
        r"job.*alert.*notification",
        r"your.*daily.*job.*digest",
        r"personalized.*job.*picks",
    ],
    EmailType.NEWSLETTER: [
        r"unsubscribe.*newsletter",
        r"newsletter.*unsubscribe",
        r"weekly.*digest",
        r"daily.*digest",
        r"tech.*newsletter",
        r"developer.*newsletter",
        r"engineering.*newsletter",
        r"career.*newsletter",
        r"this.*week.*in.*tech",
        r"morning.*brew",
        r"hacker.*news.*digest",
        r"tl;?dr",
        r"byte.*by.*byte",
        r"substack",
    ],
    EmailType.SOCIAL: [
        r"linkedin.*notification",
        r"linkedin.*connection.*request",
        r"linkedin.*message",
        r"twitter.*notification",
        r"facebook.*notification",
        r"github.*notification",
        r"new.*follower",
        r"someone.*mentioned.*you",
        r"commented.*on.*your.*post",
        r"connection.*request.*accepted",
        r"viewed.*your.*profile",
        r"social.*media.*update",
    ],
    EmailType.BLOG: [
        r"new.*blog.*post",
        r"new.*article.*published",
        r"medium.*story",
        r"dev\.to.*post",
        r"hashnode.*post",
        r"substack.*post",
        r"new.*publication",
        r"latest.*from.*the.*blog",
        r"weekly.*article.*roundup",
        r"blog.*update.*notification",
    ],
}


def _extract_sender_domain(sender: str) -> str:
    """Extract domain from sender email address.

    Args:
        sender: Sender email in format "Name <email@domain.com>" or "email@domain.com"

    Returns:
        Lowercase domain (e.g., 'linkedin.com') or empty string if extraction fails.
    """
    try:
        # Handle format like "John Doe <john@linkedin.com>"
        match = re.search(r"<([^>]+)>", sender)
        if match:
            email_addr = match.group(1)
        else:
            email_addr = sender

        # Extract domain from email address
        if "@" in email_addr:
            domain = email_addr.split("@")[-1].lower()
            return domain
        return ""
    except Exception:
        return ""


def classify_email(email: Email) -> EmailType:
    """Classify email using two-phase approach.

    Phase 1: Sender-based pre-classification for known job platforms.
    Phase 2: Text-based classification for other emails.

    Args:
        email: The email to classify.

    Returns:
        Classified EmailType.
    """
    # Phase 1: Sender-based pre-classification
    sender_domain = _extract_sender_domain(email.sender)
    if sender_domain and (
        any(platform in sender_domain for platform in JOB_PLATFORM_SENDERS)
        or any(sender_domain in platform for platform in JOB_PLATFORM_SENDERS)
    ):
        logger.debug(
            "Classified email %s as JOB_PROVIDER (sender domain: %s)",
            email.message_id,
            sender_domain,
        )
        return EmailType.JOB_PROVIDER

    # Phase 2: Text-based classification
    text = f"{email.subject} {email.body_text}".lower()

    for email_type, patterns in CLASSIFICATION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                logger.debug(
                    "Classified email %s as %s (matched pattern: %s)",
                    email.message_id,
                    email_type.value,
                    pattern,
                )
                return email_type

    logger.debug("Classified email %s as OTHER", email.message_id)
    return EmailType.OTHER
