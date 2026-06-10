"""Minimal proxy endpoints for shop_xi front-end to avoid CORS and caching.

This module provides a small `proxy_fetch` whitelisted method that the
frontend can call at `/api/method/shop_xi.api.proxy_fetch` to retrieve
external feeds through the server (helps avoid CORS and rate-limits). It
implements a small allowlist and simple caching via `frappe.cache()`.
"""
from __future__ import annotations
import json
import frappe
from frappe import _
from frappe.utils import now


@frappe.whitelist(allow_guest=True)
def proxy_fetch(url: str, ttl: int = 60):
    """
    Fetch an external URL on behalf of the front-end and return JSON/text.

    Parameters:
    - url: full external URL to fetch
    - ttl: cache time in seconds (default 60)

    NOTE: This is intentionally minimal. Only use for public, non-sensitive
    endpoints. In production, restrict allowed hosts and add rate-limiting.
    """
    import requests

    # Basic host allowlist — extend as needed
    allowlist = [
        "cdn.jsdelivr.net",
        "api.github.com",
        "www.cisa.gov",
        "videos.pexels.com",
        "images.unsplash.com",
        "raw.githubusercontent.com",
    ]

    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        frappe.throw("Invalid URL scheme", frappe.ValidationError)

    hostname = parsed.hostname or ""
    if not any(hostname.endswith(allowed) for allowed in allowlist):
        frappe.throw("Host not allowed", frappe.PermissionError)

    cache_key = f"shop_xi:proxy:{url}"
    cached = frappe.cache().get_value(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except Exception:
            # fallthrough to refetch
            pass

    try:
        resp = requests.get(url, timeout=8)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "text/plain")
        body = resp.text
        payload = {"status": resp.status_code, "content_type": content_type, "body": body, "fetched_at": now()}
        try:
            frappe.cache().set_value(cache_key, json.dumps(payload), ttl)
        except Exception:
            # cache best-effort
            pass
        return payload
    except Exception as e:
        frappe.log_error(message=str(e), title="shop_xi.proxy_fetch")
        frappe.throw("Failed to fetch external feed", frappe.ValidationError)


@frappe.whitelist(allow_guest=True)
def submit_lead(name: str = None, email: str = None, service: str = None, message: str = None):
    """
    Accept a lead form submission and notify site owners. Minimal validation
    performed server-side. In production, persist to a DocType and add
    authentication/rate-limiting.
    """
    import re

    name = (name or "").strip()
    email = (email or "").strip()
    service = (service or "").strip()
    message = (message or "").strip()

    if not name or not email or not message:
        frappe.throw("Missing required fields", frappe.ValidationError)

    # basic email sanity check
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        frappe.throw("Invalid email address", frappe.ValidationError)

    try:
        subject = f"New enquiry from {name} — {service or 'General'}"
        body = f"Name: {name}\nEmail: {email}\nService: {service}\n\nMessage:\n{message}"
        # send to site contact — adjust address as needed
        recipients = ["info@veritycore.co.zw"]
        frappe.sendmail(recipients=recipients, subject=subject, message=body)

        # log an activity in system log for operators
        frappe.logger("shop_xi").info(f"Lead submitted: {name} <{email}> service={service}")
        return {"status": "ok", "message": "Lead submitted"}
    except Exception as e:
        frappe.log_error(message=str(e), title="shop_xi.submit_lead")
        frappe.throw("Failed to submit lead", frappe.ValidationError)
