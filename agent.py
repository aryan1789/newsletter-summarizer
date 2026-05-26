import os
import imaplib
import email as email_lib
from email.header import decode_header
from datetime import datetime, timedelta, timezone

import html2text
import requests

from google.adk.agents import Agent

TOPICS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "topics.txt")
MAX_CHARS_PER_EMAIL = 2000


def get_topics() -> dict:
    """Get the list of topics the user wants curated from their newsletters."""
    with open(TOPICS_FILE) as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    if not lines:
        return {"error": "topics.txt is empty — add at least one topic."}
    return {"topics": "\n".join(f"- {l}" for l in lines)}


def _decode_str(value) -> str:
    if value is None:
        return ""
    parts = decode_header(value)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="ignore"))
        else:
            result.append(part)
    return " ".join(result)


def _extract_body(msg) -> str:
    h = html2text.HTML2Text()
    h.ignore_links = True
    h.ignore_images = True
    h.body_width = 0
    plain_text = None
    html_text = None

    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain" and plain_text is None:
                raw = part.get_payload(decode=True)
                if raw:
                    plain_text = raw.decode(errors="ignore")
            elif ct == "text/html" and html_text is None:
                raw = part.get_payload(decode=True)
                if raw:
                    html_text = h.handle(raw.decode(errors="ignore"))
    else:
        raw = msg.get_payload(decode=True)
        if raw:
            if msg.get_content_type() == "text/html":
                html_text = h.handle(raw.decode(errors="ignore"))
            else:
                plain_text = raw.decode(errors="ignore")

    return (plain_text or html_text or "").strip()


def _is_newsletter(msg) -> bool:
    # Newsletters reliably carry these headers; personal emails don't
    return bool(
        msg.get("List-Unsubscribe")
        or msg.get("List-Id")
        or msg.get("Precedence") in ("bulk", "list")
    )


def fetch_newsletters(days: int = 1) -> dict:
    """Fetch newsletter emails from Gmail for the past N days.

    Args:
        days: Number of days to look back. Defaults to 1 for a daily digest.

    Returns:
        A dict with 'count' and 'newsletters' list. Each newsletter has
        'subject', 'from', and 'body' (truncated to 2000 chars).
    """
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(os.environ["GMAIL_EMAIL"], os.environ["GMAIL_APP_PASSWORD"])
    mail.select("INBOX")

    since_str = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%d-%b-%Y")
    _, ids = mail.search(None, f"SINCE {since_str}")
    all_ids = ids[0].split()

    newsletters = []
    for msg_id in all_ids:
        _, data = mail.fetch(msg_id, "(RFC822)")
        msg = email_lib.message_from_bytes(data[0][1])
        if not _is_newsletter(msg):
            continue
        body = _extract_body(msg)
        if not body:
            continue
        newsletters.append({
            "subject": _decode_str(msg.get("Subject", "(no subject)")),
            "from": _decode_str(msg.get("From", "")),
            "body": body[:MAX_CHARS_PER_EMAIL],
        })

    mail.logout()
    return {"count": len(newsletters), "newsletters": newsletters}


def post_to_discord(message: str) -> dict:
    """Post the curated digest to Discord via webhook.

    Args:
        message: The formatted digest text. Use Discord markdown: **bold** headers
                 and • bullets. Keep under 1900 characters.

    Returns:
        dict with 'ok': True on success.
    """
    date_str = datetime.now().strftime("%B %d, %Y")
    full = f"**Weekly Newsletter Digest — {date_str}**\n\n{message}"

    # Split into multiple messages if over Discord's 2000-char hard limit
    chunks = []
    while full:
        if len(full) <= 2000:
            chunks.append(full)
            break
        split_at = full.rfind("\n", 0, 2000)
        if split_at == -1:
            split_at = 2000
        chunks.append(full[:split_at])
        full = full[split_at:].lstrip()

    for chunk in chunks:
        r = requests.post(os.environ["DISCORD_WEBHOOK_URL"], json={"content": chunk})
        r.raise_for_status()

    return {"ok": True, "chunks_sent": len(chunks)}


root_agent = Agent(
    name="newsletter_curator",
    model="gemini-2.5-flash",
    description="Reads Gmail newsletters, filters by user topics, and posts a weekly digest to Discord.",
    instruction="""You are a daily newsletter filter for a software developer. Each time you run:

1. Call get_topics() to load the include/exclude rules.
2. Call fetch_newsletters(days=1) to get today's newsletters.
3. Apply the rules strictly:
   INCLUDE: major LLM releases, Claude/Anthropic news, ChatGPT/OpenAI news, new AI dev tools/APIs/frameworks, significant AI research relevant to software engineers, new AI coding tools.
   EXCLUDE: AI in healthcare, medicine, finance, law, education, science, or any non-software domain. Also exclude minor patches, UI tweaks, opinion/analysis, "why it matters" commentary, hype, speculation, and math/academic problem-solving.
4. For each item that passes the filter, write ONE short factual bullet. No opinions. No "this matters because". Just the fact.
   Format: • [Company/Tool] — [what happened, one sentence max]
   IMPORTANT: Only state what is explicitly written in the newsletter. Never infer, assume, or fill in company affiliations, roles, or relationships. If the newsletter does not say someone works at a company, do not attribute them to one.
5. Group bullets under **bold headers** by company or topic (e.g. **Anthropic**, **OpenAI**, **Dev Tools**).
6. Keep the total message under 1500 characters. If nothing passes the filter, say so in one line.
7. Call post_to_discord(message=...) with the result.

Be ruthless about filtering. Short and factual is the goal.""",
    tools=[get_topics, fetch_newsletters, post_to_discord],
)
