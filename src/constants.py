"""Tuned constants for the scoring + bootstrap pipelines."""

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
