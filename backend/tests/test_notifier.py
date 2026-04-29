"""Tests for notifier — email digest of STRONG/GOOD deals."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.notifier import (
    build_digest_html,
    build_digest_subject,
    filter_digest_listings,
    send_digest,
)


def make_listing(grade: str = "STRONG", **overrides) -> dict:
    base = {
        "id": "l-1",
        "address": "123 Strong St",
        "city": "Cleveland",
        "state": "OH",
        "price": 55_000,
        "arv_likely": 120_000,
        "estimated_rent": 1500,
        "grade": grade,
        "monthly_cashflow": 250,
        "coc_return": 0.18,
        "cash_left_in_deal": 2000,
        "listing_url": "https://redfin.com/x",
    }
    base.update(overrides)
    return base


# ── filter_digest_listings ────────────────────────────────────────────────────

class TestFilterListings:
    def test_keeps_only_strong_and_good(self):
        listings = [
            make_listing(grade="STRONG"),
            make_listing(grade="GOOD"),
            make_listing(grade="MAYBE"),
            make_listing(grade="SKIP"),
        ]
        kept = filter_digest_listings(listings)
        assert len(kept) == 2
        grades = {l["grade"] for l in kept}
        assert grades == {"STRONG", "GOOD"}

    def test_sorts_strong_first(self):
        listings = [
            make_listing(grade="GOOD", id="g"),
            make_listing(grade="STRONG", id="s"),
        ]
        kept = filter_digest_listings(listings)
        assert kept[0]["grade"] == "STRONG"
        assert kept[1]["grade"] == "GOOD"

    def test_empty_list_returns_empty(self):
        assert filter_digest_listings([]) == []


# ── build_digest_html ─────────────────────────────────────────────────────────

class TestBuildDigestHtml:
    def test_includes_addresses(self):
        html = build_digest_html([make_listing(address="123 Apple St"), make_listing(address="456 Oak Ave")])
        assert "123 Apple St" in html
        assert "456 Oak Ave" in html

    def test_includes_grade_and_metrics(self):
        html = build_digest_html([make_listing(grade="STRONG", monthly_cashflow=250)])
        assert "STRONG" in html
        assert "$250" in html or "250" in html

    def test_empty_listings_returns_empty_state(self):
        html = build_digest_html([])
        assert "no" in html.lower() or "0" in html


# ── build_digest_subject ──────────────────────────────────────────────────────

class TestBuildDigestSubject:
    def test_includes_count(self):
        subject = build_digest_subject([make_listing(), make_listing()])
        assert "2" in subject

    def test_zero_count(self):
        subject = build_digest_subject([])
        assert "0" in subject or "no" in subject.lower()


# ── send_digest ───────────────────────────────────────────────────────────────

class TestSendDigest:
    def test_no_credentials_skips_send(self):
        # Patch credentials to empty
        with patch("backend.notifier.GMAIL_ADDRESS", ""), \
             patch("backend.notifier.GMAIL_APP_PASSWORD", ""), \
             patch("backend.notifier.NOTIFY_EMAIL", ""), \
             patch("backend.notifier.smtplib.SMTP_SSL") as mock_smtp:
            sent = send_digest([make_listing()])
        assert sent is False
        mock_smtp.assert_not_called()

    def test_no_listings_skips_send(self):
        with patch("backend.notifier.GMAIL_ADDRESS", "x@y.com"), \
             patch("backend.notifier.GMAIL_APP_PASSWORD", "pw"), \
             patch("backend.notifier.NOTIFY_EMAIL", "z@y.com"), \
             patch("backend.notifier.smtplib.SMTP_SSL") as mock_smtp:
            sent = send_digest([])
        assert sent is False
        mock_smtp.assert_not_called()

    def test_sends_email_when_configured(self):
        mock_server = MagicMock()
        mock_smtp_class = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        with patch("backend.notifier.GMAIL_ADDRESS", "x@y.com"), \
             patch("backend.notifier.GMAIL_APP_PASSWORD", "pw"), \
             patch("backend.notifier.NOTIFY_EMAIL", "z@y.com"), \
             patch("backend.notifier.smtplib.SMTP_SSL", mock_smtp_class):
            sent = send_digest([make_listing(grade="STRONG"), make_listing(grade="SKIP")])

        assert sent is True
        mock_server.login.assert_called_once_with("x@y.com", "pw")
        assert mock_server.send_message.called

    def test_smtp_error_returns_false(self):
        mock_smtp_class = MagicMock()
        mock_smtp_class.return_value.__enter__.side_effect = Exception("SMTP down")

        with patch("backend.notifier.GMAIL_ADDRESS", "x@y.com"), \
             patch("backend.notifier.GMAIL_APP_PASSWORD", "pw"), \
             patch("backend.notifier.NOTIFY_EMAIL", "z@y.com"), \
             patch("backend.notifier.smtplib.SMTP_SSL", mock_smtp_class):
            sent = send_digest([make_listing()])
        assert sent is False
