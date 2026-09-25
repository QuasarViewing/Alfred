from google_auth import get_google_credentials

# allow_browser=True: this is the one place a login window is allowed to open
creds = get_google_credentials(allow_browser=True)
print("Auth Succesful!")
print(f"Token valid: {creds.valid}")
