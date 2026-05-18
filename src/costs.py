import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# Anthropic Claude Haiku 4.5 pricing (USD per million tokens).
# Source: anthropic.com/pricing. Update when Anthropic publishes new rates.
PRICING = {
    "haiku_input_per_mtok": 1.00,
    "haiku_output_per_mtok": 5.00,
    "haiku_cache_read_per_mtok": 0.10,
    "haiku_cache_write_5m_per_mtok": 1.25,
    "web_search_per_request": 0.01,  # $10 per 1,000 searches
}


class CostTracker:
    def __init__(self) -> None:
        self.jobs_scored = 0
        self.apify_compute_units = 0.0
        self.apify_cost_usd = 0.0
        self.apify_actors: set[str] = set()
        self.anthropic_input_tokens = 0
        self.anthropic_output_tokens = 0
        self.anthropic_cache_read_tokens = 0
        self.anthropic_cache_creation_tokens = 0
        self.anthropic_web_search_requests = 0

    def track_apify(
        self, run: dict, items_charged: int = 0, actor_id: str | None = None
    ) -> None:
        # Apify settles `usageTotalUsd` async — at actor.call() return time it's
        # usually 0. Compute cost deterministically from item count × the static
        # per-event pricing in the run's pricingInfo. Fall back to usageTotalUsd
        # if Apify has settled by the time we look.
        if not run:
            return
        self.apify_compute_units += float(
            (run.get("stats") or {}).get("computeUnits") or 0
        )
        per_event = ((run.get("pricingInfo") or {}).get("pricingPerEvent") or {}).get(
            "actorChargeEvents"
        ) or {}
        cost_from_items = 0.0
        for event_cfg in per_event.values():
            cost_from_items += (
                float(event_cfg.get("eventPriceUsd") or 0) * items_charged
            )
        settled = float(run.get("usageTotalUsd") or 0)
        self.apify_cost_usd += max(cost_from_items, settled)
        if actor_id:
            self.apify_actors.add(actor_id)

    def track_anthropic(self, response) -> None:
        usage = getattr(response, "usage", None)
        if not usage:
            return
        self.anthropic_input_tokens += getattr(usage, "input_tokens", 0) or 0
        self.anthropic_output_tokens += getattr(usage, "output_tokens", 0) or 0
        self.anthropic_cache_read_tokens += (
            getattr(usage, "cache_read_input_tokens", 0) or 0
        )
        self.anthropic_cache_creation_tokens += (
            getattr(usage, "cache_creation_input_tokens", 0) or 0
        )
        srv = getattr(usage, "server_tool_use", None)
        if srv:
            self.anthropic_web_search_requests += (
                getattr(srv, "web_search_requests", 0) or 0
            )
        self.jobs_scored += 1

    def summarize(self) -> dict:
        anthropic_cost = (
            self.anthropic_input_tokens / 1_000_000 * PRICING["haiku_input_per_mtok"]
            + self.anthropic_output_tokens
            / 1_000_000
            * PRICING["haiku_output_per_mtok"]
            + self.anthropic_cache_read_tokens
            / 1_000_000
            * PRICING["haiku_cache_read_per_mtok"]
            + self.anthropic_cache_creation_tokens
            / 1_000_000
            * PRICING["haiku_cache_write_5m_per_mtok"]
            + self.anthropic_web_search_requests * PRICING["web_search_per_request"]
        )
        total = self.apify_cost_usd + anthropic_cost
        return {
            "run_timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "jobs_scored": self.jobs_scored,
            "apify_compute_units": round(self.apify_compute_units, 4),
            "apify_cost_usd": round(self.apify_cost_usd, 4),
            "apify_actors": ", ".join(sorted(self.apify_actors)),
            "anthropic_input_tokens": self.anthropic_input_tokens,
            "anthropic_output_tokens": self.anthropic_output_tokens,
            "anthropic_cache_read_tokens": self.anthropic_cache_read_tokens,
            "anthropic_cache_creation_tokens": self.anthropic_cache_creation_tokens,
            "anthropic_web_search_requests": self.anthropic_web_search_requests,
            "anthropic_cost_usd": round(anthropic_cost, 4),
            "total_cost_usd": round(total, 4),
        }
