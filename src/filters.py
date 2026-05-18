import logging
from datetime import date, timedelta
from typing import Optional

from src.config import Config
from src.sources.base import JobPosting

log = logging.getLogger(__name__)


def apply_filters(
    postings: list[JobPosting],
    config: Config,
    known_links: set[str],
) -> list[JobPosting]:
    n0 = len(postings)
    log.info("pre-filter: %d postings", n0)
    postings = filter_by_age(postings, config.max_age_days)
    postings = filter_by_location(postings, config.preferred_locations)
    postings = filter_by_employment_type(postings, config.employment_types)
    postings = filter_by_experience(postings, config.experience_range)
    postings = filter_blocked_companies(postings, config.blocked_companies)
    postings = filter_by_title_keywords(postings, config.excluded_title_keywords)
    postings = dedupe(postings, known_links)
    log.info(
        "post-filter: %d kept of %d (%d dropped)", len(postings), n0, n0 - len(postings)
    )
    return postings


def filter_by_age(postings: list[JobPosting], max_age_days: int) -> list[JobPosting]:
    cutoff = date.today() - timedelta(days=max_age_days)
    before = len(postings)
    kept = [p for p in postings if p.posted_date is None or p.posted_date >= cutoff]
    log.info("filter age >= %s: %d -> %d", cutoff, before, len(kept))
    return kept


def filter_by_location(
    postings: list[JobPosting], preferred: list[str]
) -> list[JobPosting]:
    if not preferred:
        return postings
    lowered = [s.lower() for s in preferred]
    before = len(postings)
    kept = [p for p in postings if any(loc in p.location.lower() for loc in lowered)]
    log.info("filter location: %d -> %d", before, len(kept))
    return kept


def filter_by_employment_type(
    postings: list[JobPosting], allowed: list[str]
) -> list[JobPosting]:
    if not allowed:
        return postings
    allowed_set = {t.lower() for t in allowed}
    before = len(postings)
    # Unknown employment_type is kept — too aggressive to drop on missing source data.
    kept = [
        p
        for p in postings
        if p.employment_type is None or p.employment_type.lower() in allowed_set
    ]
    log.info("filter employment_type: %d -> %d", before, len(kept))
    return kept


def filter_by_experience(
    postings: list[JobPosting], range_: tuple[int, int]
) -> list[JobPosting]:
    cfg_min, cfg_max = range_
    before = len(postings)
    unparseable: list[str] = []

    def keeps(p: JobPosting) -> bool:
        if not p.experience_required:
            return True
        parsed = _parse_experience(p.experience_required)
        if parsed is None:
            unparseable.append(p.experience_required[:50])
            return True
        pmin, pmax = parsed
        return pmin <= cfg_max and pmax >= cfg_min

    kept = [p for p in postings if keeps(p)]
    if unparseable:
        log.info(
            "experience parse: %d unparseable inputs kept (sample: %s)",
            len(unparseable),
            unparseable[:5],
        )
    log.info(
        "filter experience [%d, %d]: %d -> %d", cfg_min, cfg_max, before, len(kept)
    )
    return kept


def filter_blocked_companies(
    postings: list[JobPosting], blocked: list[str]
) -> list[JobPosting]:
    if not blocked:
        return postings
    blocked_set = {c.lower() for c in blocked}
    before = len(postings)
    kept = [p for p in postings if p.company_name.lower() not in blocked_set]
    log.info("filter blocked_companies: %d -> %d", before, len(kept))
    return kept


def filter_by_title_keywords(
    postings: list[JobPosting], keywords: list[str]
) -> list[JobPosting]:
    if not keywords:
        return postings
    lowered = [k.lower() for k in keywords]
    before = len(postings)
    kept = [p for p in postings if not any(k in p.job_title.lower() for k in lowered)]
    log.info("filter title keywords: %d -> %d", before, len(kept))
    return kept


def dedupe(postings: list[JobPosting], known_links: set[str]) -> list[JobPosting]:
    # Drops postings already in the sheet AND collapses duplicates within this batch
    # (same job matched by two different search_queries).
    before = len(postings)
    seen = set(known_links)
    kept: list[JobPosting] = []
    for p in postings:
        if p.application_link in seen:
            continue
        seen.add(p.application_link)
        kept.append(p)
    log.info("dedupe (vs sheet + within batch): %d -> %d", before, len(kept))
    return kept


def _parse_experience(s: str) -> Optional[tuple[int, int]]:
    lower = s.lower()
    if "year" not in lower and "yr" not in lower:
        return None
    cleaned = s.replace("-", " ").replace("+", " ").replace("–", " ").replace("—", " ")
    nums = [int(t) for t in cleaned.split() if t.isdigit()]
    if not nums:
        return None
    lo = nums[0]
    hi = nums[1] if len(nums) > 1 else lo + 5
    if hi < lo:
        hi = lo + 5
    return (lo, hi)
