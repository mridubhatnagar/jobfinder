# LinkedIn Jobs Scraper — Apify Actor Comparison

Reference for choosing or swapping the Apify actor used by `src/sources/apify_linkedin.py`.

Last surveyed: **2026-05-14**

## Quick comparison

| | **apimaestro** | **delicious_zebu** | **memo23** | **crawlworks** (current) |
|---|---|---|---|---|
| Per-job | $0.005 | ? (undisclosed) | ? (undisclosed) | **$0.0015** (base; $0.001 high-tier) |
| Subscription floor | $0 | $25/mo | $15/mo | $0 |
| Salary in output | ✅ | ✅ | ❌ | ✅ |
| Required skills in output | LLM-derived | LLM-derived | LLM-derived | ✅ source-provided |
| Filtering at source | Light | Rich | Rich | Rich |
| Login required | No | No | No | Not mentioned |
| Monthly active users | 1000s | 2 ⚠️ | 30 | **79** |
| Last updated | Active | 2 months ago | 20 days ago | 24 days ago |
| URL | [apimaestro](https://apify.com/apimaestro/linkedin-jobs-scraper-api) | [delicious_zebu](https://apify.com/delicious_zebu/linkedin-jobs-scraper-no-login-required) | [memo23](https://apify.com/memo23/apify-linkedin-search-results-scraper) | [crawlworks](https://apify.com/crawlworks/linkedin-jobs-scraper) |

## Filtering parameters

| Parameter | apimaestro | delicious_zebu | memo23 | crawlworks |
|---|---|---|---|---|
| keywords | ✅ | ✅ | ✅ | ✅ |
| location | ✅ (single string) | ✅ (single string) | ✅ (string + geoId/placeIds) | ✅ |
| experienceLevel | ✅ string (`mid_senior`) | ✅ string | ✅ numeric (`4`=Mid-Senior) | ✅ |
| employmentType | ❌ (filtered locally) | ✅ | ✅ (`contractType`) | ✅ |
| remote/onsite/hybrid | ✅ | ✅ | ✅ (`jobTypes`) | ✅ (`workType`) |
| date posted | ❌ (filtered locally) | ✅ (24h/week/month) | ✅ (`timeRange`) | ✅ Any/24h/3d/7d/30d + custom (UI: "Time posted range"; JSON key TBD by probe) |
| company filter | ❌ | ✅ | ✅ (`companyNames`) | ❌ |
| max results | maxItems (inert — actor caps ~100) | ✅ | ✅ | ✅ (up to 1000) |

## Monthly cost projection

Assuming daily run × 5 `search_queries` × ~100 jobs/query = ~15K jobs/month.

| Actor | Floor | Usage @ 15K/mo | Total |
|---|---|---|---|
| apimaestro | $0 | $75 | $75 |
| delicious_zebu | $25 | ? | ≥$25 |
| memo23 | $15 | ? | ≥$15 |
| **crawlworks** | $0 | $22.50 (base $1.50/1K) | **$22.50** |

If `experienceLevel: mid_senior` (already added on Drive 2026-05-14) cuts source-side waste ~50%:
- apimaestro: ~$37.50/mo
- crawlworks: ~$11.25/mo

Apify free tier is **$5/month** — none of these fit comfortably at the current 5-query daily cadence. Need to either pay for credits, trim queries to 1-2, or switch to weekly cadence to stay free.

## Detailed notes

### apimaestro/linkedin-jobs-scraper-api

- Trialed during Phase 1 launch (TODO #7), later replaced by crawlworks.
- **`maxItems` was inert** — actor returned ~100 jobs/query regardless of the setting.
- **`usageTotalUsd` settles asynchronously** — `track_apify` computes cost as `items × eventPriceUsd` from `pricingInfo` instead, with `usageTotalUsd` as fallback. (Behavior retained for crawlworks.)
- Light filtering: only `keywords`, `location`, `remote`, `experienceLevel` (string codes).

### delicious_zebu/linkedin-jobs-scraper-no-login-required

- **$25/mo floor doesn't fit the $5 free tier.**
- 2 monthly active users — bus-factor concerning.
- Rich filtering at source but per-job cost undisclosed on listing.

### memo23/apify-linkedin-search-results-scraper

- **$15/mo floor.**
- **No salary field in output** — losing the `salary` column in the Sheet.
- Uses numeric codes for `experienceLevels` (1=Internship, 2=Entry, 3=Associate, 4=Mid-Senior, 5=Executive, 6=Director).
- Healthier adoption than delicious_zebu (30 MAU, updated 20 days ago).

### crawlworks/linkedin-jobs-scraper (current)

- Selected after a live probe confirmed pricing and output shape.
- **3.3× cheaper than apimaestro** at $0.0015/job base ($0.001 on higher subscription tiers).
- No monthly subscription floor (pay-per-event model).
- Rich source-side filtering — replaces most of jobfinder's local filters.
- Output includes salary AND source-provided required skills.
- Output mapping in `src/sources/apify_linkedin.py:_to_posting` is tuned to crawlworks's field names (`jobUrl`, `applyUrl`, `jobDescription`, `companyName`, `employmentType`, `salary`, etc.).
- **Input schema:**
  - `query` (string), `location` (single string), `jobsToFetch` (int — honored, unlike apimaestro's `maxItems`)
  - `timePostedRange` (string enum, seconds): `""` (any), `"86400"` (24h), `"259200"` (3d), `"604800"` (7d), `"2592000"` (30d)
  - Employment type flags: `contract`, `fullTime`, `partTime`, `temporary`, `volunteer`, `internship`
  - Experience level flags: `internshipLevel`, `entryLevel`, `associate`, `midSeniorLevel`, `director`, `executive`
  - Work mode flags: `remote`, `hybrid` (onSite implied when both false)

## Decision factors (for future swaps)

**Avoid memo23 if:** salary data in the Sheet is non-negotiable.
**Avoid delicious_zebu if:** $25/mo subscription floor is a non-starter.

## Sources

- [apimaestro/linkedin-jobs-scraper-api](https://apify.com/apimaestro/linkedin-jobs-scraper-api)
- [delicious_zebu/linkedin-jobs-scraper-no-login-required](https://apify.com/delicious_zebu/linkedin-jobs-scraper-no-login-required)
- [memo23/apify-linkedin-search-results-scraper](https://apify.com/memo23/apify-linkedin-search-results-scraper)
- [crawlworks/linkedin-jobs-scraper](https://apify.com/crawlworks/linkedin-jobs-scraper)
- [Best LinkedIn Scrapers on Apify (2026)](https://use-apify.com/docs/best-apify-actors/best-linkedin-scrapers)
