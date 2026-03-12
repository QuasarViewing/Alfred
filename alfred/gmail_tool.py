from googleapiclient.discovery import build
from google_auth import get_google_credentials
from email.mime.text import MIMEText
import base64

def get_unread_emails(max_results=10):
    try:
        creds = get_google_credentials()
        service = build("gmail", "v1", credentials=creds)
        results = service.users().messages().list(
            userId="me",
            labelIds=["UNREAD"],
            maxResults=max_results
        ).execute()

        messages = results.get("messages", [])

        if not messages:
            return "No unread emails found."
        
        output = []
        for msg in messages:
            message = service.users().messages().get(
                userId="me",
                id=msg["id"],
                format="metadata",
                metadataHeaders=["Subject", "From"]
            ).execute()
            headers = message.get("payload", {}).get("headers", [])
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
            sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown Sender")
            snippet = message.get("snippet", "")
            output.append(f"From: {sender}\nSubject: {subject}\nSnippet: {snippet}\n")
        return "\n".join(output)
    except Exception as e:
        return f"An error occurred: {e}"

def search_emails(query, max_results=10):
    try:
        creds = get_google_credentials()
        service = build("gmail", "v1", credentials=creds)
        results = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=max_results
        ).execute()
        messages = results.get("messages", [])
        if not messages:
            return "No emails found matching the query."
        
        output = []
        for msg in messages:
            message = service.users().messages().get(
                userId="me",
                id=msg["id"],
                format="metadata",
                metadataHeaders=["Subject", "From"]
            ).execute()
            headers = message.get("payload", {}).get("headers", [])
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
            sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown Sender")
            snippet = message.get("snippet", "")
            output.append(f"From: {sender}\nSubject: {subject}\nSnippet: {snippet}\n")
        return "\n".join(output)
    except Exception as e:
        return f"An error occurred: {e}"

def send_email(to, subject, body):
    try:
        creds = get_google_credentials()
        service = build("gmail", "v1", credentials=creds)
        
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        service.users().messages().send(
            userId="me",
            body={"raw":raw}
        ).execute()

        return f"Email sent to {to}."
    except Exception as e:
        return f"An error occurred: {e}"

def create_draft(to, subject, body):
    try:
        creds = get_google_credentials()
        service = build("gmail", "v1", credentials=creds)
        
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        service.users().drafts().create(
            userId="me",
            body={"message": {"raw":raw}}
        ).execute()

        return f"Draft Created {to}."
    except Exception as e:
        return f"An error occurred: {e}"

