# Jobfinder — Phase 1 TODO

Derived from `PLAN.md`. 24 tasks, grouped by stage.

**Legend:** `[x]` done · `[ ]` pending · `(DEFERRED)` punted past Phase 1 launch · `(BLOCKED)` waiting on external dependency

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
  Chosen: `apimaestro/linkedin-jobs-scraper-api` ($0.005/job, no login). Probed real output — confirmed `description`, `salary`, `apply_url` are returned (despite gaps in the actor's documented schema). Updated `config.example.yaml` accordingly.

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

- [ ] **18. Write `.github/workflows/daily.yml`**
  Daily cron schedule (UTC) + `workflow_dispatch` for manual triggers. Workflow builds the Docker image then runs the container with `docker compose run --rm jobfinder` (or `docker run`), injecting all GitHub Secrets as env vars. Public-repo logs are sanitized by `SafeFormatter`; workflow should not echo secrets or run any extra debug commands.

## External setup

- [x] **19. One-time Google Cloud + Drive + Sheets setup**
  GCP project created; Sheets + Drive APIs enabled; service account + JSON key generated; Sheet with `Jobs` + `Costs` tabs shared with SA as Editor; `resume.pdf` uploaded + shared as Viewer; `config.yaml` uploaded + shared as Editor; all three IDs in `.env.local`.

- [x] **20. Generate Gmail app password + sign up for Apify**
  Gmail 2FA + app password generated. Apify account active with $5/month free tier.

- [ ] **21. Create public GitHub repo + add all secrets**
  Create the public repo. Add secrets: `APIFY_TOKEN`, `ANTHROPIC_API_KEY`, `GCP_SERVICE_ACCOUNT_JSON` (single line), `GOOGLE_SHEET_ID`, `GOOGLE_DRIVE_RESUME_FILE_ID`, `GOOGLE_DRIVE_CONFIG_FILE_ID`, `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS`, `RECIPIENT_EMAIL`. `.gitignore` already excludes local copies.

## Verification

- [x] **22. Local dry-run via Docker Compose**
  Full live run completed (`DRY_RUN=0 docker compose run --rm jobfinder python main.py`). Funnel: 401 fetched → 227 after age → 20 after location → 17 after employment type → 17 scored → 2 kept (threshold 70) → 2 rows appended to Jobs, 1 cost row to Costs, 1 digest email sent. Apify cost tracking corrected mid-run: was returning $0 because `usageTotalUsd` settles async; now derived from `items × pricingPerEvent.eventPriceUsd` and matches exactly ($2.005 for 401 items). Total run cost ~$2.34. `maxItems` discovered to be inert on this actor (always returns ~100/query).

- [ ] **23. First GH Actions run: bootstrap + manual verify**
  Push code. First run bootstraps `search_queries` into Drive `config.yaml` and exits with email. Review/edit bootstrapped queries on Drive. Manually trigger `workflow_dispatch` for the real first run. Verify: `Jobs` tab populated, `Costs` tab row appended, digest email received, GH Actions logs contain no PII or JD text.

- [ ] **24. Threshold tuning + add-a-source smoke tests**
  Week 1: lower `relevance_threshold` to ~50, observe surfaced jobs, adjust to the right signal level. Smoke test plugin pattern: add a second Apify entry in `config.yaml` (no code change) and confirm pipeline picks it up; add a stub `src/sources/<company>.py` + register in config and confirm. Validates the "adding a source = config edit only" promise.
