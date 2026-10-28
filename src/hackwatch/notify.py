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
    tracks = (f'<br><small><b>Tracks :</b> {html.escape(" · ".join(h.tracks))}</small>' if h.tracks else "")
    resume = f'<br><small style="color:#333">{html.escape(h.resume)}</small>' if h.resume else ""
    return (f'<li style="margin-bottom:12px"><a href="{html.escape(h.url)}"><b>{html.escape(h.title)}</b></a>'
            f'<br><span style="color:#555">{html.escape(meta)}</span>{tracks}{resume}'
            f'<br><small style="color:#777">{html.escape("; ".join(s.raisons))}</small></li>')


MAX_OTHERS = 150


def _other_row(s: Scored) -> str:
    h = s.hackathon
    when = f"{h.start:%d/%m/%Y}" if h.start else "?"
    if h.end:
        when += f" → {h.end:%d/%m/%Y}"
    warn = " ⚠ éligibilité restreinte" if any("éligibilité" in r for r in s.raisons) else ""
    cells = (f"{s.score:.2f}", f'<a href="{html.escape(h.url)}">{html.escape(h.title)}</a>{warn}',
             html.escape(when), html.escape(h.location or ("en ligne" if h.is_online else "")),
             html.escape(h.prize or ""))
    return "<tr>" + "".join(f'<td style="padding:2px 8px">{c}</td>' for c in cells) + "</tr>"


def render(items: list[Scored], others: list[Scored] | None = None, failed: list[str] | None = None) -> str:
    others = others or []
    groups: dict[str, list[Scored]] = {}
    for s in items:  # items déjà triés par score : l'ordre des axes suit le meilleur score
        groups.setdefault(s.axe, []).append(s)
    body = "".join(
        f"<h3>{html.escape(AXE_LABELS.get(axe, axe or 'Autres'))}</h3><ul>"
        + "".join(_item(s) for s in group) + "</ul>"
        for axe, group in groups.items()
    )
    if others:
        rows = "".join(_other_row(s) for s in others[:MAX_OTHERS])
        more = f"<p>… et {len(others) - MAX_OTHERS} autres</p>" if len(others) > MAX_OTHERS else ""
        body += (f"<h2>Autres hackathons (en ligne ou à Paris/IDF, sous le seuil de pertinence) : "
                 f'{len(others)}</h2><table style="font-size:13px;border-collapse:collapse">{rows}</table>{more}')
    foot = ""
    if failed:
        foot = f'<p style="color:#a00">Sources en échec : {html.escape(", ".join(failed))}</p>'
    s = "s" if len(items) > 1 else ""
    return f"<html><body><h2>{len(items)} hackathon{s} principa{'ux' if s else 'l'}</h2>{body}{foot}</body></html>"


def build_message(items: list[Scored], sender: str, to: str, others: list[Scored] | None = None,
                  failed: list[str] | None = None) -> EmailMessage:
    others = others or []
    msg = EmailMessage()
    msg["Subject"] = f"Hackathons du {date.today():%d/%m/%Y} : {len(items)} principaux, {len(others)} autres"
    msg["From"] = sender
    msg["To"] = to
    msg.set_content("\n".join(f"- {s.hackathon.title} ({s.score:.2f}) : {s.hackathon.url}" for s in items)
                    + f"\n\n{len(others)} autres hackathons sous le seuil"
                    + (f"\nSources en échec : {', '.join(failed)}" if failed else ""))
    msg.add_alternative(render(items, others, failed), subtype="html")
    return msg


def send(items: list[Scored], others: list[Scored] | None = None, failed: list[str] | None = None) -> None:
    load_dotenv()
    try:
        sender, password, to = (os.environ[k] for k in ("GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "EMAIL_TO"))
    except KeyError as e:
        raise RuntimeError(f"Variable manquante dans .env : {e.args[0]}") from None
    if not (sender and password and to):
        raise RuntimeError("Identifiants Gmail vides dans .env")
    msg = build_message(items, sender, to, others, failed)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(sender, password)
        s.send_message(msg)
