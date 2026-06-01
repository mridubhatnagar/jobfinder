import json
import logging
from datetime import date
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

from env_config import EnvConfig
from src.constants import COSTS_HEADER, JOBS_HEADER, JOBS_WRAP_COLUMNS
from src.sources.base import JobPosting

log = logging.getLogger(__name__)

SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _gspread_client() -> gspread.Client:
    info = json.loads(EnvConfig.gcp_service_account_json)
    creds = Credentials.from_service_account_info(info, scopes=SHEETS_SCOPES)
    return gspread.authorize(creds)


def _open_worksheet(tab_name: str) -> gspread.Worksheet:
    client = _gspread_client()
    sh = client.open_by_key(EnvConfig.google_sheet_id)
    return sh.worksheet(tab_name)


def _ensure_header(
    ws: gspread.Worksheet,
    header: list[str],
    wrap_columns: list[str] | None = None,
) -> None:
    # Only writes if row 1 is empty — never overwrites a user-renamed header.
    # If the existing header is shorter than expected, append missing columns
    # at the end (safe — won't touch user renames in the columns that exist).
    existing = ws.row_values(1)
    if not existing:
        ws.update(values=[header], range_name="A1")
        if wrap_columns:
            ws.format(wrap_columns, {"wrapStrategy": "WRAP"})
        log.info("wrote header row + formatting to %r", ws.title)
        return
    if len(existing) < len(header):
        from gspread.utils import rowcol_to_a1

        new_cols = header[len(existing) :]
        start = rowcol_to_a1(1, len(existing) + 1)
        ws.update(values=[new_cols], range_name=start)
        log.info(
            "extended header on %r with %d new columns: %s",
            ws.title,
            len(new_cols),
            new_cols,
        )


def get_known_links() -> set[str]:
    ws = _open_worksheet("Jobs")
    col = JOBS_HEADER.index("application_link") + 1  # 1-indexed
    values = ws.col_values(col)
    if values and values[0] == "application_link":
        values = values[1:]
    known = {v for v in values if v}
    log.info("loaded %d known application_links from sheet", len(known))
    return known


def read_jobs() -> list[dict]:
    ws = _open_worksheet("Jobs")
    return ws.get_all_records()


def read_costs() -> list[dict]:
    ws = _open_worksheet("Costs")
    return ws.get_all_records()


def append_jobs(rows: list[tuple[JobPosting, dict]]) -> None:
    if not rows:
        log.info("no new jobs to write")
        return
    ws = _open_worksheet("Jobs")
    _ensure_header(ws, JOBS_HEADER, wrap_columns=JOBS_WRAP_COLUMNS)
    new_rows = [_row_for_job(p, s) for p, s in rows]
    ws.append_rows(new_rows, value_input_option="USER_ENTERED")
    log.info("appended %d rows to Jobs", len(rows))


def append_cost_row(cost_summary: dict) -> None:
    ws = _open_worksheet("Costs")
    _ensure_header(ws, COSTS_HEADER)
    row = [_serialize(cost_summary.get(col)) for col in COSTS_HEADER]
    ws.append_row(row, value_input_option="USER_ENTERED")
    log.info("appended cost row")


def _row_for_job(p: JobPosting, score: dict) -> list[Any]:
    return [
        date.today().isoformat(),
        p.source or "",
        score.get("role_category") or p.role_category or "",
        p.company_name or "",
        score.get("company_website") or "",
        p.job_title or "",
        p.location or "",
        p.posted_date.isoformat() if p.posted_date else "",
        p.experience_required or "",
        p.salary or "",
        p.application_link or "",
        bool(score.get("cover_letter_required")),
        int(score.get("relevance_score") or 0),
        score.get("relevance_reason") or "",
        ", ".join(score.get("required_skills") or []),
        ", ".join(score.get("missing_skills") or []),
        bool(score.get("resume_update_required")),
        score.get("resume_update_reason") or "",
    ]


def _serialize(v) -> Any:
    if v is None:
        return ""
    if isinstance(v, (int, float, str, bool)):
        return v
    return str(v)
