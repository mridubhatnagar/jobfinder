import logging
from datetime import date, datetime
from typing import Iterable, Optional

from apify_client import ApifyClient

from env_config import EnvConfig
from src.config import ApifySource as ApifyConfig, Config
from src.costs import CostTracker
from src.sources.base import JobPosting, JobSource

log = logging.getLogger(__name__)


class ApifyLinkedInSource(JobSource):
    """Apify LinkedIn source — tuned for crawlworks/linkedin-jobs-scraper.

    Output field names follow crawlworks: companyName, jobTitle, jobDescription,
    applyUrl, jobUrl, postedDate, employmentType, salary, etc. The actor input
    uses `query` (not `keywords`) and supports boolean filter flags
    (fullTime/contract/midSeniorLevel/...) + timePostedRange seconds-string
    + location single-string + jobsToFetch.
    """

    def __init__(
        self,
        source_config: ApifyConfig,
        cost_tracker: Optional[CostTracker] = None,
    ):
        self.source_config = source_config
        self.cost_tracker = cost_tracker
        self.client = ApifyClient(token=EnvConfig.apify_token)

    def fetch_jobs(self, config: Config) -> Iterable[JobPosting]:
        actor = self.client.actor(self.source_config.actor)
        missing_desc = 0
        for query in config.search_queries:
            run_input = {**self.source_config.input, "query": query}
            log.info(
                "apify run: source=%s actor=%s location=%r query=%r",
                self.source_config.name,
                self.source_config.actor,
                self.source_config.input.get("location"),
                query,
            )
            run = actor.call(run_input=run_input)
            if run is None:
                log.warning("apify run returned None for query=%r", query)
                continue
            # apify-client v3 returns a typed Run object (not a dict). Convert to
            # the by-alias dict shape the rest of the pipeline and costs.track_apify
            # already expect (defaultDatasetId, stats, pricingInfo, usageTotalUsd).
            run = run.model_dump(by_alias=True)
            dataset_id = run.get("defaultDatasetId")
            if not dataset_id:
                log.warning("apify run has no defaultDatasetId for query=%r", query)
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
                    run,
                    items_charged=len(items),
                    actor_id=self.source_config.actor,
                )
            for item in items:
                posting = _to_posting(
                    item, role_category=query, source_name=self.source_config.name
                )
                if not posting.description:
                    missing_desc += 1
                yield posting
        if missing_desc:
            log.warning(
                "apify: %d postings had no description field — LLM scoring will be impaired. "
                "Check the actor's actual output schema.",
                missing_desc,
            )


def _to_posting(item: dict, role_category: str, source_name: str) -> JobPosting:
    return JobPosting(
        source=source_name,
        company_name=item.get("companyName") or "",
        job_title=item.get("jobTitle") or "",
        location=item.get("location") or "",
        # Prefer the public job-view URL — `applyUrl` is sometimes /job-apply/ID
        # which requires an authenticated apply session and silently fails.
        application_link=item.get("jobUrl") or item.get("applyUrl") or "",
        description=item.get("jobDescription") or "",
        company_website=None,  # crawlworks's companyUrl is a LinkedIn page; scoring fills the homepage via web search
        posted_date=_parse_date(item.get("postedDate")),
        salary=item.get("salary") or None,
        employment_type=_normalize_employment_type(item.get("employmentType")),
        role_category=role_category,
    )


def _normalize_employment_type(value: Optional[str]) -> Optional[str]:
    # crawlworks returns clean strings like "Full-time", "Contract", "Internship".
    # Local filter compares lowercase against config.employment_types.
    if not value:
        return None
    return value.lower()


def _parse_date(value) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            pass
    return None
