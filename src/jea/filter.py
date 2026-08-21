"""Rule-based email filtering."""

import logging
import re

from jea.models import Email, FilterRule

logger = logging.getLogger("jea.filter")


def matches_rule(email: Email, rule: FilterRule) -> bool:
    """Check if an email matches a filter rule.

    An email matches a rule if it passes all enabled criteria (keywords, sender domains,
    sender patterns, subject patterns) and doesn't contain any exclude keywords.

    Args:
        email: The email to check.
        rule: The filter rule to match against.

    Returns:
        True if the email matches the rule.
    """
    text = f"{email.subject} {email.body_text}".lower()
    sender = email.sender.lower()

    # Check exclude keywords first (short-circuit)
    if rule.exclude_keywords:
        if any(kw.lower() in text for kw in rule.exclude_keywords):
            logger.debug("Email %s excluded by keyword rule %s", email.message_id, rule.name)
            return False

    # Check keywords (empty list means match all)
    keyword_match = not rule.keywords or any(
        kw.lower() in text for kw in rule.keywords
    )

    # Check sender domains (empty list means match all)
    domain_match = not rule.sender_domains or any(
        sender.endswith(f"@{d.lower()}") for d in rule.sender_domains
    )

    # Check sender patterns (regex, empty list means match all)
    sender_match = not rule.sender_patterns or any(
        re.search(p, sender, re.IGNORECASE) for p in rule.sender_patterns
    )

    # Check subject patterns (regex, empty list means match all)
    subject_match = not rule.subject_patterns or any(
        re.search(p, email.subject, re.IGNORECASE) for p in rule.subject_patterns
    )

    result = keyword_match and domain_match and sender_match and subject_match
    if result:
        logger.debug("Email %s matched rule %s", email.message_id, rule.name)
    return result


def filter_emails(emails: list[Email], rules: list[FilterRule]) -> list[Email]:
    """Filter emails by returning those that match any rule.

    Args:
        emails: List of emails to filter.
        rules: List of filter rules to apply.

    Returns:
        List of emails matching at least one rule.
    """
    if not rules:
        return emails

    filtered = [e for e in emails if any(matches_rule(e, r) for r in rules)]
    logger.info("Filtered %d emails from %d total", len(filtered), len(emails))
    return filtered
