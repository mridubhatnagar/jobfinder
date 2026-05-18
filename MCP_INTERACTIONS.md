# Jobfinder — MCP Interaction Guide

Once the Phase 2 MCP server is deployed (Cloud Run + HTTP transport), you can interact with your job market intelligence using natural language from any MCP-compatible client (Claude Code, Cursor, ChatGPT Web/Mobile, etc.).

---

## 1. Daily Intelligence (The "Pull" Mode)

These queries help you quickly digest the latest findings without opening the Google Sheet.

- *"What are my top 3 matches from today's run? Give me the TL;DR on why they are good."*
- *"Are there any remote jobs that pay over [X] that I haven't seen yet?"*
- *"Show me all the jobs at [Company Name] that we've found in the last week."*
- *"Summarize the activity from the last 3 days. How many high-score jobs did we find?"*

## 2. Action Coordination (The "Application" Mode)

Use these when you are ready to move from "browsing" to "applying."

- *"I'm about to apply to the [Role] at [Company]. Based on my resume, what's the #1 thing I should emphasize in my intro note?"*
- *"Generate a draft email to a recruiter for the [Job Link] role, highlighting my experience with [Specific Skill]."*
- *"Which of the 'high-relevance' jobs on my list haven't I applied to yet? Remind me why I was hesitant about them."*
- *"Based on the 'Missing Skills' for the [Company] role, what should I quickly research before I hit submit?"*

## 3. Career Strategy & Market Analysis (Phase 3)

These queries leverage the accumulated data to give you high-level market insights.

- *"Based on the last 100 jobs you've scored, what is the 'market-clearing' salary for a Senior Backend role in Bangalore?"*
- *"I'm seeing a lot of 'Missing Skills' related to [Technology]. Can you find me 3 jobs where that was required so I can understand the context better?"*
- *"If I spend the next month learning [New Skill], how many of my current 'Low Score' jobs would become 'High Score' matches?"*
- *"Compare the 'Forward Deployed' vs 'Backend' roles we've found. Which category has higher average relevance scores for my current resume?"*

## 4. Interview Prep (Phase 4)

Ground your interview preparation in the specific data the system has collected.

- *"I have an interview with [Company] tomorrow. Pull their JD from the sheet and tell me what technical 'red flags' they might be looking for based on my resume gaps."*
- *"What are the 5 most common questions asked at [Company] based on recent web searches? Let's roleplay the 'Why our company?' question."*
- *"Review the 'Resume Update Reason' for the [Company] role and help me prepare a 2-minute 'Tell me about yourself' pitch that addresses those points."*

---

## Mobile Usage (ChatGPT App / Mobile Browser)

Because the MCP server is hosted on **Cloud Run**, you can ask these questions directly from your phone.

- **Scenario:** You're at a coffee shop and get a notification.
- **You (in ChatGPT Mobile):** *"Check my jobfinder for any new high-score matches today."*
- **ChatGPT:** [Calls MCP Server] *"Found one 92/100 match at Razorpay for a Staff Engineer. It emphasizes K8s and payment systems."*
- **You:** *"Draft a short LinkedIn message to the hiring manager emphasizing my FinTech background."*
- **Result:** You copy-paste the draft into LinkedIn Mobile and apply in 60 seconds.
