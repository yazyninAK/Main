"""Send notifications via Telegram and email (Gmail SMTP)."""
from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText

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


def send_email(subject: str, body: str) -> None:
    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")
    to_address = os.environ.get("NOTIFY_EMAIL_TO", gmail_address)
    if not gmail_address or not gmail_app_password or not to_address:
        print("Email credentials missing, skipping email notification")
        return

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = to_address

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_address, gmail_app_password)
        server.sendmail(gmail_address, [to_address], msg.as_string())


def notify_new_post(post: dict) -> None:
    title = post.get("title", "(без заголовка)")
    url = post.get("url", "")
    text = post.get("text", "")

    message = f"Новое объявление:\n{title}\n{url}\n\n{text}".strip()
    send_telegram(message)
    send_email(f"Новое объявление: {title}", message)
