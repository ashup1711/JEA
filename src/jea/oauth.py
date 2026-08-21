"""OAuth 2.0 flow for Gmail API authentication."""

import logging
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from jea.exceptions import OAuthError

logger = logging.getLogger("jea.oauth")


def get_gmail_service(
    credentials_file: str, token_file: str, scopes: list[str]
) -> Any:
    """Authorize and return Gmail API service object.

    Args:
        credentials_file: Path to the OAuth client secrets JSON file.
        token_file: Path to store/load the user's access and refresh tokens.
        scopes: List of OAuth scopes to request.

    Returns:
        Gmail API service object.

    Raises:
        OAuthError: If authentication fails.
    """
    try:
        creds = None
        token_path = Path(token_file)
        cred_path = Path(credentials_file)

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), scopes)  # type: ignore[no-untyped-call]

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing expired OAuth token")
                creds.refresh(Request())
            else:
                if not cred_path.exists():
                    raise OAuthError(f"Credentials file not found: {credentials_file}")
                logger.info("Starting OAuth authorization flow")
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(cred_path), scopes
                )
                creds = flow.run_local_server(port=0)

            with open(token_path, "w") as f:
                f.write(creds.to_json())
            logger.info("OAuth token saved to %s", token_file)

        service = build("gmail", "v1", credentials=creds)
        logger.info("Gmail API service created successfully")
        return service

    except Exception as e:
        if isinstance(e, OAuthError):
            raise
        raise OAuthError(f"OAuth authentication failed: {e}") from e
