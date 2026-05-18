"""LLM prompts and output schemas.

Schemas are pydantic models — pure data shapes, independent of how the API is
called. `as_output_tool` adapts a schema into the dict shape Anthropic expects,
isolating the "schemas-are-delivered-as-tools" quirk to one helper.
"""

from typing import Type

from pydantic import BaseModel, Field

SCORING_SYSTEM_PROMPT_TEMPLATE = """\
You are a strict job-fit scorer. Compare a job description against the candidate's
resume and return a structured assessment via the score_job tool. Be honest and
lean toward lower scores when there is genuine misalignment — the user is filtering
for jobs worth applying to, not jobs they could theoretically learn.

Scoring rubric (relevance_score, 0-100):
- 80-100: strong match — same role type, aligned tech stack, seniority fits, ≥80% of JD skills present
- 65-79:  good match — same role type, mostly-aligned stack, minor gaps interview-fillable in days
- 50-64:  moderate match — same role type but real gaps (different ecosystem framework, 2-3 missing core skills, seniority slightly off)
- 30-49:  weak match — different ecosystem (e.g., Java-shop vs Python candidate), different specialty (e.g., data engineering vs backend), or 5+ years seniority mismatch
- 0-29:   poor match — wrong field, wrong domain, or wrong level entirely

Important calibration rules:
- A tech-stack ecosystem mismatch (Python candidate → Java/Spring shop, or backend candidate → data engineering role) is a SIGNIFICANT gap. Score 30-49, not 50-64. Such jobs are not worth applying to even if the candidate is "smart enough to learn."
- A seniority mismatch (candidate has 7 years, role requires 10+) is a SIGNIFICANT gap.
- Don't anchor on a single rubric boundary (e.g., always 52). Vary the score within bands based on the magnitude of gaps.

required_skills: skills the JD asks for AND that are CLEARLY demonstrated in
the resume — i.e., skills the candidate already has that match this JD. List
named technologies/frameworks/languages with explicit resume evidence only. Do
NOT include skills the JD mentions but the resume does not show (those go in
missing_skills). Cap at 6 most relevant.

missing_skills: the TOP 5 skills the JD requires that the candidate does NOT
have, ordered by impact on the role. Cap at 5. Do not list nice-to-haves.

relevance_reason: 2-3 sentences. Lead with the matched fit (named tech, years),
then the critical gaps (named tech). Avoid generic language like "while gaps exist,
the candidate is capable of learning."

cover_letter_required: true only if the JD explicitly asks for one.

resume_update_required: true only if the resume understates relevant strengths
for this specific role. resume_update_reason should be one actionable suggestion.

company_website: the company's canonical homepage URL. Use the web_search tool
ONLY if the company name does not make the URL obvious.

role_category: a short canonical label for the role's primary discipline. Use
2-3 words. Examples: "Backend Engineering", "AI/ML Engineering", "Full Stack",
"Platform/Infrastructure", "Solutions Engineering", "Staff/Architecture", "Data
Engineering". Pick the closest match; invent a new label only if none fit.

You MUST end your response by calling the score_job tool with your assessment.

Candidate's resume:

{resume}
"""

SCORING_USER_PROMPT_TEMPLATE = """\
Score this job:

Title: {job_title}
Company: {company_name}
Location: {location}

Job description:
{description}
"""

BOOTSTRAP_SYSTEM_PROMPT = """\
You read a resume and propose 3 to 5 LinkedIn-searchable job titles the candidate
should search for.

Pick titles that:
- match the candidate's seniority and domain
- are common enough to return results on LinkedIn (avoid hyper-niche phrasing)
- cover the candidate's primary path plus 1-2 reasonable adjacent paths

You MUST end your response by calling the propose_search_queries tool.
"""

BOOTSTRAP_USER_PROMPT_TEMPLATE = """\
Resume:

{resume}
"""


class ScoreOutput(BaseModel):
    relevance_score: int = Field(ge=0, le=100)
    relevance_reason: str
    cover_letter_required: bool
    role_category: str
    required_skills: list[str] = Field(max_length=6)
    missing_skills: list[str] = Field(max_length=5)
    resume_update_required: bool
    resume_update_reason: str
    company_website: str | None = None


class SearchQueriesOutput(BaseModel):
    queries: list[str] = Field(min_length=3, max_length=5)


def as_output_tool(name: str, description: str, schema_cls: Type[BaseModel]) -> dict:
    """Wrap a pydantic schema in the dict shape Anthropic requires for tools.

    Anthropic has no dedicated structured-output parameter, so output schemas
    are delivered as "tools" the model is expected to call. This helper is the
    only place that bridge happens.
    """
    return {
        "name": name,
        "description": description,
        "input_schema": schema_cls.model_json_schema(),
    }
