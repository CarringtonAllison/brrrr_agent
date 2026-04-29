"""Email digest of STRONG/GOOD deals via Gmail SMTP.

Configured via env vars: GMAIL_ADDRESS, GMAIL_APP_PASSWORD, NOTIFY_EMAIL.
If any are missing, send_digest is a no-op (returns False).
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from backend.config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD, NOTIFY_EMAIL

logger = logging.getLogger(__name__)


GRADE_ORDER = {"STRONG": 0, "GOOD": 1}


def filter_digest_listings(listings: list[dict]) -> list[dict]:
    """Keep STRONG/GOOD listings only, sorted STRONG first."""
    kept = [l for l in listings if l.get("grade") in GRADE_ORDER]
    kept.sort(key=lambda l: GRADE_ORDER.get(l.get("grade", ""), 99))
    return kept


def _fmt_money(n: float | int | None) -> str:
    if n is None:
        return "—"
    return f"${round(n):,}"


def _fmt_pct(n: float | None) -> str:
    if n is None:
        return "—"
    return f"{n * 100:.1f}%"


def build_digest_subject(listings: list[dict]) -> str:
    deals = filter_digest_listings(listings)
    if not deals:
        return "BRRRR digest — no qualifying deals today"
    return f"BRRRR digest — {len(deals)} deal{'s' if len(deals) != 1 else ''} worth a look"


def build_digest_html(listings: list[dict]) -> str:
    deals = filter_digest_listings(listings)
    if not deals:
        return "<p>No STRONG or GOOD deals found in this scan.</p>"

    rows = []
    for l in deals:
        addr = l.get("address", "—")
        city = l.get("city") or ""
        state = l.get("state") or ""
        location = f"{city}, {state}".strip(", ")
        url = l.get("listing_url")
        link = f'<a href="{url}">{addr}</a>' if url else addr
        rows.append(
            "<tr>"
            f'<td><strong style="color:{_grade_color(l["grade"])}">{l["grade"]}</strong></td>'
            f"<td>{link}<br/><span style='color:#666;font-size:12px'>{location}</span></td>"
            f"<td>{_fmt_money(l.get('price'))}</td>"
            f"<td>{_fmt_money(l.get('arv_likely') or l.get('arv'))}</td>"
            f"<td>{_fmt_money(l.get('monthly_cashflow'))}/mo</td>"
            f"<td>{_fmt_pct(l.get('coc_return'))}</td>"
            f"<td>{_fmt_money(l.get('cash_left_in_deal'))}</td>"
            "</tr>"
        )

    table = (
        '<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse;font-family:sans-serif;">'
        "<thead><tr style='background:#f3f4f6'>"
        "<th>Grade</th><th>Address</th><th>Price</th><th>ARV</th>"
        "<th>Cashflow</th><th>CoC</th><th>Cash Left</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )
    header = f"<h2>BRRRR Digest — {len(deals)} deal{'s' if len(deals) != 1 else ''}</h2>"
    return header + table


def _grade_color(grade: str) -> str:
    return {"STRONG": "#16a34a", "GOOD": "#2563eb"}.get(grade, "#6b7280")


def send_digest(listings: list[dict]) -> bool:
    """Send digest email to NOTIFY_EMAIL via Gmail SMTP. Returns True if sent."""
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD or not NOTIFY_EMAIL:
        logger.info("Email credentials not configured — skipping digest")
        return False

    deals = filter_digest_listings(listings)
    if not deals:
        logger.info("No STRONG/GOOD deals — skipping digest")
        return False

    msg = EmailMessage()
    msg["Subject"] = build_digest_subject(listings)
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = NOTIFY_EMAIL
    msg.set_content(f"You have {len(deals)} deals worth reviewing — open in HTML to see the table.")
    msg.add_alternative(build_digest_html(listings), subtype="html")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        logger.info(f"Digest sent to {NOTIFY_EMAIL} with {len(deals)} deals")
        return True
    except Exception as exc:
        logger.warning(f"Digest send failed: {exc}")
        return False
