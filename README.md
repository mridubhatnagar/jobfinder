# Jobfinder

Daily-cron job aggregator that scores postings against your resume and writes high-relevance matches to a Google Sheet. End-of-run email digest links you to the sheet. Pause anytime by disabling the GitHub Actions workflow.

See [`PLAN.md`](./PLAN.md) for the full design rationale, phased roadmap, and architectural decisions.

## How it works

1. GitHub Actions cron triggers daily (also runnable on-demand via `workflow_dispatch`).
2. Workflow builds the Docker image and runs `python main.py`.
3. The container:
   - Fetches `config.yaml` and `resume.pdf` from Google Drive (service account auth).
   - Pulls job postings from each configured source (Apify LinkedIn actor, company careers pages).
   - Filters by location, age, employment type, experience, blocklists.
   - Scores each surviving JD against the resume using Claude Haiku (concurrent, cached resume in system prompt).
   - Appends matches above threshold to the `Jobs` tab of a Google Sheet.
   - Appends a per-run cost row to the `Costs` tab.
   - Sends an email digest with the top matches and a sheet link.

## Public-repo notice

This repo is **public**: portfolio + transparency + free Actions minutes. Consequences:

- All personal data (resume, real `config.yaml`, `career_goals.yaml`) lives in **Google Drive**, not the repo.
- All secrets live in **GitHub Secrets** (or local `.env`, gitignored).
- **GitHub Actions logs are public.** The pipeline sanitizes logs (counts and status only - no JD text, no resume text, no full LLM responses).
- If your job search is sensitive (e.g. visible to a current employer), reconsider repo visibility before forking.

Forkers must provision their own secrets and Drive files - none of mine are reachable.

## Prerequisites

- Docker Engine + Docker Compose v2 (`docker compose version` should print `Docker Compose version v2.x`).
- A Google account (free) for Drive + Sheets.
- An Anthropic API key.
- An Apify account (free tier covers low-volume LinkedIn scraping).
- A Gmail account with 2FA enabled (for SMTP app password).

## One-time setup

### 1. Google Cloud + Drive + Sheets

1. Create a GCP project at https://console.cloud.google.com.
2. Enable **Google Sheets API** and **Google Drive API** (APIs & Services → Library).
3. Create a service account (IAM → Service Accounts → Create). No project-level role needed.
4. Generate a JSON key (Keys tab → Add Key → Create new key → JSON). Save it outside the repo.
5. Note the service account email - `*@*.iam.gserviceaccount.com`. You'll share each resource below with this email.
6. Create a Google Sheet with two tabs named exactly `Jobs` and `Costs`. Share with the service account email as **Editor**. Copy the sheet ID from the URL.
7. Upload your `resume.pdf` to Drive. Share with the service account as **Viewer**. Copy the file ID.
8. Copy [`config.example.yaml`](./config.example.yaml) → `config.yaml`, fill in real values (locations, threshold, etc.), upload to Drive. Share with the service account as **Editor** (so first-run bootstrap can write back `search_queries`). Copy the file ID.

### 2. Gmail app password

1. Google Account → Security → 2-Step Verification → App passwords.
2. Generate one for "Mail". This is your `SMTP_PASS`.

### 3. Apify

1. Sign up at https://apify.com.
2. Account → Integrations → API token. This is your `APIFY_TOKEN`.

### 4. Secrets

Set these in a local `.env` (from [`.env.example`](./.env.example)):

| Secret | Source |
|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com |
| `APIFY_TOKEN` | Apify account |
| `GCP_SERVICE_ACCOUNT_JSON` | The full JSON key, single-lined via `jq -c . your-key.json` |
| `GOOGLE_SHEET_ID` | From the Sheet URL |
| `GOOGLE_DRIVE_RESUME_FILE_ID` | From the Drive file URL |
| `GOOGLE_DRIVE_CONFIG_FILE_ID` | From the Drive file URL |
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_USER` | sender Gmail address |
| `SMTP_PASS` | Gmail app password |
| `RECIPIENT_EMAIL` | where the digest goes |

### 5. First run

1. Push to the public repo.
2. The first GH Actions run finds `search_queries: []` in your Drive `config.yaml`, bootstraps 3–5 job titles from your resume via Claude, writes them back to Drive, and exits with an email saying "Bootstrapped queries. Review and re-run."
3. Open the Drive `config.yaml`. Tweak the bootstrapped queries.
4. Trigger the workflow manually (`workflow_dispatch`). Verify the `Jobs` + `Costs` tabs populate and the digest email arrives.

## Local development

The same image runs locally and in CI.

```bash
# 1. Local secrets (gitignored + dockerignored)
cp .env.example .env
# Fill in the same values you used in GitHub Secrets.

# 2. Dry run - prints what would be written without touching Sheet/email
docker compose run --rm jobfinder

# 3. Real local run - writes to your Sheet, sends a real email
DRY_RUN=0 docker compose run --rm jobfinder
```

`./src/` and `./main.py` are bind-mounted into the container, so code edits don't need a rebuild. Only `requirements.txt` or `Dockerfile` changes require `docker compose build`.

## Pausing the cron

When you land a job (or just need a break): GitHub repo → Actions → "Jobfinder daily" → ⋯ → **Disable workflow**. Re-enable any time.

## Adding a source

| Type | How |
|---|---|
| Another Apify actor | Add a new entry under `sources:` in `config.yaml`. No code change. |
| A specific company careers page | Create `src/sources/<company>.py` implementing the `JobSource` ABC. Register under `sources:` with `type: plugin`. |

See [`src/sources/base.py`](./src/sources/base.py) for the `JobPosting` dataclass + `JobSource` ABC.

## License

Personal project, no license declared. Forks welcome but unsupported.
