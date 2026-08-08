"""Send notifications via Telegram and a GitHub issue (for email, via
GitHub's own notification emails - no SMTP credentials needed)."""
from __future__ import annotations

import html
import os

import requests


def _escape_html(text: str) -> str:
    return html.escape(text, quote=False)


def send_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram credentials missing, skipping Telegram notification")
        return
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=15,
    )
    if not resp.ok:
        print(f"Telegram notification failed: {resp.status_code} {resp.text}")


def create_github_issue(title: str, body: str) -> None:
    """Open a GitHub issue mentioning the repo owner.

    GitHub emails the mentioned user automatically using its own
    (already-authenticated) mail sender - no SMTP password or API key
    needed on our side.
    """
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        print("GITHUB_TOKEN/GITHUB_REPOSITORY missing, skipping issue notification")
        return

    resp = requests.post(
        f"https://api.github.com/repos/{repo}/issues",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        json={"title": title, "body": body, "labels": ["new-listing"]},
        timeout=15,
    )
    if not resp.ok:
        print(f"GitHub issue notification failed: {resp.status_code} {resp.text}")


def build_telegram_message(post: dict) -> str:
    """Telegram HTML formatting: <b>bold</b> labels. Dynamic values are
    HTML-escaped since parse_mode=HTML treats &/</> as markup."""
    title = _escape_html(post.get("title") or "(без заголовка)")
    price = _escape_html(post.get("price") or "не указана")
    seller = _escape_html(post.get("seller") or "не указан")
    url = post.get("url", "")
    filter_names = _escape_html(", ".join(post.get("matched_filters", [])))

    blocks = ["<b>Новое объявление</b>"]
    if filter_names:
        blocks.append(f"<b>Фильтр:</b> {filter_names}")
    blocks += [
        f"<b>Название:</b> {title}",
        f"<b>Цена:</b> {price}\n<b>Продавец:</b> {seller}",
        f"<b>Ссылка:</b> {url}",
    ]
    return "\n\n".join(blocks)


def build_issue_body(post: dict) -> str:
    """GitHub Markdown formatting: **bold** labels."""
    title = post.get("title") or "(без заголовка)"
    price = post.get("price") or "не указана"
    seller = post.get("seller") or "не указан"
    url = post.get("url", "")
    filter_names = ", ".join(post.get("matched_filters", []))

    blocks = ["**Новое объявление**"]
    if filter_names:
        blocks.append(f"**Фильтр:** {filter_names}")
    blocks += [
        f"**Название:** {title}",
        f"**Цена:** {price}\n**Продавец:** {seller}",
        f"**Ссылка:** {url}",
    ]
    return "\n\n".join(blocks)


def notify_new_post(post: dict) -> None:
    title = post.get("title") or "(без заголовка)"
    notify_user = os.environ.get("GITHUB_NOTIFY_USER", "")
    filter_prefix = ""
    if post.get("matched_filters"):
        filter_prefix = f"[{', '.join(post['matched_filters'])}] "

    send_telegram(build_telegram_message(post))

    issue_body = build_issue_body(post)
    if notify_user:
        issue_body += f"\n\n@{notify_user}"
    create_github_issue(f"{filter_prefix}Новое объявление: {title}", issue_body)


def _chunk_lines(lines: list[str], max_len: int = 3500) -> list[str]:
    """Group lines into chunks under max_len chars, to stay under Telegram's
    ~4096 char message limit for long digests."""
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in lines:
        line_len = len(line) + 1
        if current and current_len + line_len > max_len:
            chunks.append("\n".join(current))
            current, current_len = [], 0
        current.append(line)
        current_len += line_len
    if current:
        chunks.append("\n".join(current))
    return chunks


def notify_digest(title: str, posts: list[dict]) -> None:
    """Send a single numbered list of post links, instead of one
    notification per post - used for manual bulk/test scans."""
    header_plain = f"{title} — найдено: {len(posts)}"

    telegram_items = [
        f'{i}. <a href="{p["url"]}">{_escape_html(p.get("title") or p["url"])}</a>'
        for i, p in enumerate(posts, 1)
    ]
    telegram_chunks = _chunk_lines(telegram_items) or ["(ничего не найдено)"]
    header_html = f"<b>{_escape_html(header_plain)}</b>"
    total = len(telegram_chunks)
    for idx, chunk in enumerate(telegram_chunks, 1):
        prefix = header_html if total == 1 else f"{header_html} ({idx}/{total})"
        send_telegram(f"{prefix}\n\n{chunk}")

    issue_items = [
        f"{i}. [{p.get('title') or p['url']}]({p['url']})" for i, p in enumerate(posts, 1)
    ]
    issue_body = f"**{header_plain}**\n\n" + ("\n".join(issue_items) or "(ничего не найдено)")
    create_github_issue(title, issue_body)
