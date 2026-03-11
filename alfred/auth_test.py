from google_auth import get_google_credentials

creds = get_google_credentials()
print("Auth Succesful!")
print(f"Token valid: {creds.valid}")
