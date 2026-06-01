# Jobfinder — Phase 1 TODO

Derived from `PLAN.md`. 25 tasks, grouped by stage.

**Legend:** `[x]` done · `[ ]` pending · `(DEFERRED)` punted past Phase 1 launch · `(BLOCKED)` waiting on external dependency · `(OBSERVATION-GATED)` do only if real-run data surfaces a need

## Scaffold

- [x] **1. Scaffold repo: Dockerfile, compose, .gitignore, .dockerignore, .env.example, requirements.txt**
  Dockerfile (`python:3.11-slim`), `docker-compose.yml` with `jobfinder` service (bind-mount `./src` + `./main.py`, read `.env`, `DRY_RUN=1` default), `.dockerignore` (excludes `.git/`, `__pycache__/`, `data/`, `.env`, `*.pdf`, real `config.yaml`), `.gitignore` (mirrors plus local configs/resumes/data/), `.env.example` documenting required env vars, `requirements.txt` with anthropic/apify-client/gspread/google-auth/google-api-python-client/pypdf/httpx/pyyaml/pydantic/selectolax.

- [x] **2. Write `config.example.yaml` + README setup instructions**
  `config.example.yaml` documents the schema (`preferred_locations`, `max_age_days`, `relevance_threshold`, `employment_types`, `experience_range`, `blocked_companies`, `excluded_title_keywords`, `max_jobs_per_run`, `timezone`, `search_queries`, `sources`). README covers Docker prereq, fork setup, GitHub Secrets list, Drive/Sheets one-time steps, local `docker compose run --rm jobfinder` loop, and the public-repo visibility caveat.

## Core modules

- [x] **3. Implement `src/logging_config.py` with `SafeFormatter` + stack-trace scrubbing**
  Centralized logger setup. `SafeFormatter` truncates long strings. Global exception handler scrubs JD/resume content from `Exception.args` before printing. Logs counts/statuses only — no JD text, resume text, full LLM responses, full URLs, or PII. Used by every other module from the start so nothing accidentally logs sensitive data.

- [x] **4. Implement `src/config.py`: fetch `config.yaml` from Drive + pydantic validation**
  Service-account-auth Drive client downloads `config.yaml` by file ID (env `GOOGLE_DRIVE_CONFIG_FILE_ID`), parses YAML, validates with a pydantic model matching the documented schema. Also writes back to Drive (used by first-run bootstrap to persist `search_queries`). Fails loudly on missing env or invalid schema.

- [x] **5. Implement `src/resume.py`: fetch PDF from Drive + extract text with `pypdf`**
  Same service-account Drive client; download resume PDF by `GOOGLE_DRIVE_RESUME_FILE_ID`, extract text with `pypdf`, return as string for use in scoring system prompt + bootstrap. No caching to disk — fetch each run for freshness.

- [x] **6. Implement `src/sources/base.py`: `JobPosting` dataclass + `JobSource` ABC**
  `JobPosting` dataclass with all fields from the plan (`source`, `company_name`, `company_website`, `job_title`, `location`, `posted_date`, `experience_required`, `salary`, `application_link`, `description`, `employment_type`). `JobSource` ABC with `fetch_jobs(config) -> Iterable[JobPosting]`. This is the plugin contract — adding a company = new file implementing this.

- [x] **7. Investigate + select Apify LinkedIn actor**
  Chosen: `crawlworks/linkedin-jobs-scraper` ($0.0015/job base tier, no login). Initially trialed `apimaestro/linkedin-jobs-scraper-api` ($0.005/job) but switched to crawlworks for 3.3× cost reduction once a probe confirmed per-job pricing and a clean output mapping (`jobUrl`, `applyUrl`, `jobDescription`, `companyName`, `employmentType`, `salary`). Compared candidates in `SCRAPER_OPTIONS.md`.

- [x] **8. Implement `src/sources/apify_linkedin.py`: generic Apify actor caller**
  Reads `actor_id` + input schema from config; runs once per search_query in `config.search_queries`; maps actor output to `JobPosting` (with corrections for the actor's real shape: `apply_url` preferred, `salary` populated, `employment_type` extracted from `job_insights`). Tags each posting's `role_category` with the originating `search_query`.

- [ ] **9. (DEFERRED) Investigate Razorpay careers page structure**
  Revisit after Phase 1 launches with LinkedIn-only. Check `razorpay.com/jobs/` and `careers.razorpay.com`. Determine: Lever/Greenhouse-backed (clean JSON API — best), Workday (complex), or custom SPA (needs Playwright). Decision affects whether `playwright` joins `requirements.txt`.

- [ ] **10. (DEFERRED) Implement `src/sources/razorpay.py`**
  `JobSource` subclass for Razorpay using whatever the page investigation reveals. Returns `JobPosting`s tagged with `role_category`.

- [x] **11. Implement `src/filters.py`: pre-scoring filters**
  Pure functions over `List[JobPosting]`: age (`max_age_days`), location (`preferred_locations`), `employment_type`, experience (`experience_range`), `blocked_companies`, `excluded_title_keywords`. Plus dedup against the existing `application_link` set fetched from the Sheet. Each filter logs counts before/after; experience filter aggregates unparseable strings + samples them for visibility.

- [x] **12. Implement `src/sheet.py`: `gspread` read for dedup + append preserving user columns**
  Service-account auth via `gspread`. Two tabs: `Jobs` and `Costs`. `get_known_links()` reads the full `application_link` column from `Jobs`. `append_jobs(rows)` writes only the app-owned columns from the documented schema — never touches user-added columns like `status`/`notes`. `append_cost_row(row)` appends to `Costs` tab. Verified end-to-end against the real Sheet with append+delete round-trip.

- [x] **13. Implement `src/costs.py`: `CostTracker` with hardcoded `PRICING` constants**
  `CostTracker` class. `track_apify(run_metadata)` reads `computeUnits` + `usageTotalUsd`. `track_anthropic(response)` reads `response.usage` (`input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`, `server_tool_use.web_search_requests`). `summarize() -> dict` matches `Costs` tab schema and converts to USD via `PRICING` constants for Haiku 4.5. Hand-verified math.

- [x] **14. Implement `src/scoring.py`: concurrent Haiku scoring with prompt-cached resume**
  Async scorer using Anthropic SDK. Model: `claude-haiku-4-5-20251001`. Resume in system prompt with `cache_control` (5-min TTL). JD truncated to first ~6000 chars. `asyncio.Semaphore(5)`. Web search tool enabled for backfilling `company_website`. Returns structured JSON via `score_job` tool. Each call feeds `CostTracker`. End-to-end verified against the real Drive resume + 3 synthetic postings: 3/3 succeeded, scores ranked sensibly (72 / 5 / 68), web search fired only for ambiguous company names, total cost $0.07.

- [x] **15. Implement `src/email_digest.py`: SMTP send via Gmail app password**
  `smtplib.SMTP_SSL` + Gmail app password. `send_digest` builds subject `Jobfinder daily — {N} new matches` and a plain-text body with per-source counts, total fetched, scored, kept, top 5 (title/company/score/link), Sheet URL, and `Today's run cost: $X.XX`. `send_bootstrap_notice` lists the bootstrapped queries with the Drive config URL for review. Both gated by `main.py` on `DRY_RUN`. SMTP delivery not yet exercised live (will validate on first `DRY_RUN=0` bootstrap run).

- [x] **16. Implement `src/bootstrap.py`: first-run `search_query` extraction**
  If `config.search_queries` is empty, calls Haiku 4.5 with the resume via the `propose_search_queries` tool (3–5 strings, structured-output forced via `tool_choice`). On `DRY_RUN=1` logs the derived queries and exits. On `DRY_RUN=0` updates `config.search_queries` and `save_config()`s back to Drive, then sends the bootstrap notice email. Cost tracked via shared `CostTracker`. Verified live: derived 5 reasonable queries for the real resume at ~$0.002.

- [x] **17. Implement `main.py`: orchestrate the pipeline**
  Full pipeline: load config + resume → if queries empty run `bootstrap_search_queries` and exit → per-source fetch (cost-tracked) wrapped in try/except → filter (with Sheet dedup) → recency sort → cap at `max_jobs_per_run` → concurrent score → threshold-keep → on `DRY_RUN=0` append Jobs + Costs and send digest. Plugin sources whose module isn't importable log a warning and skip (graceful for the deferred razorpay entry). End-to-end validated through the bootstrap branch; full fetch-through-score path validated once Drive `search_queries` is populated.

## CI

- [x] **18. Write `.github/workflows/daily.yml`**
  Daily cron schedule (UTC) + `workflow_dispatch` for manual triggers. Workflow builds the Docker image then runs the container with `docker compose run --rm jobfinder` (or `docker run`), injecting all GitHub Secrets as env vars. Public-repo logs are sanitized by `SafeFormatter`; workflow should not echo secrets or run any extra debug commands.

## External setup

- [x] **19. One-time Google Cloud + Drive + Sheets setup**
  GCP project created; Sheets + Drive APIs enabled; service account + JSON key generated; Sheet with `Jobs` + `Costs` tabs shared with SA as Editor; `resume.pdf` uploaded + shared as Viewer; `config.yaml` uploaded + shared as Editor; all three IDs in `.env.local`.

- [x] **20. Generate Gmail app password + sign up for Apify**
  Gmail 2FA + app password generated. Apify account active with $5/month free tier.

- [x] **21. Create public GitHub repo + add all secrets**
  Create the public repo. Add secrets: `APIFY_TOKEN`, `ANTHROPIC_API_KEY`, `GCP_SERVICE_ACCOUNT_JSON` (single line), `GOOGLE_SHEET_ID`, `GOOGLE_DRIVE_RESUME_FILE_ID`, `GOOGLE_DRIVE_CONFIG_FILE_ID`, `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS`, `RECIPIENT_EMAIL`. `.gitignore` already excludes local copies.

## Verification

- [x] **22. Local dry-run via Docker Compose**
  Full live run completed (`DRY_RUN=0 docker compose run --rm jobfinder python main.py`). Funnel: 401 fetched → 227 after age → 20 after location → 17 after employment type → 17 scored → 2 kept (threshold 70) → 2 rows appended to Jobs, 1 cost row to Costs, 1 digest email sent. Apify cost tracking corrected mid-run: was returning $0 because `usageTotalUsd` settles async; now derived from `items × pricingPerEvent.eventPriceUsd` and matches exactly ($2.005 for 401 items on apimaestro). Total run cost on apimaestro ~$2.34; `maxItems` was inert on that actor (always returned ~100/query). Subsequently switched to crawlworks (~$0.60/run, 3.3× cheaper, `jobsToFetch` honored) — see task #7.

- [x] **23. First GH Actions run: bootstrap + manual verify**
  Push code. First run bootstraps `search_queries` into Drive `config.yaml` and exits with email. Review/edit bootstrapped queries on Drive. Manually trigger `workflow_dispatch` for the real first run. Verify: `Jobs` tab populated, `Costs` tab row appended, digest email received, GH Actions logs contain no PII or JD text. Live: daily cron is running and digest emails are arriving.

- [ ] **24. Threshold tuning + add-a-source smoke tests**
  Week 1: lower `relevance_threshold` to ~50, observe surfaced jobs, adjust to the right signal level. Smoke test plugin pattern: add a second Apify entry in `config.yaml` (no code change) and confirm pipeline picks it up; add a stub `src/sources/<company>.py` + register in config and confirm. Validates the "adding a source = config edit only" promise.

- [ ] **25. (OBSERVATION-GATED) Add Naukri / Indeed / Instahyre as sources**
  Trigger: ≥1 week of LinkedIn-only digests reveals gaps (specific roles or companies consistently missing). Order of effort/payoff: **Naukri first** (India-specific tech coverage, Apify actor expected), **Indeed second** (broad aggregator, Apify actor expected), **Instahyre last** (smaller platform, likely needs a custom `src/sources/instahyre.py` scraper). Code prerequisite for the first non-LinkedIn Apify source: today's `src/sources/apify_linkedin.py` hardcodes crawlworks's LinkedIn output fields in `_to_posting`. Options: (A) generalize via a `field_map` in `config.yaml`, or (B) duplicate the file per actor (e.g., `apify_indeed.py`) and register via `type: plugin`. Pick B for the first addition; A becomes worth it at 3+ Apify sources.

---

# Jobfinder — Long-running hardening

Cross-cutting changes that make the system suitable for **multi-cycle reuse** as personal infrastructure (see PLAN.md "Long-term intent"). Independent of Phase 2 MCP work — applies to the cron pipeline itself.

- [ ] **LR-1. Stamp `resume_version` on every scored job row**
  Add `resume_version` column at the end of the `Jobs` tab schema. Compute once per run from the freshly fetched resume PDF (short SHA of the bytes, or date stamp like `2026-05-20` — pick whichever is cheaper to read at a glance). Threaded through `src/scoring.py` so every scored row carries it. Required because the system runs across multiple job-search cycles — a score from an old resume version is not comparable to a score from a new one. Existing rows stay blank (no backfill).

- [ ] **LR-2. Hard daily cost ceiling that short-circuits the run**
  Add `MAX_DAILY_COST_USD` env var (default e.g. $1.00). At start of `main.py`, read today's accumulated `total_cost_usd` from the `Costs` tab; if already over the ceiling, log + exit before any paid call. Re-check after Apify cost is known but before LLM scoring starts. Bounds worst-case behavior (upstream pricing change, source flood, config typo) without changing per-call discipline.

---

# Jobfinder — Phase 2 TODO

MCP server exposing read tools over the existing `Jobs` + `Costs` sheets. Cron remains the only writer; MCP only reads.

**Confirmed scope decisions (2026-05-20):**
- Library: `fastmcp` (decorator-based, simpler stdio → HTTP transition)
- v1 tool surface: `get_jobs(filters)` + `get_stats(days)`. Narrow tools (`get_top_matches`, `get_score_reason`) are subsumed — Claude composes them via the primitive. Add later only if LLM struggles.
- No `run_pass` tool. MCP reads the Sheet only; cron is the writer.
- Sheet reads: every call (fresh, <1s at current volume; no cache).
- Build order: stdio local → HTTP local (ngrok) → Cloud Run.

## Stdio (local, fast iteration)

- [x] **P2-1. Add `fastmcp` to `requirements.txt`**
  Pinned `fastmcp>=2.0.0` (resolved to 3.3.1). Image rebuilt.

- [x] **P2-2. Add `read_jobs()` + `read_costs()` helpers to `src/sheet.py`**
  Thin wrappers around `_open_worksheet(...).get_all_records()`. Reuse the existing gspread client path; no new auth surface.

- [x] **P2-3. Create `src/mcp_server.py` with FastMCP instance + `get_jobs` + `get_stats`**
  Single file. Logging to stderr only. Schema constants moved to `src/constants.py`.

- [x] **P2-4. Local stdio smoke test against the live Sheet**
  Verified live: `get_stats(14)` → 27 jobs / 11 runs / $9.95 spend; `get_jobs(min_score=70)` → 5 matches, properly sorted.

- [x] **P2-5. Wire into Claude Code via `.mcp.json`**
  `.mcp.json` at repo root registers the `jobfinder` server with `docker compose run -T --rm jobfinder python -m src.mcp_server`. Round-trip queries from Claude Code verified against the live Sheet.

## HTTP (local, multi-client testing)

- [x] **P2-6. Switch FastMCP to HTTP transport on a local port**
  Added `MCP_TRANSPORT` env var (default `stdio`) to `env_config.py` + `.env.example`. Forwarded via `docker-compose.yml` `environment:` block. `src/mcp_server.py` `__main__` branches on transport: HTTP runs `mcp.run(transport="http", host="0.0.0.0", port=8000)`. Also added `env_config.py` to compose bind mounts so future env-var edits are live without rebuild. Validated: `MCP_TRANSPORT=http docker compose run --service-ports --rm jobfinder python -m src.mcp_server` → "Starting MCP server 'jobfinder' with transport 'http' on http://0.0.0.0:8000/mcp".

- [x] **P2-7. Expose via ngrok + connect from a remote client**
  `ngrok http 8000` → connected from claude.ai web custom connector (no auth, supervised one-off). Both tools (`get_jobs`, `get_stats`) listed and invoked successfully; end-to-end round-trip verified by asking claude.ai for the most relevant job — data came back from the live Sheet. Cross-client portability promise from PLAN.md is now validated.

- [x] **P2-8. Google OAuth + email allowlist (replaces static API key) — load-bearing**
  Scope expanded from static `Authorization: Bearer` (rejected because claude.ai web and ChatGPT custom connectors require OAuth) to full OAuth via FastMCP's `GoogleProvider` (OAuth Proxy pattern). New env vars: `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `MCP_BASE_URL`, `MCP_ALLOWED_EMAILS`. HTTP mode fails fast at startup if any are missing; stdio mode unaffected. Tools gated by `require_allowed_email` decorator that reads `email` + `email_verified` from the verified access token claims. Smoke test (local HTTP, port 8000) verified: (1) unauth POST → 401 + `WWW-Authenticate`, (2) allowed email completes OAuth and gets real Sheet data, (3) non-allowed email completes OAuth but tool call returns `Forbidden`; server logs `rejected tool call; email_verified=True allowlisted=False` with no PII leakage. GCP OAuth client configured (consent screen in Testing mode, redirect URI `http://localhost:8000/auth/callback`; Cloud Run URL gets added in P2-11).

- [x] **P2-9. Per-IP token-bucket rate limit (replaces per-key after P2-8 expanded)**
  `src/rate_limit.py` `RateLimitMiddleware` (Starlette `BaseHTTPMiddleware`): 20 req/min, burst 10, keyed by `X-Forwarded-For` leftmost (Cloud Run-compatible) with `request.client.host` fallback. Mounted globally via `mcp.run(transport="http", middleware=[Middleware(RateLimitMiddleware)])`, so it gates `/mcp`, `/authorize`, `/register`, `/token`, `/auth/callback`, and the `.well-known/*` OAuth discovery paths — pre-auth surface is bounded, not just tool calls. Returns 429 with a `Retry-After` header. In-memory bucket dict; growth unbounded under attack but fine for v1 single instance. Smoke-tested locally: rapid 30 requests → 10×401 then 20×429; separate XFF values get separate buckets; same XFF gets bucketed together regardless of source IP.

## Cloud Run deploy

- [ ] **P2-10. Add MCP server entrypoint to Dockerfile / compose**
  Same image, command overridden (`python -m src.mcp_server`). No second build path.

- [ ] **P2-11. Deploy to Cloud Run**
  `gcloud run deploy --source .` with command override. Secrets via Cloud Run env vars (or Secret Manager for `GCP_SERVICE_ACCOUNT_JSON`). Scale to zero, 1 max instance for v1.

- [ ] **P2-12. Wire production URL + API key into each MCP client**
  Claude Code `.mcp.json`, ChatGPT custom connector, claude.ai integration. Document each in README.

- [ ] **P2-13. Update README + `.env.example` for Phase 2**
  New section: local stdio dev loop, local HTTP dev loop, Cloud Run deploy, client config snippets, API key generation + rotation.

## Deferred past Phase 2 v1

- [ ] **P2-D1. (DEFERRED) Narrow convenience tools (`get_top_matches`, `get_score_reason`)**
  Add only if real usage shows the LLM stumbling on the primitive. Both are one-call wrappers over `get_jobs`.

- [ ] **P2-D2. (DEFERRED) `get_resume()` tool**
  Foundation for Phase 3 advisor. Not needed for v1 read-only chat against the Sheet.

- [ ] **P2-D3. (DEFERRED) MCP server cost tracking**
  Per-request Anthropic spend (when advisor tools land in Phase 3) + Cloud Run vCPU-seconds. Add `source` column to `Costs` tab to distinguish `cron` vs `mcp_server`.

---

# Jobfinder — Multi-platform expansion (one platform/day)

Added 2026-06-01. See PLAN.md "Multi-platform sources — one platform/day". Expand LinkedIn-only → 5 dedicated platforms, one per day on a weekday rotation, each in its own Sheet tab; cross-postings kept and managed manually via a `status` column (no automated dedup).

**Decisions to confirm:** D1 (keep same-URL re-add dedup); final actor picks per platform.

- [ ] **MP-0. Land the apify-client v3 fix first**
  The pending requirements pin + `model_dump(by_alias=True)` boundary fix + `_fetch_all` hardening must be committed/pushed and confirmed live before stacking multi-platform work on top.

- [ ] **MP-1. Probe + select dedicated actors (bounded, authorized per-run)**
  For Indeed (`misceres/indeed-scraper`), Naukri (`memo23/naukri-scraper`), Wellfound (`crawlerbros/wellfound-scraper`), CutShort (`thirdwatch/cutshort-jobs-scraper`): pull each input schema (free), then run a small probe with a hard `max_total_charge_usd` cap to confirm India coverage, output shape, and per-job cost. Record the output→`JobPosting` mapping per actor. CutShort has no reviews — scrutinize quality. LinkedIn stays on crawlworks (no probe needed).

- [ ] **MP-2. Generalize `ApifySource` (`src/config.py`)**
  Add `mapper` (default `crawlworks`), `query_param` (default `query`), `max_total_charge_usd` (optional). Add top-level `schedule` (weekday → source name) to `Config`. Backward-compatible — existing crawlworks sources unaffected.

- [ ] **MP-3. Generalize the Apify source + mapper registry**
  Rename `src/sources/apify_linkedin.py` → `apify.py`, class `ApifyJobSource`. Add `MAPPERS` registry + one `_to_posting_*` per actor output shape (from MP-1 probes). `fetch_jobs` uses `query_param`, selects the mapper, passes `max_total_charge_usd` to `actor.call`. Update `main.py` imports.

- [ ] **MP-4. Weekday rotation in `main.py`**
  Resolve today's weekday → source via `config.schedule`; if unmapped, log + exit. Fetch only that source.

- [ ] **MP-5. Per-platform Sheet tabs + `status` column (`src/sheet.py`)**
  One tab per platform (auto-create from `JOBS_HEADER`); `append_jobs(rows, tab)` targets the platform tab. Add `status` to the header as a user-filled column the app never writes. Scope `get_known_links(tab)` per-tab for same-URL dedup (pending D1).

- [ ] **MP-6. MCP aggregate across tabs (`src/mcp_server.py`)**
  `get_jobs` / `get_stats` read + merge all platform tabs instead of the single `Jobs` tab.

- [ ] **MP-7. Docs**
  Update `config.example.yaml` (schedule + new source fields), `SCRAPER_OPTIONS.md` (new actors + the per-platform `max_results` / cost-cap gotcha), README (rotation + per-tab model).

- [ ] **MP-8. Live validation per platform (paid, authorized per-run)**
  After build, run each platform's source once (real run, explicit go-ahead each) and confirm: correct tab populated, fields mapped, cost within cap, digest shows the right platform.
