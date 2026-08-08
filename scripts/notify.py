"""Send notifications via Telegram and a GitHub issue (for email, via
GitHub's own notification emails - no SMTP credentials needed)."""
from __future__ import annotations

import os

import requests


def send_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram credentials missing, skipping Telegram notification")
        return
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "disable_web_page_preview": False},
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


def build_message(post: dict) -> str:
    title = post.get("title") or "(без заголовка)"
    price = post.get("price") or "не указана"
    seller = post.get("seller") or "не указан"
    url = post.get("url", "")

    return (
        "Новое объявление\n\n"
        f"Название: {title}\n"
        f"Цена: {price}\n"
        f"Продавец: {seller}\n"
        f"Ссылка: {url}"
    )


def notify_new_post(post: dict) -> None:
    title = post.get("title") or "(без заголовка)"
    notify_user = os.environ.get("GITHUB_NOTIFY_USER", "")

    message = build_message(post)
    send_telegram(message)

    issue_body = message
    if notify_user:
        issue_body += f"\n\n@{notify_user}"
    create_github_issue(f"Новое объявление: {title}", issue_body)
