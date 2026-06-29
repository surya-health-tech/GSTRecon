"""Gmail API helpers for platform outbound email."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from email import policy
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr

from app.services.oauth_http import format_http_error, http_ssl_context


def _normalize_in_reply_to(message_id: str | None) -> str | None:
    if not message_id:
        return None
    mid = str(message_id).strip()
    if not mid:
        return None
    if mid.startswith("<") and mid.endswith(">"):
        return mid
    return f"<{mid}>" if "@" in mid else mid


def build_plain_reply_mime(
    *,
    from_email: str,
    from_display: str | None,
    to_email: str,
    subject: str,
    body: str,
    in_reply_to: str | None,
) -> bytes:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = str(Header(subject, "utf-8"))
    if from_display:
        msg["From"] = formataddr((from_display, from_email))
    else:
        msg["From"] = from_email
    msg["To"] = to_email
    irt = _normalize_in_reply_to(in_reply_to)
    if irt:
        msg["In-Reply-To"] = irt
        msg["References"] = irt
    return msg.as_bytes(policy=policy.SMTP)


def _gmail_api_send_raw(access_token: str, raw_rfc822: bytes) -> dict:
    raw_b64 = base64.urlsafe_b64encode(raw_rfc822).decode("ascii")
    payload = json.dumps({"raw": raw_b64}).encode("utf-8")
    req = urllib.request.Request(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60, context=http_ssl_context()) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(format_http_error(e)) from e
