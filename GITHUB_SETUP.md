# GitHub Setup

1. Push the repository to GitHub.
2. Enable Actions with read/write repository contents permission if your organization requires it.
3. Optional secret: `SEC_USER_AGENT` containing only a literal SEC-compatible user-agent string.
4. Optional secret: `OPENAI_API_KEY`.
5. Optional repository variable: `OPENAI_MODEL`.
6. Run `Equity Research Engine` manually once before relying on the weekday schedule.

The workflow commits `published/` so the decision and point-in-time estimate ledgers remain durable.
