import asyncio
import logging
from typing import Optional

from anthropic import AsyncAnthropic

from env_config import EnvConfig
from src.constants import JD_TRUNCATE_CHARS, MAX_CONCURRENCY, SCORING_MAX_TOKENS
from src.costs import CostTracker
from src.prompts import (
    SCORING_SYSTEM_PROMPT_TEMPLATE,
    SCORING_USER_PROMPT_TEMPLATE,
    ScoreOutput,
    as_output_tool,
)
from src.sources.base import JobPosting

log = logging.getLogger(__name__)

MODEL = EnvConfig.anthropic_model

WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 1,
}

SCORE_JOB_TOOL = as_output_tool(
    "score_job",
    "Submit the scored assessment for the candidate vs this job.",
    ScoreOutput,
)


def score_postings_sync(
    postings: list[JobPosting],
    resume_text: str,
    cost_tracker: CostTracker,
) -> list[tuple[JobPosting, dict]]:
    return asyncio.run(_score_postings_async(postings, resume_text, cost_tracker))


async def _score_postings_async(
    postings: list[JobPosting],
    resume_text: str,
    cost_tracker: CostTracker,
) -> list[tuple[JobPosting, dict]]:
    if not postings:
        return []
    client = AsyncAnthropic()
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    log.info(
        "scoring %d postings (concurrency=%d, model=%s)",
        len(postings),
        MAX_CONCURRENCY,
        MODEL,
    )
    tasks = [
        _score_one(client, semaphore, p, resume_text, cost_tracker) for p in postings
    ]
    results = await asyncio.gather(*tasks)
    successes = [r for r in results if r is not None]
    log.info("scoring complete: %d/%d succeeded", len(successes), len(postings))
    return successes


async def _score_one(
    client: AsyncAnthropic,
    semaphore: asyncio.Semaphore,
    posting: JobPosting,
    resume_text: str,
    cost_tracker: CostTracker,
) -> Optional[tuple[JobPosting, dict]]:
    async with semaphore:
        # One retry: the model occasionally skips the tool call or returns a
        # transient error. The tolerant ScoreOutput schema handles format drift;
        # this catches the rarer "didn't call score_job" / transient-API cases.
        for attempt in range(2):
            try:
                response = await client.messages.create(
                    model=MODEL,
                    max_tokens=SCORING_MAX_TOKENS,
                    system=[
                        {
                            "type": "text",
                            "text": SCORING_SYSTEM_PROMPT_TEMPLATE.format(
                                resume=resume_text
                            ),
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    messages=[
                        {
                            "role": "user",
                            "content": SCORING_USER_PROMPT_TEMPLATE.format(
                                job_title=posting.job_title,
                                company_name=posting.company_name,
                                location=posting.location,
                                description=(posting.description or "")[
                                    :JD_TRUNCATE_CHARS
                                ],
                            ),
                        }
                    ],
                    tools=[WEB_SEARCH_TOOL, SCORE_JOB_TOOL],
                    tool_choice={"type": "auto"},
                )
                cost_tracker.track_anthropic(response)
                return (posting, _extract_score(response))
            except Exception as e:
                if attempt == 0:
                    continue
                log.warning(
                    "scoring failed for company=%r role=%r: %s",
                    posting.company_name,
                    posting.role_category,
                    type(e).__name__,
                )
                return None


def _extract_score(response) -> dict:
    for block in response.content:
        if (
            getattr(block, "type", None) == "tool_use"
            and getattr(block, "name", None) == "score_job"
        ):
            return ScoreOutput.model_validate(block.input).model_dump()
    raise ValueError("model did not call score_job tool")
