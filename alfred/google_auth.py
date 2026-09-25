from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from config import GOOGLE_CREDENTIALS_PATH, GOOGLE_TOKEN_PATH

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
]

LOGIN_EXPIRED = (
    "Google login has expired. On the PC, run:  py auth_test.py  "
    "(If this keeps happening weekly, the OAuth app is still in 'Testing' mode - "
    "publish it in Google Cloud Console > OAuth consent screen.)"
)


def get_google_credentials(allow_browser=False):
    """allow_browser=False inside the bot: a 7am scheduled job must never
    sit waiting for someone to click through a browser window.
    auth_test.py passes True to do the one-time login."""
    creds = None

    if GOOGLE_TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(GOOGLE_TOKEN_PATH), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            # Refresh token revoked or expired — only a fresh login fixes it
            creds = None

    if not creds or not creds.valid:
        if not allow_browser:
            raise RuntimeError(LOGIN_EXPIRED)
        flow = InstalledAppFlow.from_client_secrets_file(
            str(GOOGLE_CREDENTIALS_PATH), SCOPES
        )
        creds = flow.run_local_server(port=0)

    with open(GOOGLE_TOKEN_PATH, "w") as f:
        f.write(creds.to_json())
    return creds
