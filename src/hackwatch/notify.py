from __future__ import annotations

import html
import os
import smtplib
import ssl
from datetime import date
from email.message import EmailMessage

from dotenv import load_dotenv

from hackwatch.scoring import AXE_LABELS, Scored


def _item(s: Scored) -> str:
    h = s.hackathon
    when = f"{h.start:%d/%m/%Y}" if h.start else "?"
    if h.end:
        when += f" → {h.end:%d/%m/%Y}"
    meta = " · ".join(x for x in (when, h.location or ("en ligne" if h.is_online else ""),
                                  h.prize, f"score {s.score:.2f}") if x)
    return (f'<li style="margin-bottom:12px"><a href="{html.escape(h.url)}"><b>{html.escape(h.title)}</b></a>'
            f'<br><span style="color:#555">{html.escape(meta)}</span>'
            f'<br><small>{html.escape("; ".join(s.raisons))}</small></li>')


def render(items: list[Scored], n_below: int = 0, failed: list[str] | None = None) -> str:
    groups: dict[str, list[Scored]] = {}
    for s in items:  # items déjà triés par score : l'ordre des axes suit le meilleur score
        groups.setdefault(s.axe, []).append(s)
    body = "".join(
        f"<h3>{html.escape(AXE_LABELS.get(axe, axe or 'Autres'))}</h3><ul>"
        + "".join(_item(s) for s in group) + "</ul>"
        for axe, group in groups.items()
    )
    foot = f'<p style="color:#777">{n_below} autres hackathons sous le seuil</p>'
    if failed:
        foot += f'<p style="color:#a00">Sources en échec : {html.escape(", ".join(failed))}</p>'
    return f"<html><body><h2>{len(items)} hackathons pour toi</h2>{body}{foot}</body></html>"


def build_message(items: list[Scored], sender: str, to: str, n_below: int = 0,
                  failed: list[str] | None = None) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"Hackathons du {date.today():%d/%m/%Y} : {len(items)} pour toi"
    msg["From"] = sender
    msg["To"] = to
    msg.set_content("\n".join(f"- {s.hackathon.title} ({s.score:.2f}) : {s.hackathon.url}" for s in items)
                    + f"\n\n{n_below} autres hackathons sous le seuil"
                    + (f"\nSources en échec : {', '.join(failed)}" if failed else ""))
    msg.add_alternative(render(items, n_below, failed), subtype="html")
    return msg


def send(items: list[Scored], n_below: int = 0, failed: list[str] | None = None) -> None:
    load_dotenv()
    try:
        sender, password, to = (os.environ[k] for k in ("GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "EMAIL_TO"))
    except KeyError as e:
        raise RuntimeError(f"Variable manquante dans .env : {e.args[0]}") from None
    if not (sender and password and to):
        raise RuntimeError("Identifiants Gmail vides dans .env")
    msg = build_message(items, sender, to, n_below, failed)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(sender, password)
        s.send_message(msg)
