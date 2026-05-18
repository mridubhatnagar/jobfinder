import io
import logging

import pypdf

from env_config import EnvConfig
from src.drive import get_drive_service

log = logging.getLogger(__name__)


def load_resume_text() -> str:
    service = get_drive_service()
    content = (
        service.files()
        .get_media(fileId=EnvConfig.google_drive_resume_file_id)
        .execute()
    )
    reader = pypdf.PdfReader(io.BytesIO(content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    log.info("loaded resume: %d pages, %d chars", len(reader.pages), len(text))
    return text
