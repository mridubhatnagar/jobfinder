# Resume update brief

Based on jobfinder run 2026-05-20: 6 AI/ML roles matched (score ≥ 60) at companies including Jade Global, The Hartford India, Xebia, Mihira Visual Labs, CGI, Unisys.

## Decision: 2 projects on resume — Prepit + SystemsFeed

**Hold for later:**
- **Contentflo** — private repo + only 1 user. Swap in when repo goes public OR user count / feedback story grows.
- **Jobfinder** (this repo) — currently in build. **Graduation gates** (all must be true to move from portfolio "currently building" to resume project):
  1. Hosted on Cloud Run (not localhost) — reachable with laptop off
  2. Cross-client verified from ≥2 surfaces (Claude Desktop + claude.ai web minimum)
  3. Auth + rate limiting live (API key header, per-key rate limit)
  4. Used in real personal workflow for 2–4 weeks so it's defensible in interviews

  When graduated, **swap Prepit out, keep SystemsFeed.** Reasoning: Prepit is deprecated (cost takedown); jobfinder will be live + actively used (stronger shipped signal). Losing RAG keyword is real but addressable in skills line. Jobfinder + SystemsFeed = MCP + cost discipline + eval methodology + structured LLM use — more differentiated than RAG-from-deprecated-project.

## Why projects carry 100% of AI signal

Day job (IIT Madras) involves *using* Claude Code as a tool but no AI-specific feature work. So the resume's AI credibility comes entirely from the projects section — there's no "AI work at current role" bullet to back it up. This is why getting the project pair right matters more than usual.

## Per-JD project selection (process, not frozen variants)

Don't maintain a hardcoded variant table — it rots as new projects ship. Instead, encode two stable pieces:

### 1. Project tag registry (extensible)

| Project | Skill tags |
|---|---|
| Prepit | RAG, vector DB, hybrid retrieval, LangGraph |
| SystemsFeed | LLM classification, eval methodology, prompt engineering, structured output |
| Jobfinder *(once graduated)* | MCP server, production LLM pipeline, cost discipline, structured output, tool use |
| *(future projects)* | *(add row here — selection rule below doesn't change)* |

### 2. Selection rule (stable for any pool size)

1. Score each project by tag-overlap with the JD's `required_skills`
2. Pick the highest-scoring project (the **anchor**)
3. Pick a second project that fills the **biggest unmet JD skill gap** from the anchor — diversity constraint, avoid two same-cluster projects when the JD wants breadth

### Operational discipline

- Swap *which 2 projects appear*, not the bullets — bullets stay stable
- Decide at digest-read time per JD; don't pre-generate every combo
- Skills line on resume should reflect the full tag set, regardless of which 2 projects are shown — keyword screens hit even when the project-level evidence isn't shown

### Where this should live long-term

Encode the registry as YAML in jobfinder + the selection rule as `recommend_resume_variant(job_id)` MCP tool (Phase 3 advisor). Then this brief only needs to point at the tool; adding project #4 = one YAML row, no markdown rewrites.

### Why this pair
- Both have public GitHub repos (verifiable by reviewers)
- Both demonstrate **measured engineering decisions** — rare senior signal:
  - Prepit: shipped, then deprecated due to per-query LLM costs
  - SystemsFeed: evaluated tagging strategies on a golden set before picking one
- Covers RAG (Prepit) + prompt engineering / eval (SystemsFeed)
- LangGraph keyword still hits via Prepit

### What each bullet must communicate

**Prepit** — RAG interview prep · Python, FastAPI, LangGraph, Weaviate, Claude API
- RAG architecture (retrieval setup — specifics TBD)
- Model choice and routing
- **Cost-driven deprecation as a deliberate call** — this is the senior signal worth leading with
- Repo: github.com/mridubhatnagar/prepwise

**SystemsFeed** — engineering content tagger · Python, Claude API, embeddings
- Constrained-vocabulary tagging: prevented tag sprawl past ~30 instead of 50+ unique variants
- **Eval-driven prompt selection** — compared tagging strategies against a golden set before shipping
- Live (cron currently paused)
- Repo: github.com/mridubhatnagar/enggfeed

## Other resume edits discussed

### Summary — anchor to actual AI work
Current line claims "spec-driven AI" but the experience section is all pre-AI roles. Replace with something like:
> Python backend engineer (7+ yrs) shipping production AI systems — RAG pipelines, LangGraph agents, MCP servers. Built async services serving 70K+ weekly users at IIT Madras and Peppo.

### AI Engineering skills — densify
Current: *LLM Application Development, Agents, RAG Systems, LangGraph*
Replace with:
> LLM apps (Claude, OpenAI), RAG (Weaviate, hybrid retrieval), LangGraph agents, MCP servers, eval-driven prompt engineering, LLM cost/latency optimization

Covers MCP (Xebia explicitly asked) without spending a project slot. **MCP claim is backed by jobfinder** (in build) — be ready to discuss it in interviews even though it's not a resume project yet.

### Jobfinder placement
Lives under "currently building" on portfolio (mridulabs.dev/projects/), **not** on resume. Keeps resume tight to shipped work; portfolio link in resume header covers anyone who wants to see in-progress.

### Cuts to free ~6 lines
1. **Reckonsys (Aug–Dec 2017)** — drop entirely (sub-6-month role at 7 yrs experience)
2. **KreditBee** — collapse to 1 line
3. **Goibibo** — trim to 2 lines, quantify or remove generic bullets
4. **Independent Consultant** — keep, drop one bullet if tight

### Other
- Add GitHub links inline next to each project name
- Add `MCP` (and `LangSmith` if used) to Tools

## Still needed before bullets can be drafted

**Prepit:**
- Models used (Sonnet, Haiku, OpenAI?)
- Doc/query volume (rough numbers fine)
- Retrieval setup (chunk size, hybrid BM25+vector?, rerank?)
- Rough magnitude on why cost forced takedown
- Any quality measurement done

**SystemsFeed:**
- Tagging strategy landed on (allowlist in prompt? structured output enum? embedding dedup against canonical?)
- Eval setup: golden set size, # of strategies compared, metric
- Posts/day when cron was active

## Out of scope for now
- Contentflo bullets (revisit conditions above)
- Two-variant resume for data-pipeline vs AI-product roles
- Cover letter / outreach templates
