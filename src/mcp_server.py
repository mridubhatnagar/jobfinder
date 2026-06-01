import logging
import sys
from collections import Counter
from datetime import date, timedelta
from functools import wraps

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth.providers.google import GoogleProvider
from fastmcp.server.dependencies import get_access_token

from env_config import EnvConfig
from src import sheet
from src.constants import DEFAULT_STATS_WINDOW_DAYS

# stdio transport uses stdout for JSON-RPC framing. Logs go to stderr only.
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
log = logging.getLogger("jobfinder.mcp")


def _http_auth() -> tuple[GoogleProvider, frozenset[str]]:
    required = {
        "GOOGLE_OAUTH_CLIENT_ID": EnvConfig.google_oauth_client_id,
        "GOOGLE_OAUTH_CLIENT_SECRET": EnvConfig.google_oauth_client_secret,
        "MCP_BASE_URL": EnvConfig.mcp_base_url,
        "MCP_ALLOWED_EMAILS": EnvConfig.mcp_allowed_emails,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise SystemExit(f"MCP_TRANSPORT=http requires: {', '.join(missing)}")
    provider = GoogleProvider(
        client_id=EnvConfig.google_oauth_client_id,
        client_secret=EnvConfig.google_oauth_client_secret,
        base_url=EnvConfig.mcp_base_url,
        required_scopes=["openid", "email"],
    )
    allowed = frozenset(
        e.strip().lower() for e in EnvConfig.mcp_allowed_emails.split(",") if e.strip()
    )
    return provider, allowed


if EnvConfig.mcp_transport == "http":
    _auth_provider, _ALLOWED_EMAILS = _http_auth()
    mcp = FastMCP("jobfinder", auth=_auth_provider)
else:
    _ALLOWED_EMAILS = frozenset()
    mcp = FastMCP("jobfinder")


def require_allowed_email(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if _ALLOWED_EMAILS:
            token = get_access_token()
            if token is None:
                raise ToolError("Unauthenticated")
            email = (token.claims.get("email") or "").strip().lower()
            verified = token.claims.get("email_verified")
            if not verified or email not in _ALLOWED_EMAILS:
                log.warning(
                    "rejected tool call; email_verified=%s allowlisted=%s",
                    bool(verified),
                    email in _ALLOWED_EMAILS,
                )
                raise ToolError("Forbidden")
        return fn(*args, **kwargs)

    return wrapper


def _parse_date(s) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(str(s).strip())
    except ValueError:
        return None


def _to_int(v) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


@mcp.tool
@require_allowed_email
def get_jobs(
    role_category: str | None = None,
    min_score: int | None = None,
    fetched_within_days: int | None = None,
    company: str | None = None,
    location: str | None = None,
    search_text: str | None = None,
    limit: int | None = 50,
) -> list[dict]:
    """Return rows from the Jobs sheet, filtered.

    Args:
        role_category: case-insensitive substring match on the role_category column
        min_score: only rows with relevance_score >= this value
        fetched_within_days: only rows whose date_of_fetching is within the last N days
        company: case-insensitive substring match on company_name
        location: case-insensitive substring match on location
        search_text: case-insensitive substring match against job_title + relevance_reason
        limit: max rows to return (default 50; pass null for no cap)
    """
    rows = sheet.read_jobs()
    total = len(rows)

    if role_category:
        rows = [
            r
            for r in rows
            if role_category.lower() in str(r.get("role_category", "")).lower()
        ]
    if min_score is not None:
        rows = [
            r
            for r in rows
            if (s := _to_int(r.get("relevance_score"))) is not None and s >= min_score
        ]
    if fetched_within_days:
        cutoff = date.today() - timedelta(days=fetched_within_days)
        rows = [
            r
            for r in rows
            if (d := _parse_date(r.get("date_of_fetching"))) and d >= cutoff
        ]
    if company:
        rows = [
            r for r in rows if company.lower() in str(r.get("company_name", "")).lower()
        ]
    if location:
        rows = [
            r for r in rows if location.lower() in str(r.get("location", "")).lower()
        ]
    if search_text:
        needle = search_text.lower()
        rows = [
            r
            for r in rows
            if needle
            in f"{r.get('job_title', '')} {r.get('relevance_reason', '')}".lower()
        ]

    rows.sort(key=lambda r: _to_int(r.get("relevance_score")) or 0, reverse=True)
    if limit is not None:
        rows = rows[:limit]
    log.info("get_jobs returned %d/%d rows", len(rows), total)
    return rows


@mcp.tool
@require_allowed_email
def get_stats(days: int = DEFAULT_STATS_WINDOW_DAYS) -> dict:
    """Summary of fetching activity and spend over the last N days.

    Returns totals, score distribution, per-source counts, per-role counts,
    and cost summary from the Costs tab.
    """
    cutoff = date.today() - timedelta(days=days)
    jobs = sheet.read_jobs()
    costs = sheet.read_costs()

    recent_jobs = [
        r for r in jobs if (d := _parse_date(r.get("date_of_fetching"))) and d >= cutoff
    ]

    scores = [
        s for r in recent_jobs if (s := _to_int(r.get("relevance_score"))) is not None
    ]
    distribution = Counter()
    for s in scores:
        bucket = f"{(s // 10) * 10}-{(s // 10) * 10 + 9}"
        distribution[bucket] += 1

    by_source = Counter(str(r.get("source", "") or "unknown") for r in recent_jobs)
    by_role = Counter(str(r.get("role_category", "") or "unknown") for r in recent_jobs)

    recent_costs = []
    for c in costs:
        ts = str(c.get("run_timestamp", ""))[:10]
        d = _parse_date(ts)
        if d and d >= cutoff:
            recent_costs.append(c)

    total_cost = sum(float(c.get("total_cost_usd") or 0) for c in recent_costs)
    runs = len(recent_costs)

    return {
        "window_days": days,
        "jobs_count": len(recent_jobs),
        "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
        "score_distribution": dict(sorted(distribution.items())),
        "by_source": dict(by_source),
        "by_role": dict(by_role),
        "runs_in_window": runs,
        "total_cost_usd": round(total_cost, 4),
    }


if __name__ == "__main__":
    if EnvConfig.mcp_transport == "http":
        from starlette.middleware import Middleware

        from src.rate_limit import RateLimitMiddleware

        mcp.run(
            transport="http",
            host="0.0.0.0",
            port=8000,
            middleware=[Middleware(RateLimitMiddleware)],
        )
    else:
        mcp.run()
