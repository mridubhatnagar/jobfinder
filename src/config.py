import io
import logging
from typing import Annotated, Literal, Union

import yaml
from googleapiclient.http import MediaIoBaseUpload
from pydantic import BaseModel, Field, field_validator

from env_config import EnvConfig
from src.drive import get_drive_service

log = logging.getLogger(__name__)


class ApifySource(BaseModel):
    type: Literal["apify"]
    name: str
    actor: str
    input: dict = Field(default_factory=dict)
    # Output→JobPosting mapper name (see src/sources/apify.py MAPPERS).
    mapper: str = "crawlworks"
    # Input key each search_query fills; None for skills-based actors that take
    # no free-text query (they run once with their static `input`).
    query_param: str | None = "query"
    # Hard per-run Apify charge cap (USD), enforced by Apify.
    max_total_charge_usd: float | None = None


class PluginSource(BaseModel):
    type: Literal["plugin"]
    name: str
    module: str


Source = Annotated[Union[ApifySource, PluginSource], Field(discriminator="type")]


class Config(BaseModel):
    preferred_locations: list[str]
    max_age_days: int = Field(gt=0)
    relevance_threshold: int = Field(ge=0, le=100)
    employment_types: list[str]
    experience_range: tuple[int, int]
    blocked_companies: list[str] = Field(default_factory=list)
    excluded_title_keywords: list[str] = Field(default_factory=list)
    max_jobs_per_run: int = Field(gt=0)
    timezone: str
    search_queries: list[str] = Field(default_factory=list)
    sources: list[Source]
    # weekday name (lowercase) -> source name. The cron fetches only that day's
    # source. Empty = legacy behavior (all sources every run).
    schedule: dict[str, str] = Field(default_factory=dict)

    @field_validator("experience_range")
    @classmethod
    def _validate_range(cls, v):
        lo, hi = v
        if lo < 0 or hi < lo:
            raise ValueError(
                f"experience_range must be [min, max] with 0 <= min <= max; got {v}"
            )
        return v


def load_config() -> Config:
    # Local override for testing config changes without touching the Drive file
    # (which the live cron reads). Set LOCAL_CONFIG_PATH to a local YAML.
    if EnvConfig.local_config_path:
        with open(EnvConfig.local_config_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        log.info("loaded config from local path %s", EnvConfig.local_config_path)
    else:
        service = get_drive_service()
        content = (
            service.files()
            .get_media(fileId=EnvConfig.google_drive_config_file_id)
            .execute()
        )
        raw = yaml.safe_load(content.decode("utf-8")) or {}
    config = Config.model_validate(raw)
    log.info(
        "loaded config: %d locations, %d sources, %d queries",
        len(config.preferred_locations),
        len(config.sources),
        len(config.search_queries),
    )
    return config


def save_config(config: Config) -> None:
    # Round-trips through pyyaml — comments and flow style in the original file
    # are not preserved. The bootstrap path tells the user to re-review on Drive.
    service = get_drive_service()
    body = yaml.safe_dump(
        config.model_dump(), sort_keys=False, default_flow_style=False
    )
    media = MediaIoBaseUpload(
        io.BytesIO(body.encode("utf-8")),
        mimetype="application/x-yaml",
        resumable=False,
    )
    service.files().update(
        fileId=EnvConfig.google_drive_config_file_id, media_body=media
    ).execute()
    log.info("config.yaml updated on Drive")
