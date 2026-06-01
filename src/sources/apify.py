"""Generic Apify job source.

One actor = one platform = one mapper. The source config selects the output
mapper by name (`mapper`), names which input key each search_query fills
(`query_param`; None for skills-based actors that take no free-text query), and
optionally caps spend per run (`max_total_charge_usd`).

Output field names differ per actor, so each platform has its own `_to_posting_*`
built from a live probe of that actor (see SCRAPER_OPTIONS.md / PLAN.md).
"""

import logging
from datetime import date, datetime
from typing import Callable, Iterable, Optional

from apify_client import ApifyClient

from env_config import EnvConfig
from src.config import ApifySource as ApifyConfig, Config
from src.costs import CostTracker
from src.sources.base import JobPosting, JobSource

log = logging.getLogger(__name__)


class ApifyJobSource(JobSource):
    """Runs one Apify actor and maps its output to JobPosting via a named mapper."""

    def __init__(
        self,
        source_config: ApifyConfig,
        cost_tracker: Optional[CostTracker] = None,
    ):
        self.source_config = source_config
        self.cost_tracker = cost_tracker
        self.client = ApifyClient(token=EnvConfig.apify_token)

    def fetch_jobs(self, config: Config) -> Iterable[JobPosting]:
        mapper = MAPPERS.get(self.source_config.mapper)
        if mapper is None:
            raise ValueError(
                f"unknown mapper {self.source_config.mapper!r} for source "
                f"{self.source_config.name!r} (known: {sorted(MAPPERS)})"
            )
        actor = self.client.actor(self.source_config.actor)
        qp = self.source_config.query_param
        # Role-query actors loop over search_queries; skills-based actors (qp=None)
        # run once with their static input.
        queries = config.search_queries if qp else [None]
        missing_desc = 0
        for query in queries:
            run_input = dict(self.source_config.input)
            if qp and query is not None:
                run_input[qp] = query
            log.info(
                "apify run: source=%s actor=%s query=%r",
                self.source_config.name,
                self.source_config.actor,
                query,
            )
            run = self._call(actor, run_input)
            if run is None:
                continue
            dataset_id = run.get("defaultDatasetId")
            if not dataset_id:
                log.warning(
                    "apify run has no defaultDatasetId for source=%s query=%r",
                    self.source_config.name,
                    query,
                )
                continue
            items = self.client.dataset(dataset_id).list_items().items
            log.info(
                "apify returned %d items for source=%s query=%r",
                len(items),
                self.source_config.name,
                query,
            )
            if self.cost_tracker is not None:
                self.cost_tracker.track_apify(
                    run, items_charged=len(items), actor_id=self.source_config.actor
                )
            for item in items:
                posting = mapper(item, query, self.source_config.name)
                if not posting.description:
                    missing_desc += 1
                yield posting
        if missing_desc:
            log.warning(
                "apify source=%s: %d postings had no description — scoring impaired",
                self.source_config.name,
                missing_desc,
            )

    def _call(self, actor, run_input: dict) -> Optional[dict]:
        kwargs = {"run_input": run_input}
        # Hard per-run charge cap (Apify-enforced) — critical for pay-per-result
        # actors whose own item caps may be inert.
        if self.source_config.max_total_charge_usd is not None:
            kwargs["max_total_charge_usd"] = self.source_config.max_total_charge_usd
        run = actor.call(**kwargs)
        if run is None:
            log.warning(
                "apify run returned None for source=%s", self.source_config.name
            )
            return None
        # apify-client v3 returns a typed Run object; convert to the by-alias dict
        # the rest of the pipeline + costs.track_apify expect.
        return run.model_dump(by_alias=True)


# --- mappers: one per actor output shape -----------------------------------


def _to_posting_crawlworks(item: dict, role: Optional[str], source: str) -> JobPosting:
    return JobPosting(
        source=source,
        company_name=item.get("companyName") or "",
        job_title=item.get("jobTitle") or "",
        location=item.get("location") or "",
        # Prefer the public job-view URL; applyUrl is sometimes an auth-gated apply link.
        application_link=item.get("jobUrl") or item.get("applyUrl") or "",
        description=item.get("jobDescription") or "",
        company_website=None,
        posted_date=_parse_date(item.get("postedDate")),
        salary=item.get("salary") or None,
        employment_type=_normalize_employment_type(item.get("employmentType")),
        role_category=role,
    )


def _to_posting_indeed(item: dict, role: Optional[str], source: str) -> JobPosting:
    jt = item.get("jobType")
    emp = (
        jt[0] if isinstance(jt, list) and jt else (jt if isinstance(jt, str) else None)
    )
    return JobPosting(
        source=source,
        company_name=item.get("company") or "",
        job_title=item.get("positionName") or "",
        location=item.get("location") or "",
        application_link=item.get("url") or item.get("externalApplyLink") or "",
        description=item.get("description") or "",
        company_website=None,
        posted_date=_parse_date(item.get("postingDateParsed")),
        salary=item.get("salary") or None,
        employment_type=_normalize_employment_type(emp),
        role_category=role,
    )


def _to_posting_naukri(item: dict, role: Optional[str], source: str) -> JobPosting:
    cd = item.get("companyDetail") or {}
    return JobPosting(
        source=source,
        company_name=cd.get("name") or item.get("staticCompanyName") or "",
        job_title=item.get("title") or "",
        location=_naukri_location(item.get("locations")),
        # staticUrl is the clean public naukri listing; url is a tracking redirect.
        application_link=item.get("staticUrl") or item.get("url") or "",
        description=item.get("description") or item.get("shortDescription") or "",
        company_website=cd.get("websiteUrl") or None,
        posted_date=_parse_date(item.get("createdDate")),
        experience_required=item.get("experienceText") or None,
        salary=_naukri_salary(item.get("salaryDetail")),
        employment_type=_normalize_employment_type(item.get("jobType")),
        role_category=role,
    )


def _to_posting_cutshort(item: dict, role: Optional[str], source: str) -> JobPosting:
    return JobPosting(
        source=source,
        company_name=item.get("company_name") or "",
        job_title=item.get("title") or "",
        location=item.get("location") or "",
        application_link=item.get("apply_url") or "",
        description=item.get("description") or "",
        company_website=None,
        posted_date=None,  # cutshort actor returns no posting date
        experience_required=item.get("experience_range") or None,
        salary=_cutshort_salary(item),
        employment_type=None,  # not provided by the actor
        role_category=role,
    )


MAPPERS: dict[str, Callable[[dict, Optional[str], str], JobPosting]] = {
    "crawlworks": _to_posting_crawlworks,
    "indeed": _to_posting_indeed,
    "naukri": _to_posting_naukri,
    "cutshort": _to_posting_cutshort,
}


# --- shared field helpers ---------------------------------------------------

# Map each platform's employment-type vocab onto config.employment_types tokens.
# Unknown values map to None (kept by the filter — never silently dropped).
_EMP_MAP = {
    "full-time": "full-time",
    "fulltime": "full-time",
    "full time": "full-time",
    "full time, permanent": "full-time",
    "permanent": "full-time",
    "contract": "long-term-contract",
    "contractual": "long-term-contract",
    "long-term-contract": "long-term-contract",
    "part-time": "part-time",
    "parttime": "part-time",
    "internship": "internship",
    "temporary": "temporary",
}


def _normalize_employment_type(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return _EMP_MAP.get(value.strip().lower())


def _naukri_location(locations) -> str:
    if not isinstance(locations, list):
        return ""
    labels = [
        l.get("label") for l in locations if isinstance(l, dict) and l.get("label")
    ]
    return ", ".join(labels)


def _naukri_salary(sd) -> Optional[str]:
    if not isinstance(sd, dict):
        return None
    label = sd.get("label")
    if label and label.strip().lower() != "not disclosed":
        return label
    lo, hi = sd.get("minimumSalary") or 0, sd.get("maximumSalary") or 0
    if lo or hi:
        return f"{lo}-{hi} {sd.get('currency') or ''}".strip()
    return None


def _cutshort_salary(item: dict) -> Optional[str]:
    lo, hi = item.get("salary_min"), item.get("salary_max")
    if lo or hi:
        return f"{lo or ''}-{hi or ''} {item.get('salary_currency') or ''}".strip()
    return None


def _parse_date(value) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        # fromisoformat (py3.11) handles both "...T...Z" and "YYYY-MM-DD HH:MM:SS".
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            pass
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            pass
    return None
