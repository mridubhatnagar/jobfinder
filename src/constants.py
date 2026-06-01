"""Shared constants: pipeline tuning + sheet schemas."""

# Truncate JD bodies before sending to the model. ~6000 chars is enough for any
# real JD; protects against pathological postings and keeps input tokens bounded.
JD_TRUNCATE_CHARS = 6000

# Max parallel scoring calls. 5 is well under Anthropic rate limits and balances
# throughput vs. burst risk.
MAX_CONCURRENCY = 5

# Per-call output token caps. Scoring needs room for required_skills (≤6),
# missing_skills (≤5), reason (~3 sentences), and a few short fields. Bootstrap
# returns only 3-5 short strings.
SCORING_MAX_TOKENS = 2048
BOOTSTRAP_MAX_TOKENS = 512

# Default lookback window for MCP get_stats. One week balances recency vs. having
# enough rows for the distribution buckets to be meaningful.
DEFAULT_STATS_WINDOW_DAYS = 7

# Sheet schemas — column order is load-bearing (writes index by position).
JOBS_HEADER = [
    "date_of_fetching",
    "source",
    "role_category",
    "company_name",
    "company_website",
    "job_title",
    "location",
    "posted_date",
    "experience_required",
    "salary",
    "application_link",
    "cover_letter",
    "relevance_score",
    "relevance_reason",
    "required_skills",
    "missing_skills",
    "resume_update_required",
    "resume_update_reason",
]

# relevance_reason, required_skills, missing_skills, resume_update_reason
JOBS_WRAP_COLUMNS = ["N:N", "O:O", "P:P", "R:R"]

COSTS_HEADER = [
    "run_timestamp",
    "jobs_scored",
    "apify_compute_units",
    "apify_cost_usd",
    "anthropic_input_tokens",
    "anthropic_output_tokens",
    "anthropic_cache_read_tokens",
    "anthropic_cache_creation_tokens",
    "anthropic_web_search_requests",
    "anthropic_cost_usd",
    "total_cost_usd",
    "apify_actors",  # appended at end to keep historical rows aligned
]
