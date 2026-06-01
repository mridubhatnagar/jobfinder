import os

from dotenv import load_dotenv

load_dotenv()


class EnvConfig:
    anthropic_model: str = os.environ["ANTHROPIC_MODEL"]
    apify_token: str = os.environ["APIFY_TOKEN"]
    gcp_service_account_json: str = os.environ["GCP_SERVICE_ACCOUNT_JSON"]
    google_sheet_id: str = os.environ["GOOGLE_SHEET_ID"]
    google_drive_config_file_id: str = os.environ["GOOGLE_DRIVE_CONFIG_FILE_ID"]
    google_drive_resume_file_id: str = os.environ["GOOGLE_DRIVE_RESUME_FILE_ID"]
    smtp_host: str = os.environ["SMTP_HOST"]
    smtp_user: str = os.environ["SMTP_USER"]
    smtp_pass: str = os.environ["SMTP_PASS"]
    recipient_email: str = os.environ["RECIPIENT_EMAIL"]
    dry_run: bool = os.environ.get("DRY_RUN", "1") == "1"
    mcp_transport: str = os.environ.get("MCP_TRANSPORT", "stdio")
    google_oauth_client_id: str = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
    google_oauth_client_secret: str = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
    mcp_base_url: str = os.environ.get("MCP_BASE_URL", "")
    mcp_allowed_emails: str = os.environ.get("MCP_ALLOWED_EMAILS", "")
