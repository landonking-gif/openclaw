"""
OpenClaw Army — Notification Service
=====================================

Email notification service using SMTP (Gmail) for system alerts,
task completions, daily digests, and on-demand messages.

Port: 18870

Uses GMAIL_APP_PASSWORD from .env for authentication.
"""

import logging
import os
import smtplib
import ssl
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

# Add shared utilities to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── Config ──────────────────────────────────────────────────────────────────

NOTIFICATION_PORT = int(os.getenv("NOTIFICATION_PORT", "18870"))
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
DEFAULT_RECIPIENT = os.getenv("NOTIFICATION_EMAIL", os.getenv("OWNER_EMAIL", ""))
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [notification] %(levelname)s %(message)s",
)
log = logging.getLogger("notification")

# ── Models ──────────────────────────────────────────────────────────────────

class EmailRequest(BaseModel):
    to: Optional[str] = None  # defaults to NOTIFICATION_EMAIL
    subject: str
    body: str
    html: Optional[str] = None
    priority: str = "normal"  # low, normal, high, critical
    source: str = "system"  # which service/agent sent this


class NotificationRecord(BaseModel):
    id: str
    to: str
    subject: str
    source: str
    priority: str
    sent_at: str
    success: bool
    error: Optional[str] = None


# ── State ───────────────────────────────────────────────────────────────────

history: list[NotificationRecord] = []
_counter = 0

# ── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="OpenClaw Army — Notification Service",
    description="Email notifications for system events, task completion, and alerts.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    from shared.logging_middleware import StructuredLoggingMiddleware
    app.add_middleware(StructuredLoggingMiddleware, service_name="notification")
except ImportError:
    pass

# ── Helpers ─────────────────────────────────────────────────────────────────

def _send_email(to: str, subject: str, body: str, html: Optional[str] = None) -> None:
    """Send email via Gmail SMTP. Raises on failure."""
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        raise RuntimeError("GMAIL_USER or GMAIL_APP_PASSWORD not configured")

    msg = MIMEMultipart("alternative")
    msg["From"] = f"OpenClaw Army <{GMAIL_USER}>"
    msg["To"] = to
    msg["Subject"] = f"[OpenClaw] {subject}"

    msg.attach(MIMEText(body, "plain"))
    if html:
        msg.attach(MIMEText(html, "html"))

    ctx = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls(context=ctx)
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, to, msg.as_string())


# ── Endpoints ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    configured = bool(GMAIL_USER and GMAIL_APP_PASSWORD)
    return {
        "status": "healthy",
        "service": "notification",
        "smtp_configured": configured,
        "total_sent": len([h for h in history if h.success]),
        "total_failed": len([h for h in history if not h.success]),
    }


@app.post("/send")
async def send_notification(req: EmailRequest):
    """Send an email notification."""
    global _counter
    _counter += 1
    record_id = f"notif-{_counter:06d}"
    recipient = req.to or DEFAULT_RECIPIENT

    if not recipient:
        raise HTTPException(400, "No recipient specified and NOTIFICATION_EMAIL not set")

    log.info(f"Sending [{req.priority}] to {recipient}: {req.subject}")

    try:
        _send_email(recipient, req.subject, req.body, req.html)
        rec = NotificationRecord(
            id=record_id,
            to=recipient,
            subject=req.subject,
            source=req.source,
            priority=req.priority,
            sent_at=datetime.now(timezone.utc).isoformat(),
            success=True,
        )
        history.append(rec)
        log.info(f"Sent {record_id} to {recipient}")
        return {"id": record_id, "status": "sent", "to": recipient}

    except Exception as e:
        rec = NotificationRecord(
            id=record_id,
            to=recipient,
            subject=req.subject,
            source=req.source,
            priority=req.priority,
            sent_at=datetime.now(timezone.utc).isoformat(),
            success=False,
            error=str(e),
        )
        history.append(rec)
        log.error(f"Failed to send {record_id}: {e}")
        raise HTTPException(502, f"Email delivery failed: {e}")


@app.post("/alert")
async def send_alert(subject: str, body: str, source: str = "system"):
    """Quick alert endpoint — sends to default recipient at high priority."""
    req = EmailRequest(subject=subject, body=body, source=source, priority="high")
    return await send_notification(req)


@app.get("/history")
async def get_history(limit: int = 50, source: Optional[str] = None):
    """Get notification history."""
    items = list(reversed(history))
    if source:
        items = [h for h in items if h.source == source]
    return {
        "total": len(items),
        "notifications": [h.model_dump() for h in items[:limit]],
    }


@app.on_event("startup")
async def startup():
    configured = bool(GMAIL_USER and GMAIL_APP_PASSWORD)
    log.info(f"Notification service starting on port {NOTIFICATION_PORT}")
    if not configured:
        log.warning("SMTP not configured — emails will fail. Set GMAIL_USER and GMAIL_APP_PASSWORD.")
