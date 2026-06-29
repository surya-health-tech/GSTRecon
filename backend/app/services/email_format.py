"""Greeting + signature decoration for outbound emails.

All transactional outbound mail (Task email tab, Waiting On Client reminders,
dependency notifications, portal invite/OTP, assignee notify, Triage replies)
flows through ``decorate_email_body`` so the wire format is consistent:

    Hi <FirstName>,

    <existing body content untouched>

    Thanks,
    <signer>

If the body already starts with a recognizable greeting (``Hi/Hello/Hey/Dear``)
we skip prepending another one. If it already ends with a sign-off
(``Thanks/Regards/Sincerely/Cheers/Best [regards]``) followed by a name line
we skip appending another. This keeps the helper safe to call repeatedly and
safe to call on bodies users typed by hand in the UI.

The helper is plain-text by design — every send path currently uses
``MIMEText(..., "plain")``. When/if the platform grows HTML email, give this
module an HTML twin that emits ``<p>``/``<br>`` separators instead.
"""

from __future__ import annotations

import re

# A greeting is the FIRST non-empty line and looks like "Hi Foo," / "Hello Foo,"
# / "Hey," / "Dear Foo,". We accept the line whether or not a comma is present
# so user-typed greetings without one still count.
_GREETING_RE = re.compile(
    r"^\s*(hi|hello|hey|dear)\b[^\n]*\n",
    re.IGNORECASE,
)

# A signature is a trailing "Thanks,"/"Regards,"/"Sincerely," (etc.) followed
# by one short name line at the end of the body. We require the sign-off and
# its name to be the last two non-empty lines so legitimate "thanks" inside the
# body don't suppress the decorator.
_SIGNATURE_RE = re.compile(
    r"(?:^|\n)\s*(thanks|thank you|regards|kind regards|best regards|best|sincerely|cheers)\s*[,.]?\s*\n[^\n]*\S[ \t]*\s*$",
    re.IGNORECASE,
)


def first_name_of(name: str | None) -> str | None:
    """Return the first word of a display name, suitable for "Hi <X>,".

    Returns ``None`` when no usable name can be derived; callers should fall
    back to a generic "Hi,". Strips surrounding punctuation so synthetic
    display names like ``"(External) Surya"`` still produce ``"Surya"``.
    """
    if not name:
        return None
    parts = name.strip().split()
    if not parts:
        return None
    candidate = re.sub(r"^[^A-Za-z]+|[^A-Za-z]+$", "", parts[0])
    return candidate or None


def tenant_team_signer(tenant_name: str | None) -> str:
    """Signature label for system-generated emails: ``"<Tenant> Team"``."""
    name = (tenant_name or "").strip()
    return f"{name} Team" if name else "Team"


def decorate_email_body(
    body: str,
    *,
    recipient_name: str | None,
    signer_name: str,
) -> str:
    """Wrap ``body`` with a personalized greeting and a Thanks/<signer> footer.

    Idempotent — see module docstring for the duplicate-detection rules.
    Always returns a plain-text string ending with a single newline so the
    downstream MIME builder produces a clean message.
    """
    text = (body or "").strip("\n")

    first = first_name_of(recipient_name)
    greeting = f"Hi {first}," if first else "Hi,"

    has_greeting = bool(_GREETING_RE.match(text))
    has_signature = bool(_SIGNATURE_RE.search(text))

    pieces: list[str] = []
    if not has_greeting:
        pieces.append(greeting)
        pieces.append("")
    pieces.append(text)
    if not has_signature:
        signer = (signer_name or "").strip() or "Team"
        pieces.append("")
        pieces.append("Thanks,")
        pieces.append(signer)
    return "\n".join(pieces).rstrip() + "\n"
