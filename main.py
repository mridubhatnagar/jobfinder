import importlib
import logging
from datetime import date

from env_config import EnvConfig
from src.bootstrap import bootstrap_search_queries
from src.config import ApifySource, Config, PluginSource, load_config
from src.costs import CostTracker
from src.email_digest import send_digest
from src.filters import apply_filters
from src.logging_config import setup_logging
from src.resume import load_resume_text
from src.scoring import score_postings_sync
from src.sheet import append_cost_row, append_jobs, get_known_links
from src.sources.apify_linkedin import ApifyLinkedInSource
from src.sources.base import JobPosting, JobSource

log = logging.getLogger(__name__)


def main() -> int:
    setup_logging(logging.INFO)
    dry_run = EnvConfig.dry_run
    log.info("starting jobfinder (dry_run=%s)", dry_run)

    config = load_config()
    resume_text = load_resume_text()
    log.info("resume: %d chars", len(resume_text))

    cost_tracker = CostTracker()

    if not config.search_queries:
        log.info("config.search_queries is empty — running bootstrap")
        bootstrap_search_queries(resume_text, config, cost_tracker, dry_run=dry_run)
        log.info("bootstrap cost: %s", cost_tracker.summarize())
        log.info("bootstrap done — review config.yaml on Drive and re-run")
        return 0

    all_postings, fetched_per_source, failed_sources = _fetch_all(config, cost_tracker)
    log.info("total fetched across all sources: %d", len(all_postings))

    known_links = get_known_links()
    filtered = apply_filters(all_postings, config, known_links)
    filtered.sort(key=lambda p: p.posted_date or date.min, reverse=True)
    if len(filtered) > config.max_jobs_per_run:
        log.info(
            "capping %d -> %d (max_jobs_per_run)",
            len(filtered),
            config.max_jobs_per_run,
        )
        filtered = filtered[: config.max_jobs_per_run]

    scored = score_postings_sync(filtered, resume_text, cost_tracker)
    kept = [
        (p, s)
        for p, s in scored
        if (s.get("relevance_score") or 0) >= config.relevance_threshold
    ]
    log.info(
        "threshold %d: %d kept of %d scored",
        config.relevance_threshold,
        len(kept),
        len(scored),
    )

    summary = cost_tracker.summarize()
    log.info("cost summary: %s", summary)

    if dry_run:
        log.info(
            "DRY_RUN=1 — skipping Sheet writes and digest email "
            "(would append %d jobs + 1 cost row, send 1 email)",
            len(kept),
        )
        return 0

    append_jobs(kept)
    append_cost_row(summary)
    send_digest(
        kept=kept,
        fetched_per_source=fetched_per_source,
        failed_sources=failed_sources,
        scored_count=len(scored),
        relevance_threshold=config.relevance_threshold,
        cost_summary=summary,
    )
    log.info("done — wrote %d jobs to Sheet", len(kept))
    return 0


def _fetch_all(
    config: Config, cost_tracker: CostTracker
) -> tuple[list[JobPosting], dict[str, int], list[str]]:
    all_postings: list[JobPosting] = []
    fetched_per_source: dict[str, int] = {}
    failed_sources: list[str] = []
    for src in config.sources:
        source = _instantiate_source(src, cost_tracker)
        if source is None:
            continue
        try:
            postings = list(source.fetch_jobs(config))
            log.info("source %r yielded %d postings", src.name, len(postings))
            all_postings.extend(postings)
            fetched_per_source[src.name] = len(postings)
        except Exception:
            # A source that throws is an ERROR, not an empty result. Record it
            # separately so the digest can flag it loudly — a silent "0 fetched"
            # is exactly what hid the apify-client v3 breakage for a week.
            log.exception(
                "source %r FAILED during fetch — recording 0; this is an error, "
                "not a legitimate empty result",
                src.name,
            )
            fetched_per_source[src.name] = 0
            failed_sources.append(src.name)
    if failed_sources:
        log.error(
            "%d source(s) FAILED to fetch (reported as 0 but did NOT legitimately "
            "return zero jobs): %s",
            len(failed_sources),
            ", ".join(failed_sources),
        )
    return all_postings, fetched_per_source, failed_sources


def _instantiate_source(src, cost_tracker: CostTracker) -> JobSource | None:
    if isinstance(src, ApifySource):
        return ApifyLinkedInSource(src, cost_tracker=cost_tracker)
    if isinstance(src, PluginSource):
        try:
            importlib.import_module(src.module)
        except ImportError as e:
            log.warning(
                "plugin source %r module %s not importable, skipping: %s",
                src.name,
                src.module,
                e,
            )
            return None
        log.warning(
            "plugin source %r imported but no factory convention defined yet — skipping",
            src.name,
        )
        return None
    log.warning("unknown source type: %r", src)
    return None


if __name__ == "__main__":
    raise SystemExit(main())
