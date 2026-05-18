import logging

from anthropic import Anthropic

from env_config import EnvConfig
from src.config import Config, save_config
from src.constants import BOOTSTRAP_MAX_TOKENS
from src.costs import CostTracker
from src.email_digest import send_bootstrap_notice
from src.prompts import (
    BOOTSTRAP_SYSTEM_PROMPT,
    BOOTSTRAP_USER_PROMPT_TEMPLATE,
    SearchQueriesOutput,
    as_output_tool,
)

log = logging.getLogger(__name__)

MODEL = EnvConfig.anthropic_model

PROPOSE_SEARCH_QUERIES_TOOL = as_output_tool(
    "propose_search_queries",
    "Submit the 3-5 LinkedIn search queries for this candidate.",
    SearchQueriesOutput,
)


def bootstrap_search_queries(
    resume_text: str,
    config: Config,
    cost_tracker: CostTracker,
    *,
    dry_run: bool,
) -> list[str]:
    queries = _derive_queries_from_resume(resume_text, cost_tracker)
    log.info("bootstrap derived %d queries: %s", len(queries), queries)
    if dry_run:
        log.info("DRY_RUN=1 — skipping Drive config.yaml update and bootstrap email")
        return queries
    config.search_queries = queries
    save_config(config)
    send_bootstrap_notice(queries)
    return queries


def _derive_queries_from_resume(
    resume_text: str, cost_tracker: CostTracker
) -> list[str]:
    client = Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=BOOTSTRAP_MAX_TOKENS,
        system=BOOTSTRAP_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": BOOTSTRAP_USER_PROMPT_TEMPLATE.format(resume=resume_text),
            }
        ],
        tools=[PROPOSE_SEARCH_QUERIES_TOOL],
        tool_choice={"type": "tool", "name": "propose_search_queries"},
    )
    cost_tracker.track_anthropic(response)
    for block in response.content:
        if (
            getattr(block, "type", None) == "tool_use"
            and getattr(block, "name", None) == "propose_search_queries"
        ):
            return SearchQueriesOutput.model_validate(block.input).queries
    raise ValueError("model did not call propose_search_queries tool")
