from __future__ import annotations

import html
import os
import smtplib
import ssl
from datetime import date
from email.message import EmailMessage

from dotenv import load_dotenv

from hackwatch.models import Hackathon


def render(items: list[Hackathon]) -> str:
    rows = []
    for h in items:
        when = f"{h.start:%d/%m/%Y}" if h.start else "?"
        if h.end:
            when += f" → {h.end:%d/%m/%Y}"
        meta = " · ".join(x for x in (h.source, h.location, when, h.prize) if x)
        tags = ", ".join(t for t in h.tags if t)
        rows.append(
            f'<li style="margin-bottom:12px"><a href="{html.escape(h.url)}"><b>{html.escape(h.title)}</b></a>'
            f'<br><span style="color:#555">{html.escape(meta)}</span>'
            + (f"<br><small>{html.escape(tags)}</small>" if tags else "")
            + "</li>"
        )
    return (f"<html><body><h2>{len(items)} nouveaux hackathons</h2><ul>"
            + "".join(rows) + "</ul></body></html>")


def build_message(items: list[Hackathon], sender: str, to: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"Hackathons du {date.today():%d/%m/%Y} : {len(items)} nouveautés"
    msg["From"] = sender
    msg["To"] = to
    msg.set_content("\n".join(f"- {h.title} : {h.url}" for h in items))
    msg.add_alternative(render(items), subtype="html")
    return msg


def send(items: list[Hackathon]) -> None:
    load_dotenv()
    try:
        sender, password, to = (os.environ[k] for k in ("GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "EMAIL_TO"))
    except KeyError as e:
        raise RuntimeError(f"Variable manquante dans .env : {e.args[0]}") from None
    if not (sender and password and to):
        raise RuntimeError("Identifiants Gmail vides dans .env")
    msg = build_message(items, sender, to)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(sender, password)
        s.send_message(msg)
