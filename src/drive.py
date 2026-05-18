import json

from google.oauth2 import service_account
from googleapiclient.discovery import build

from env_config import EnvConfig

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]


def get_drive_service():
    try:
        info = json.loads(EnvConfig.gcp_service_account_json)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"GCP_SERVICE_ACCOUNT_JSON is not valid JSON: {e}") from e
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=DRIVE_SCOPES
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)
