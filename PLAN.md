# Jobfinder — Implementation Plan

## Context

User is actively job-searching and wants a daily-cron system that finds relevant job listings from multiple sources, scores them against their resume, and writes high-relevance matches to a Google Sheet. End-of-run email digest nudges them to open the sheet. System will be paused (by disabling GitHub Actions workflow) once they land a job; reusable for future searches.

Build is **phased**:
- **Phase 1 (this plan):** Python core + cron + Sheets + email. Ship a working daily pipeline. **Includes lightweight skills + role-category capture so Phase 3 analytics have data from day 1.**
- **Phase 2 (deferred):** Build an MCP server with **HTTP transport, hosted on the cloud** (not local stdio), exposing read tools (`get_top_matches`, `get_stats`, etc.) for chat-style interaction. Hosted deployment is required so the server is reachable from any MCP-compatible client — Claude Code on laptop, claude.ai web (desktop or mobile browser), ChatGPT web (desktop or mobile browser, via custom connectors), Cursor, etc. — without depending on the user's laptop being on. Designed *after* Phase 1 usage informs which tools are actually needed.
- **Phase 3 (deferred, depends on Phase 2):** Career advisor — an LLM-mediated advisor backed by the accumulated job dataset, the user's resume, and their stated career goals. **Exposed via the Phase 2 MCP server** so the advisor is usable from any MCP client (Claude Code, Claude Desktop, Cursor, ChatGPT, claude.ai web app). Answers questions like "what should I learn next," "should I lean toward FDE or SE roles," "where are my biggest resume gaps." Aggregation tools exist as internal data primitives + are also exposed individually as MCP tools.
- **Phase 4 (deferred, depends on Phase 2):** Interview prep mode — track scheduled interviews and generate company-specific prep on demand. Two interaction modes off the same data: cron pushes reminders + brief in the daily email when an interview is approaching, and the user can chat (from any MCP client) to ask "list my upcoming interviews" or "tell me about the company whose interview is closest."
- **Phase 5 (presentation-layer upgrade path, only if needed):** If the Sheet becomes a real friction point after Phases 1-4 are in real use, upgrade the data store to **Airtable** (kanban + calendar + gallery views) or **Notion** (rich linking, attachments). Both are commodity tools — no engineering invested in a UI. A *custom web app* is intentionally out of scope unless project scope expands beyond single-user personal use.

This plan covers Phase 1 only.

## Repository visibility: public

This repo is intended to be **public** (portfolio + transparency + free GitHub Actions minutes on public repos). That constraint shapes several design choices:

- **No personal data files in the repo.** Resume, `config.yaml`, `career_goals.yaml` all live in Google Drive, fetched at runtime by the service account. Only source code, `*.example.yaml` templates, and the GH Actions workflow live in the repo.
- **No secrets in the repo.** API tokens, service account JSON, sheet/file IDs, SMTP credentials — all in GitHub Secrets (or Cloud Run env vars for the Phase 2 server).
- **GitHub Actions logs are public** — sanitize logging. No JD text, no resume content, no full scoring rationales printed to stdout. Log counts, statuses, summaries only.
- **Phase 2 MCP server URL becomes public knowledge** once deploy config is in the repo. API key auth on the server is load-bearing, not polite — add rate limiting too.
- **Forks need their own secrets** — README must make setup explicit.
- **Public consequence**: your job-hunting activity becomes visible. If that's a concern (e.g., visible to a current employer), reconsider repo visibility before pushing.

## Guiding architectural principle

**Build only what's uniquely yours. Use the best existing tool for everything else.**

What's uniquely yours (the core, where engineering effort goes):
- Resume-grounded relevance scoring
- Multi-source job aggregation pipeline
- Skills extraction tied to the user's roles and trajectory
- Career advisor logic (resume + goals + accumulated data)
- Interview prep generation
- The MCP server that exposes all of the above

What's commodity (where mature tools already win):
- Tabular data display, kanban, calendar, gallery views (Sheets / Airtable / Notion)
- Chat UX (Claude Code / claude.ai / ChatGPT / Cursor)
- Mobile apps, notifications, auth flows (existing platforms)
- Aggregation/counting over small datasets (Claude does this in-context)

MCP is the architectural commitment that enforces this split: the core lives behind MCP; every commodity interface that supports MCP becomes a viable frontend at zero marginal cost.

Concrete implications:
- No custom web app, no custom dashboard — let the chat advisor or commodity table tools serve those needs.
- No dedicated Python aggregation primitives for the advisor — pass raw rows, let Claude compute over them (works at our scale).
- If presentation becomes a real friction point, upgrade data store to Airtable/Notion (still commodity) rather than build a UI.

## Shape

- Python 3.11+ project
- **Runs in a Docker container locally and in CI** — `docker compose run --rm jobfinder`. Same image is the basis for the Phase 2 Cloud Run deploy, so there is one build path, not two.
- Runs on GitHub Actions cron (daily, with `workflow_dispatch` manual trigger) — workflow builds and runs the container rather than using `actions/setup-python`
- No CLI flags — container entrypoint runs `python main.py`, reading `config.yaml` + env vars
- `DRY_RUN=1` env var (passed via compose) skips sheet write and email
- MCP is *not* in v1 (separately planned for Phase 2)

## File structure

```
jobfinder/
├── main.py                       # Entry point: orchestrates the pipeline
├── config.example.yaml           # Template / documentation only (no real values)
├── README.md                     # Public-facing setup instructions
├── requirements.txt
├── Dockerfile                    # python:3.11-slim base; same image for local, CI, Phase 2 Cloud Run
├── docker-compose.yml            # Local-dev convenience: mounts .env + source tree, sets DRY_RUN
├── .dockerignore                 # Keeps build context small; mirrors .gitignore for secrets/artifacts
├── .env.example                  # Documents required env vars for local compose runs
├── .gitignore                    # Excludes local secrets, real config, runtime artifacts, .env
├── .github/
│   └── workflows/
│       └── daily.yml             # Cron schedule + workflow_dispatch; builds image and runs container
├── src/
│   ├── __init__.py
│   ├── config.py                 # Fetches config.yaml from Drive + validates
│   ├── resume.py                 # Fetches PDF from Drive, extracts text
│   ├── sources/
│   │   ├── __init__.py
│   │   ├── base.py               # JobSource ABC + JobPosting dataclass
│   │   ├── apify_linkedin.py
│   │   └── razorpay.py
│   ├── scoring.py                # Pluggable scorer interface + LLM impl
│   ├── filters.py                # location/age/employment/experience/exclusion filters
│   ├── sheet.py                  # Read existing rows for dedup, append new rows
│   ├── costs.py                  # CostTracker: accumulates Apify + Anthropic spend per run
│   ├── email_digest.py           # SMTP send
│   ├── logging_config.py         # Sanitized logger setup (no JDs, no resume text in stdout)
│   └── bootstrap.py              # First-run: extract search queries from resume
└── data/
    └── (gitignored runtime artifacts if any)
```

**What lives in Google Drive (not in the repo):**
- `resume.pdf` — fetched per run
- `config.yaml` — fetched per run; the actual configuration with locations/queries/thresholds
- `career_goals.yaml` (Phase 3) — career aspirations, dealbreakers, salary expectations

**What lives in the repo:**
- All source code
- `config.example.yaml` — documents the schema; real values stripped
- `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.example`
- README with setup instructions for forkers (includes Docker prereq + `docker compose` commands)

## Docker (local + CI parity)

- **Base image:** `python:3.11-slim`. Single-stage build is fine for v1 (no native compile steps once `selectolax` wheels resolve); switch to multi-stage only if image size becomes a real problem.
- **One image, three callers:** local dev (`docker compose run --rm jobfinder`), GitHub Actions (workflow builds the image then runs it), Phase 2 Cloud Run (same `Dockerfile`, deployed via `gcloud run deploy --source .`).
- **`docker-compose.yml`:** defines a single `jobfinder` service. Mounts `./src`, `./main.py` for fast iteration without rebuilds. Reads env from `.env` (gitignored). Sets `DRY_RUN=1` by default for local runs; override with `DRY_RUN=0 docker compose run --rm jobfinder` for a real run.
- **Secrets in local dev:** `.env` file (gitignored, generated from `.env.example`). Contains `APIFY_TOKEN`, `ANTHROPIC_API_KEY`, `GCP_SERVICE_ACCOUNT_JSON` (single-line), sheet/file IDs, SMTP credentials. **Never check in `.env`.**
- **Secrets in CI:** GitHub Secrets injected as env vars on the `docker compose run` step; no `.env` file in CI.
- **`.dockerignore`:** excludes `.git/`, `__pycache__/`, `data/`, `.env`, `*.pdf`, real `config.yaml` — defense in depth so a stray local file can't ride into a public Cloud Run image in Phase 2.
- **Trade-off acknowledged:** container start adds ~1-2s vs. bare `python main.py`. Acceptable for a daily cron + occasional dry-run workflow; bind mounts keep iteration tight.

## Sheet schema (column order)

The Google Sheet has **two tabs**:
- `Jobs` — one row per matched job (columns below)
- `Costs` — one row per cron run (cost-tracking; schema in the Cost tracking section)

**`Jobs` tab columns:**

```
date_of_fetching | source | role_category | company_name | company_website | job_title | location | posted_date | experience_required | salary | application_link | cover_letter | relevance_score | relevance_reason | required_skills | missing_skills | resume_update_required | resume_update_reason
```

- **date_of_fetching**: ISO date when we found it
- **source**: e.g., `linkedin`, `razorpay`
- **role_category**: which user `search_query` matched this job (e.g., `Forward Deployed Engineer`). Enables per-role analytics in Phase 3.
- **company_website**: actual company URL (backfilled via Anthropic web_search if not provided by source)
- **cover_letter**: bool — whether the JD asks for a cover letter (detected by LLM in scoring call)
- **relevance_score**: 0-100 score based on resume match
- **relevance_reason**: one-line explanation of the score
- **required_skills**: comma-separated list of skills/technologies extracted by LLM from the JD
- **missing_skills**: comma-separated list of skills required by the JD that are **not** present in the user's resume. Powers Phase 3 gap analysis.
- **resume_update_required**: bool — true if the LLM thinks your current resume significantly undersells you for this specific role.
- **resume_update_reason**: brief note on what specifically to change (e.g., "embrace your FinTech experience more," "highlight K8s scaling work").

App only writes/updates these columns. **User-added columns (e.g., `status`, `notes`) are preserved.**

## Cost tracking

Every cron run writes one row to a `Costs` tab in the Google Sheet so spend is visible over time.

**`Costs` tab columns:**

```
run_timestamp | jobs_scored | apify_compute_units | apify_cost_usd
| anthropic_input_tokens | anthropic_output_tokens | anthropic_cache_read_tokens
| anthropic_cache_creation_tokens | anthropic_web_search_requests
| anthropic_cost_usd | total_cost_usd
```

**Implementation:** `src/costs.py` exposes a `CostTracker` class that the pipeline updates as it goes:
- `track_apify(run_metadata)` after each actor run — reads `computeUnits` from Apify response
- `track_anthropic(response)` after each Claude call — reads `response.usage` (input_tokens, output_tokens, cache_read_input_tokens, cache_creation_input_tokens, server_tool_use.web_search_requests)
- `summarize() -> dict` at end of run — converts to USD using hardcoded `PRICING` constants

End of run: append the row to `Costs` and include a one-liner in the email digest ("today's run cost: $0.14"). Aggregation (monthly totals, etc.) is a Sheets SUM formula or, in Phase 3, the advisor can answer on demand.

Pricing constants live in one place (`src/costs.py`) — update them when Anthropic/Apify pricing changes.

**Phase 2 follow-up:** the MCP server has its own costs (Cloud Run vCPU-seconds, per-request Anthropic spend when `ask_career_advisor` runs server-side). Track via server-side logs or extend the `Costs` tab with a `source` column distinguishing `cron` vs. `mcp_server`.

## Config schema (`config.yaml`)

`config.yaml` lives in **Google Drive** (not in the repo). Service account fetches it at runtime. A `config.example.yaml` stripped of real values lives in the repo as documentation for forkers.

```yaml
preferred_locations: ["Bangalore", "Remote", "Hyderabad"]
max_age_days: 7
relevance_threshold: 70
employment_types: ["full-time", "long-term-contract"]
experience_range: [2, 8]              # [min, max] in years
blocked_companies: []                  # company names to skip
excluded_title_keywords: ["intern", "founding engineer"]
max_jobs_per_run: 200                  # safety cap on per-run scoring volume
timezone: "Asia/Kolkata"               # display only; cron schedule is UTC

search_queries:                        # bootstrapped from resume on first run; user-editable
  - "Senior Backend Engineer"
  - "Staff Engineer"
  - "Engineering Manager"

sources:
  - type: apify
    name: linkedin
    actor: bebity/linkedin-jobs-scraper  # confirm during setup
    input:
      maxItems: 100
      # location, query etc. filled in per search_query
  - type: plugin
    name: razorpay
    module: src.sources.razorpay
```

## Scoring (concurrent LLM calls)

- **Model:** Claude Haiku 4.5 (`claude-haiku-4-5-20251001`)
- **Concurrency:** Uses `asyncio` with a `Semaphore(5)` to bound concurrent requests.
- **JD Truncation:** To optimize costs, job descriptions are truncated to the first ~6,000 characters before being sent to the LLM (capturing the core requirements).
- **Context:** Resume text cached in system prompt (5-min TTL; refreshed each batch).
- **Tools:** Web search tool enabled for backfilling company websites.
- **Output (structured JSON):**
  ```json
  {
    "relevance_score": 78,
    "relevance_reason": "Strong backend Python overlap; team builds payment APIs which matches Razorpay experience.",
    "cover_letter_required": false,
    "company_website": "https://example.com",
    "required_skills": ["Python", "Kubernetes", "PostgreSQL"],
    "missing_skills": ["Go", "gRPC"],
    "resume_update_required": true,
    "resume_update_reason": "JD emphasizes gRPC heavily; ensure your API design experience highlights cross-service communication."
  }
  ```
- **Actionability:** `missing_skills` allows for quick gap analysis and interview prep.

## Plugin pattern for sources

`src/sources/base.py`:

```python
@dataclass
class JobPosting:
    source: str
    company_name: str
    company_website: str | None
    job_title: str
    location: str
    posted_date: date | None
    experience_required: str | None
    salary: str | None
    application_link: str
    description: str  # used for scoring; not written to sheet
    employment_type: str | None

class JobSource(ABC):
    @abstractmethod
    def fetch_jobs(self, config: dict) -> Iterable[JobPosting]: ...
```

- `apify_linkedin.py` — generic Apify actor caller, parameterized by actor_id and input schema (so adding other Apify-backed sources later = new config entry only)
- `razorpay.py` — custom scraper. **Needs investigation during build** — careers page may be Lever-backed (clean JSON API), a custom SPA (needs `playwright`), or pure HTML (use `httpx` + `selectolax`)

Adding a new company = drop a new file in `src/sources/` implementing `JobSource`, register in `config.yaml` under `sources:`.

## First-run bootstrap

If `search_queries` in config is empty, on startup:
1. Fetch resume from Drive
2. Send to Claude: "Extract 3-5 job titles this person should search for"
3. Write back to `config.yaml` on Drive
4. Send email: "Bootstrapped search queries. Review `config.yaml` on Drive and re-run."
5. Exit.

User reviews/edits, re-runs.

## Pipeline (in `main.py`)

The pipeline is designed for cost-efficiency and resilience. It uses `asyncio` for concurrent LLM scoring while staying within rate limits.

```
1.  Load env (fail loudly on missing secrets)
2.  Fetch config.yaml from Drive → parse + validate
3.  Fetch resume PDF from Drive → extract text (`pypdf`)
4.  If config.search_queries empty:
        → bootstrap → write back to Drive
        → send email: "Bootstrapped queries. Review config.yaml on Drive and re-run."
        → exit
5.  Read ALL application_links from `Jobs` tab (exhaustive dedup set)
6.  Initialize CostTracker
7.  For each source in config.sources:
        try:
            fetch jobs → apply "Pre-Scoring Filters" (age, location, employment_type,
            experience, blocked_companies, excluded_title_keywords, dedup against Sheet)
            → track_apify(run_metadata)
        except Exception as e:
            log(f"Source {source.name} failed: {e}") # Resilience: one failure doesn't kill the run
8.  Consolidate all jobs → Apply Cross-Query Dedup → Sort by recency → Cap at config.max_jobs_per_run
9.  Score each remaining job concurrently:
        - Use asyncio.Semaphore(5) to respect Anthropic Tier 1 rate limits
        - LLM call with prompt-cached resume
        - track_anthropic(usage)
10. Keep jobs with score >= config.relevance_threshold
11. If not DRY_RUN:
        append rows to `Jobs` tab (only known columns; preserve others)
        append row to `Costs` tab (CostTracker.summarize())
        send email digest with stats + top N matches + cost one-liner
```

## Logging discipline (public repo: GH Actions logs are public)

GitHub Actions logs are public for public repos. Anything written to stdout/stderr by the pipeline is visible to anyone on the internet. **Never log:**

- Raw job descriptions
- Resume text
- Full LLM responses (the `relevance_reason` field, the cover letter detection rationale, etc.)
- Full URLs that could embed personal info
- The user's email, phone, or any PII

**Safe to log:**

- Source name + counts ("linkedin: fetched 87 jobs")
- Number of jobs after each filter
- Per-run cost summary (totals only, not per-call breakdown)

**Implementation Details:**
- `src/logging_config.py` centralizes logger setup.
- Defines a `SafeFormatter` that truncates long strings.
- **Stack-trace scrubbing:** A global exception handler scrubs JD/resume content from `Exception.args` before they are printed to the console.

## Email digest

- SMTP via Gmail app password (simpler than Resend; no API signup)
- Recipient = `RECIPIENT_EMAIL` env var
- Subject: `Jobfinder daily — {N} new matches`
- Body: per-source counts, total fetched, kept after threshold, top 5 with links + scores, link to the sheet, one-line nudge
- One email per cron run, at end of run only

## Secrets (GitHub repo secrets — repo is public, these are non-negotiable)

```
APIFY_TOKEN
ANTHROPIC_API_KEY
GCP_SERVICE_ACCOUNT_JSON       # service account JSON, single line
GOOGLE_SHEET_ID                # destination sheet (Jobs + Costs tabs)
GOOGLE_DRIVE_RESUME_FILE_ID    # resume PDF in Drive
GOOGLE_DRIVE_CONFIG_FILE_ID    # config.yaml in Drive
SMTP_HOST                      # smtp.gmail.com
SMTP_USER                      # account that sends digest
SMTP_PASS                      # Gmail app password
RECIPIENT_EMAIL                # where digest goes
```

Phase 3 adds: `GOOGLE_DRIVE_CAREER_GOALS_FILE_ID`.

## One-time setup steps

0. Install Docker Engine + Docker Compose v2 locally (`docker compose version` should print v2.x).
1. Create a Google Cloud project; enable Sheets API + Drive API
2. Create service account; download JSON key
3. Create Google Sheet with two tabs: `Jobs` and `Costs`. Share with service-account email (Editor). Copy sheet ID.
4. Upload resume PDF to Drive; share with service-account email (Viewer); copy file ID.
5. Create `config.yaml` locally from `config.example.yaml`; fill in real values (locations, queries, threshold, sources, etc.); upload to Drive; share with service-account email (Editor — so first-run bootstrap can write back search_queries); copy file ID.
6. Generate Gmail app password (Google Account → Security → 2FA → App passwords).
7. Create **public** GitHub repo; add all secrets listed above (Settings → Secrets and variables → Actions).
8. Verify `.gitignore` excludes any local copies of `config.yaml`, `career_goals.yaml`, `resume.pdf`, `*.env`, `data/`, `__pycache__/`, etc.
9. Sign up at apify.com; copy API token; add to GitHub Secrets.
10. Push code. First GH Actions run will bootstrap `search_queries` in the Drive-hosted `config.yaml` and exit.
11. Open the Drive `config.yaml`; review/edit bootstrapped `search_queries` and any other field.
12. Manually trigger workflow via `workflow_dispatch` → verify `Jobs` + `Costs` sheets are populated + digest email arrives.
13. **Local dev loop:** copy `.env.example` → `.env`; fill in the same values used in GitHub Secrets; run `docker compose run --rm jobfinder` for a dry-run (defaults to `DRY_RUN=1`). For a real local run: `DRY_RUN=0 docker compose run --rm jobfinder`.

## Verification plan

- **Local dry-run before pushing:** `docker compose run --rm jobfinder` (compose sets `DRY_RUN=1` by default) — should print what *would* be written without touching sheet/email
- **First real run:** trigger manually via `workflow_dispatch`; inspect sheet
- **Threshold tuning (week 1):** lower `relevance_threshold` to 50, observe what's surfaced, adjust until signal is right
- **Add a second Apify source:** drop into `config.yaml` as a new entry; confirm pipeline picks it up without code changes
- **Add a second company careers page:** create `src/sources/<company>.py`; register in config; confirm

## Critical libraries (`requirements.txt`)

```
anthropic>=0.40.0
apify-client>=1.7.0
gspread>=6.0.0
google-auth>=2.30.0
google-api-python-client>=2.140.0   # for Drive
pypdf>=4.0.0
httpx>=0.27.0
pyyaml>=6.0.0
pydantic>=2.7.0                      # config validation
selectolax>=0.3.21                   # html parsing for custom scrapers (if needed)
```

## Open items to validate during build

These can't be decided from a desk; need to be confirmed when building:

1. **Apify LinkedIn actor selection** — resolved: `crawlworks/linkedin-jobs-scraper` ($0.0015/job base tier, no login, `jobsToFetch` honored). Comparison of candidates lives in `SCRAPER_OPTIONS.md`.
2. **Razorpay careers page structure** — check `razorpay.com/jobs/` (and `careers.razorpay.com`) for: Lever/Greenhouse-backed (clean JSON API), Workday (complex), or custom SPA (Playwright). Decision affects whether `playwright` is needed.
3. **`employment_type` from LinkedIn** — confirm Apify actor exposes this; filter logic depends on it
4. **`experience_required` extraction** — Apify often gives only `seniorityLevel` ("Mid-Senior level"); may need a regex pass on JD or extract via LLM in scoring call

## Why MCP (Phase 2 rationale)

Phase 1 ships without MCP because the daily-cron job-finder doesn't need it. MCP gets added in Phase 2 — **hosted on the cloud over HTTP transport**, not running locally as stdio — for these concrete reasons:

1. **Cleaner chat experience in Claude Code.** Helper scripts + Bash work, but Claude has to parse stdout and guess CLI args. MCP gives Claude *typed, schema-validated tools* — less surface for hallucination, no parsing errors. Worth it once chat usage gets frequent.

2. **Cross-client portability.** The same MCP server works in:
   - Claude Desktop (if/when used)
   - Cursor / Windsurf / Zed AI (editors with MCP support)
   - ChatGPT (recently added MCP client support)
   - claude.ai web app (custom integrations)

   Without MCP, each client needs separate integration. With MCP, write once.

3. **Composability with future personal MCP tools.** If later automations (calendar review, expense tracking, etc.) also expose MCP servers, an agent can combine them in a single chat turn — e.g., "summarize today's job matches AND remind me about interview prep meetings." Bash scripts can't be composed like this across processes.

4. **Foundation for a daily-digest agent (alternative to email).** A small Python script can wake at 8pm, call Claude API with MCP tools attached, and let Claude pick the right tools to produce a Slack/Telegram message. More flexible than hardcoded email.

5. **Learning + portfolio artifact.** Real MCP server building experience — tool surface design, schema definition, stdio transport, agent loop. Concrete, demonstrable.

**What MCP does *not* buy us** that's worth being explicit about:
- Nothing for the daily cron run itself (that's pure Python; MCP isn't in the loop).
- Nothing if the user only ever chats via Claude Code with a few helper scripts — that already works.
- It does *not* eliminate hallucination entirely; it constrains it.

Honest take: ~30% nicer day-to-day for chat; ~80% nicer if this becomes the start of a personal MCP toolkit. The bet in Phase 2 is on the latter.

## Deferred to Phase 2 (separate plan when ready)

**Architecture (hosted, not local):**
- MCP server wrapping read operations (`get_top_matches`, `get_stats`, `get_score_reason`, `run_pass`)
- **HTTP / Streamable-HTTP transport** (not stdio) so the server is reachable from any MCP client over the network
- **Hosted on cloud** — recommended: **Cloud Run** (best fit since user already uses Google Cloud for Sheets/Drive service account; scales to zero, generous free tier). Alternatives: Fly.io, Render, Railway, $5/mo VPS.
- **Authentication**: API key in `Authorization` header is **load-bearing** (the public repo makes the server URL public knowledge — auth is the only barrier between strangers and your job data). Generate one key, paste into each client's connector config (Claude Code `.mcp.json`, ChatGPT custom connector, claude.ai integration, etc.). Rotate periodically. OAuth 2.1 deferred until / unless the server is exposed to clients that require it.
- **Rate limiting**: required given the public-repo posture. Per-key request budget (e.g. 100 calls/hour) to bound abuse cost if the key ever leaks. Implement via Cloud Run middleware or simple in-memory token bucket.
- Secrets (`APIFY_TOKEN`, `ANTHROPIC_API_KEY`, `GCP_SERVICE_ACCOUNT_JSON`, MCP API key) injected as Cloud Run env vars or via Secret Manager.
- Same Python code that runs the cron pipeline can back the MCP server — `src/sources/`, `src/sheet.py`, `src/scoring.py`, etc. are reused; only a thin MCP-server wrapper module is new.
- **Same `Dockerfile` from Phase 1** is the Cloud Run image. The MCP server entrypoint (e.g. `python -m src.mcp_server`) is swapped in via Cloud Run's command override, or via a second compose service in local dev. No second image, no parallel build path.

**Client setup once Phase 2 ships:** paste the server URL + API key into each MCP-compatible client. Chat with the job-finder from any of them — laptop or phone — without your laptop being on.

**Dev workflow during Phase 2 build:** run the MCP server locally + expose via **ngrok** (or Cloudflare Tunnel) for iteration. Once the server is stable, deploy to Cloud Run for production and swap the URL in each client's config. Tunneling is dev-only; production must be hosted so the system works when the laptop is off.

**Other Phase 2 items (independent of MCP architecture):**
- Auto-generated cover letter drafts (saved as Drive Doc, linked in sheet)
- Daily digest *push* notification (WhatsApp/Telegram) instead of email
- Company enrichment (recent news, funding) per match
- Application status tracking column (user manually fills; app preserves)
- Multiple resume profiles for different role types

## Deferred to Phase 3 — career advisor

**Framing:** not analytics. This is an LLM-mediated *career advisor* that uses the accumulated job dataset, the user's resume, and their stated career goals as ingredients to give grounded, personalized advice. Aggregation/analytics primitives exist as internal data tools that feed the advisor — they are not the product surface.

**Scope:** advice draws on the user's *own* collected dataset (jobs matching their `search_queries`) as the grounded baseline — typically 2-3 roles (e.g., Forward Deployed Engineer, Solutions Engineer, Backend Engineer). For questions that exceed this dataset, the advisor explicitly falls back to Claude's general knowledge and/or web search and labels its source.

**Three sources the advisor blends:**

| Source | When used | Example claim |
|---|---|---|
| **Your collected data** (grounded) | "What skills do *my* FDE searches actually require?" | "K8s appears in 68% of 47 FDE postings collected over 6 weeks." |
| **Claude general knowledge** (training cutoff Jan 2026) | Roles you haven't searched; broad trends | "Forward Deployed Engineer roles broadly emphasize customer-facing technical work." |
| **Web search** (Anthropic web_search tool) | Recency-sensitive ("last 3 months"); niche queries | "Multiple recent listings in late 2025 emphasize LLM-tooling familiarity." |

Each advisor response should attribute the source of each claim so the user can weigh confidence appropriately.

**Casting a wider net for grounded data:**

The user's grounded dataset can be expanded simply by adding more `search_queries` to `config.yaml`. Adjacent roles you're *curious* about (even ones you wouldn't immediately apply to — e.g., "ML Engineer," "Solutions Architect," "Developer Advocate") collect skill data with minimal extra cost since Apify is already running. After a few weeks the advisor can compare those slices grounded in your own data.

**Why this works without external data services:** Phase 1 already collects skills (`required_skills`) and role tagging (`role_category`) from day 1. By the time Phase 3 is built, the dataset has weeks of accumulated postings to reason over. Claude knowledge + web search fill the rest.

**Conversations the advisor should support:**

- "What skills should I focus on building right now?" — advisor cross-references resume vs. accumulated demand across user's roles, surfaces 2-3 skills ranked by frequency × score-lift potential.
- "Should I lean toward FDE or SE direction?" — advisor compares the two slices: salary, openings volume, skill overlap with current resume, growth trajectory.
- "Where are my biggest resume gaps?" — advisor reads resume + most-common required_skills, names what's missing and how it'd appear in a JD.
- "How is the market for my roles right now?" — advisor gives qualitative summary (e.g., "openings for FDE roles dropped 30% last 2 weeks; SE roles steady; skills shifted toward more emphasis on LLM tooling") plus concrete numbers when asked.
- "Should I apply to this specific job?" — advisor pulls the relevance score + reason, plus career-trajectory context ("this is a stepping-stone vs. lateral vs. stretch role").
- "Build me a 3-month learning plan." — advisor synthesizes: "based on skill gaps and what's trending, focus on X month 1, Y month 2, expect relevance scores to lift from 65 → 78."

**Internal architecture note:**

No dedicated Python aggregation primitives. The advisor fetches raw rows via `get_jobs(filters)` and Claude aggregates in-context (counting skill mentions, computing salary medians, comparing role slices, spotting trends). This works because the dataset is small (~50-500 rows) and answers are qualitative, not regulatory-precise. Aligns with the project's guiding principle: aggregation over small datasets is commodity work Claude does for free; building Python primitives would re-implement what the LLM already does well.

**Additional inputs needed for good advice:**

- **`career_goals.yaml`** — short user-written file: target seniority/title in N years, preferred company type (product / consulting / startup), red lines (e.g., "no on-call," "no relocation"), ambitions ("want to move into ML infra"). The advisor reasons against this. **Lives in Drive, not in the public repo** — fetched at runtime by the same service account that fetches the resume. New secret: `GOOGLE_DRIVE_CAREER_GOALS_FILE_ID`.
- Optionally: application status column (deferred to Phase 2) — advisor can learn from what user applied to vs. rejected.

**Implementation shape: MCP-first (depends on Phase 2).**

Phase 3 *extends* the Phase 2 MCP server with advisor + analytics tools. No separate non-MCP path; if the user wants Phase 3 capability, Phase 2 must ship first. The benefit: the same advisor experience is available in any MCP client — Claude Code in terminal, Claude Desktop, Cursor, ChatGPT (now MCP-client-compatible), claude.ai web app, future MCP-aware tools.

**Tools added to the Phase 2 MCP server (intentionally minimal):**

- `get_jobs(filters)` — return raw rows from the accumulated dataset, filtered by role/timeframe/etc. The advisor (and any client) aggregates over these in-context.
- `get_resume()` — resume text.
- `get_career_goals()` — read `career_goals.yaml`.
- `ask_career_advisor(question)` — high-level synthesis tool. Internally calls the three above, invokes Claude, optionally web-searches, returns advice with source attribution per claim.

No dedicated aggregation primitives (`top_skills`, `salary_distribution`, etc.) — Claude computes over raw rows at our scale (≤500 rows). If Claude's in-context aggregation proves unreliable in practice (it shouldn't at this scale), add Python aggregation tools incrementally — don't build them speculatively.

**How a chat session in ChatGPT would look (illustrative):**

```
User (in ChatGPT): "Using my jobfinder MCP, what should I focus on learning next quarter?"
ChatGPT: [calls ask_career_advisor]
MCP server: reads resume, career_goals, top_skills for user's roles, my_skill_gaps
           → calls Claude internally to synthesize
           → returns: { advice: "...", sources: [...] }
ChatGPT: displays the advice.
```

The MCP server does the actual reasoning (using your `ANTHROPIC_API_KEY` server-side). The client (ChatGPT/Cursor/etc.) just orchestrates and renders. This means advice quality is consistent across clients, and your data stays in one place.

**Honest limitations the advisor should surface in its responses:**

- Grounded claims are limited to the user's `search_queries` slice; broader claims must be labeled as Claude-knowledge or web-search-derived (lower confidence).
- Salary signal is sparse in the dataset (many JDs don't list comp); the advisor should give confidence/sample-size context, not point estimates.
- Grounded trend claims need ~3-4 weeks of accumulated data — early advice should lean on Claude knowledge and stay qualitative.
- Skill extraction is LLM-based and noisy; advisor should not over-index on rare skills (n=1 or n=2 occurrences). Surface skills with mention count, not just rank.
- Web search results are recency-current but the advisor should still cite specific search results when used so the user can verify.
- The advisor is not a substitute for actual mentors / recruiters / people-in-role conversations. Frame advice as one data-grounded perspective.

## Deferred to Phase 4 — interview prep mode

**What it adds:** track scheduled interviews and generate per-interview prep. Supports both push (cron-driven reminders) and pull (chat queries) off the same data.

**Data:** new `Interviews` tab in the Google Sheet (or extend existing rows with status/interview metadata). Columns sketch: `company`, `role`, `application_link`, `interview_date`, `round_type`, `notes`, `prep_status`. User adds rows manually (or via the `add_interview` MCP tool).

**Cron-driven push (reminders):**
- Existing daily cron also scans the `Interviews` tab.
- When an interview is within N days (configurable), the daily email includes:
  - Upcoming interviews block (sorted by proximity)
  - For the closest interview: short company brief + recommended prep focus + any open prep items
- Day-before: a dedicated email with the final brief.

**Chat-driven pull (any MCP client):**
- `list_upcoming_interviews(within_days=30)` — returns scheduled interviews sorted by date.
- `prep_for_interview(interview_id_or_link)` — returns a synthesized brief: what the company does, recent news/launches (via web search), recommended technical and behavioral focus areas, "why this role" narrative grounded in the user's resume + career goals, and 5-10 questions to ask the interviewer.
- `add_interview(company, role, date, round_type, application_link=None)` — append a row.
- `interview_brief(interview_id)` — same as `prep_for_interview` but tighter (final-night-before brief format).

**How the advisor uses available context:**
- The user's resume + `career_goals.yaml` (already in Phase 3 inputs)
- The job row in the main sheet (the original posting they applied to — JD-equivalent for what to emphasize)
- Claude general knowledge (most companies are well-known)
- Web search (recent news, product launches, funding, recent press)

**Honest limitations:**
- Interview tracking requires user discipline to log interviews (until calendar integration is added — see below).
- Company brief quality varies — well-known companies get richer briefs; small startups may have thin web presence.
- Prep advice is generic-ish unless the user can share the specific interview format (which the system doesn't know about by default).

**Optional Phase 4.1 — Google Calendar integration:**
- Same service-account approach as Sheets/Drive; enable Calendar API.
- Auto-detect events whose titles match interview patterns (configurable keywords: "interview," "screening," "onsite," company name match against the Sheet).
- Auto-create rows in the `Interviews` tab from detected events.
- Removes the manual-logging requirement; otherwise additive.

## Deferred to Phase 5 — presentation-layer upgrade (revisit only if friction emerges)

**Not committed.** Sheets is the v1 storage + UI. Phase 5 is only triggered if the Sheet becomes a real friction point in lived use after Phases 1-4 ship.

**If triggered, the upgrade path is to a commodity tool, not a custom web app:**

| Candidate | When to pick |
|---|---|
| **Airtable** | Want kanban for application status, calendar for interviews, gallery for browsing. API is solid; cron writes stay reliable. Free tier (1k records) covers a job hunt. |
| **Notion** | Want rich linking (interview ↔ company ↔ application), attachments, notes alongside data. API slower / rate-limited — batch writes carefully. |

**What stays the same regardless of which is picked:**
- Cron pipeline (sources, scoring, filters) — unchanged
- MCP server architecture — unchanged
- Email digest, chat surfaces — unchanged
- Only `src/sheet.py` swaps for `src/airtable.py` or `src/notion.py`. ~half-day rewire.

**Why a custom web app is intentionally not the Phase 5 default:**
Building a custom UI is *anti-philosophy* for this project — re-implementing what mature commodity tools already ship. Custom web app stays in scope only if the project expands beyond single-user personal use (sharing, commercializing). For the stated use case, that scenario is unlikely.

**Likely signals that even Phase 5 isn't needed:**
- Daily run yields manageable rows; sorting/filtering in Sheets covers it.
- Chat via existing MCP clients handles ad-hoc questions well.
- Email digest + advisor handles the proactive surface.

The system is considered *complete* at Phase 4. Phase 5 is a contingency, not a roadmap commitment.

## Deferred indefinitely (intentionally out of scope)

- **Custom web app** — violates the guiding principle (rebuilds commodity UI); only revisit if scope expands beyond single-user personal use.
- **Analytics dashboard / charts / visualization layer** — dashboards reward looking, not acting; chat advisor is more actionable. If charts are ever wanted, Sheets/Airtable/Notion native chart features cover it.
- **Dedicated Python aggregation primitives** for the advisor — at our data scale Claude aggregates in-context reliably; building Python primitives is speculative engineering.
- Recruiter / hiring-manager extraction
- LLM-tweaked resume per job
- Salary normalization across currencies
- Reposted-job dedup (same job, different URL)
