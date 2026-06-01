import logging
import smtplib
from email.message import EmailMessage

from env_config import EnvConfig
from src.sources.base import JobPosting

log = logging.getLogger(__name__)

SMTP_PORT_SSL = 465


def _sheet_url() -> str:
    return f"https://docs.google.com/spreadsheets/d/{EnvConfig.google_sheet_id}/edit"


def _drive_config_url() -> str:
    return (
        f"https://drive.google.com/file/d/{EnvConfig.google_drive_config_file_id}/view"
    )


def _smtp_send(subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = EnvConfig.smtp_user
    msg["To"] = EnvConfig.recipient_email
    msg.set_content(body)

    with smtplib.SMTP_SSL(EnvConfig.smtp_host, SMTP_PORT_SSL) as server:
        server.login(EnvConfig.smtp_user, EnvConfig.smtp_pass)
        server.send_message(msg)
    log.info("sent email subject=%r", subject)


def send_digest(
    *,
    kept: list[tuple[JobPosting, dict]],
    fetched_per_source: dict[str, int],
    failed_sources: list[str],
    scored_count: int,
    relevance_threshold: int,
    cost_summary: dict,
) -> None:
    # Flag errors in the subject so a broken source can't hide behind a
    # "0 new matches" that looks like a normal quiet day.
    warn = " ⚠ source errors" if failed_sources else ""
    subject = f"Jobfinder daily — {len(kept)} new matches{warn}"
    body = _format_digest_body(
        kept=kept,
        fetched_per_source=fetched_per_source,
        failed_sources=failed_sources,
        scored_count=scored_count,
        relevance_threshold=relevance_threshold,
        cost_summary=cost_summary,
    )
    _smtp_send(subject, body)


def send_bootstrap_notice(queries: list[str]) -> None:
    subject = f"Jobfinder — bootstrapped {len(queries)} search queries"
    lines = [
        "Claude read your resume and derived these search queries:",
        "",
    ]
    lines.extend(f"  - {q}" for q in queries)
    lines.extend(
        [
            "",
            "Review (and optionally edit) config.yaml on Drive, then re-run.",
            "",
            f"Drive config: {_drive_config_url()}",
        ]
    )
    _smtp_send(subject, "\n".join(lines))


def _format_digest_body(
    *,
    kept: list[tuple[JobPosting, dict]],
    fetched_per_source: dict[str, int],
    failed_sources: list[str],
    scored_count: int,
    relevance_threshold: int,
    cost_summary: dict,
) -> str:
    lines = ["Fetched:"]
    total = 0
    for src, n in fetched_per_source.items():
        flag = "   ⚠ ERROR (fetch failed)" if src in failed_sources else ""
        lines.append(f"  {src}: {n}{flag}")
        total += n
    lines.append(f"  (total: {total})")
    if failed_sources:
        lines.append("")
        lines.append(
            f"⚠ {len(failed_sources)} source(s) errored and returned no data — "
            "this is a failure, not an empty result. Check the run logs: "
            + ", ".join(failed_sources)
        )
    lines.append(f"Scored: {scored_count}")
    lines.append(f"Kept (score >= {relevance_threshold}): {len(kept)}")
    lines.append("")

    top = sorted(
        kept,
        key=lambda ks: int(ks[1].get("relevance_score") or 0),
        reverse=True,
    )[:5]
    if top:
        lines.append("Top matches:")
        for i, (p, s) in enumerate(top, 1):
            score = int(s.get("relevance_score") or 0)
            lines.append(f"  {i}. {p.job_title} @ {p.company_name}  [{score}]")
            if p.application_link:
                lines.append(f"     {p.application_link}")
        lines.append("")

    sheet = _sheet_url()
    if sheet:
        lines.append(f"Sheet: {sheet}")

    total_cost = cost_summary.get("total_cost_usd", 0)
    lines.append(f"Today's run cost: ${total_cost:.2f}")
    return "\n".join(lines)
