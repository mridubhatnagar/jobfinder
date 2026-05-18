# Jobfinder — Potential Extensions

These are high-value directions the system can be extended in once the core Phase 1–4 pipeline is stable. These ideas focus on turning the "Job Search Engine" into a "Full-Lifecycle Career Engine."

---

## 1. The "Network Bridge" (Referral Hunter)

- **The Idea:** Automatically identify potential referrers for high-scoring jobs.
- **Mechanism:** When a job score exceeds a high threshold (e.g., 85+), trigger a secondary scan of your LinkedIn 1st/2nd-degree connections (via Apify or manual CSV export) to find people currently working at that company.
- **Value:** Shifts the strategy from "Cold Applying" to "Warm Referrals."
- **Output:** A new column in the Sheet: `Suggested Referrer: [Name] ([Relationship])`.

## 2. The "Resume Architect" (Tailored Content)

- **The Idea:** Provide surgical, job-specific resume improvements.
- **Mechanism:** Analyze the gap between your resume and the JD. Instead of just identifying "Missing Skills," generate 2-3 specific bullet point rewrites for your existing experience that highlight the technologies or responsibilities emphasized by the employer.
- **Value:** Increases the probability of passing automated Applicant Tracking Systems (ATS).
- **Output:** A `Tailoring Notes` or `Bullet Point Deltas` field in the Sheet.

## 3. The "Ghostwriting Assistant" (Inbound Optimization)

- **The Idea:** Use market data to optimize your "passive" job hunt (LinkedIn Profile).
- **Mechanism:** Aggregate the `required_skills` column across all fetched jobs over a 30-day period. Identify high-frequency keywords that are missing from your LinkedIn 'About' or 'Skills' sections.
- **Value:** Boosts your visibility in recruiter searches (Inbound), reducing the need for active hunting (Outbound).
- **Output:** A monthly "Profile Health" nudge in the email digest with 3-5 keywords to add to your profile.

## 4. The "Market Comp" (Salary Negotiator)

- **The Idea:** Build a private, grounded database of actual salary ranges for your specific niche.
- **Mechanism:** Extract and normalize salary data whenever it appears in a JD. Over time, calculate medians and percentiles for specific `role_categories` and seniority levels.
- **Value:** Provides hard data for salary negotiations. You can cite "market medians for [Role] in [Location] based on N active listings."
- **Output:** A separate `Market Intelligence` tab or dashboard showing salary trends.

## 5. The "Application Velocity" Tracker

- **The Idea:** Quantify the "health" of your job hunt.
- **Mechanism:** Track the time between `date_of_fetching` and when you mark a job as `Applied`. Calculate conversion rates (Applied -> Interview -> Offer).
- **Value:** Identifies bottlenecks. If you have a 90% score but 0% interview rate, the problem is your resume. If you have a high interview rate but 0% offers, the problem is interview prep.
- **Output:** Monthly "Funnel Health" report.
