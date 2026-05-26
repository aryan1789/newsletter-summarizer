# CLAUDE.md — Newsletter Summarizer

## What this project does
A Google ADK agent that reads Gmail every day, filters newsletters down to only software/AI-relevant facts, and posts a short digest to Discord. Runs automatically via GitHub Actions.

## Stack
- **Agent framework**: Google ADK (`google-adk`)
- **Model**: `gemini-2.5-flash` (via `GOOGLE_API_KEY`)
- **Email**: Gmail IMAP with an app password
- **Output**: Discord webhook
- **Scheduler**: GitHub Actions cron (`0 20 * * *` = 8am NZST daily)

## File structure
```
agent.py          — ADK Agent definition + 3 tools (get_topics, fetch_newsletters, post_to_discord)
main.py           — async entry point, runs the agent
topics.txt        — INCLUDE/EXCLUDE filter rules (edit this to change what gets surfaced)
requirements.txt  — google-adk, html2text, requests
.env              — local credentials (gitignored, never committed)
.env.example      — credential template
.github/workflows/daily.yml — GitHub Actions cron job
```

## How the agent works
1. `get_topics()` — reads `topics.txt` for the filter rules
2. `fetch_newsletters(days=1)` — logs into Gmail via IMAP, pulls last 24h of inbox, filters to emails with newsletter headers (`List-Unsubscribe`, `List-Id`, `Precedence: bulk/list`), strips to plain text
3. Gemini applies the topic filter and writes one bullet per relevant item
4. `post_to_discord(message)` — posts to Discord webhook, splits into multiple messages if over 2000 chars

## Topic filter (topics.txt)
INCLUDE: major LLM releases, Claude/Anthropic news, ChatGPT/OpenAI news, new AI dev tools/APIs/frameworks, significant AI research relevant to software, new AI coding tools.
EXCLUDE: AI in non-software fields, minor patches, opinions/analysis, hype, math/academic problem-solving.

## Credentials (all stored as GitHub Secrets + local .env)
| Secret | What it is |
|--------|-----------|
| `GMAIL_EMAIL` | aryanshahnz@gmail.com |
| `GMAIL_APP_PASSWORD` | Gmail app password (not the account password) |
| `DISCORD_WEBHOOK_URL` | Discord channel webhook URL |
| `GOOGLE_API_KEY` | Google AI Studio API key (billing enabled on "Newsletter Summarizer" GCP project) |

## Key decisions & history
- Started as Anthropic SDK script → rebuilt as Google ADK agent so Gemini orchestrates tool calls natively
- `gemini-2.0-flash` retired for new users → switched to `gemini-2.5-flash`
- Billing had to be enabled on the GCP project — free tier quota was 0 for NZ accounts
- Newsletter detection uses email headers only (no content scanning of personal emails)
- Agent instruction explicitly forbids inferring company affiliations not stated in the source newsletter

## To change the filter topics
Edit `topics.txt`, commit, and push — no code changes needed.

## To test manually
GitHub → Actions → Daily Newsletter Digest → Run workflow

## To run locally
```
pip install -r requirements.txt
# fill in .env with credentials
python main.py
```

## GitHub repo
https://github.com/aryan1789/newsletter-summarizer
