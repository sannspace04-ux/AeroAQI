"""
src/api/routers/auth.py
========================
OTP-based authentication endpoints for AeroAQI.

These endpoints support the email and phone OTP login flow in the
frontend.  They are deliberately simple:

  POST /auth/otp/request  — generate and send a one-time password
  POST /auth/otp/verify   — verify the OTP and return a user profile

Provider configuration
----------------------
OTP delivery requires an external SMS/email provider.  The backend
reads the provider type and credentials from environment variables:

  AEROAQI_OTP_PROVIDER   — "email" | "sms" | "none" (default "none")
  AEROAQI_OTP_FROM       — sender address or phone number
  AEROAQI_OTP_API_KEY    — provider API key (kept server-side, never exposed)

When AEROAQI_OTP_PROVIDER is "none" (or unset) these endpoints return
HTTP 503 with a clear explanation.  They never pretend to have sent an
OTP when no provider is configured.

Storage
-------
OTPs are stored in an in-process dict keyed by (channel, identifier).
Each entry has an expiry timestamp.  This is sufficient for the SIH
prototype; a production deployment should use Redis or a DB table.

Security
--------
- OTP values are NEVER returned in API responses.
- OTP values are NEVER written to logs.
- Credentials are read from environment variables only.
- OTPs are 6 digits, valid for 10 minutes, and single-use.
"""

from __future__ import annotations

import os
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Auth"])

# ---------------------------------------------------------------------------
# In-process OTP store
# {(channel, identifier): {"otp_hash": str, "expires_at": float, "used": bool}}
# ---------------------------------------------------------------------------
_OTP_STORE: dict[tuple, dict] = {}
_OTP_TTL_SECONDS = 600   # 10 minutes
_OTP_DIGITS = 6


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class OtpRequestBody(BaseModel):
    channel: str = Field(
        ...,
        description="Delivery channel: 'email' or 'phone'",
        examples=["email"],
    )
    identifier: str = Field(
        ...,
        description="Email address or phone number (E.164 format recommended)",
        examples=["user@example.com"],
    )


class OtpRequestResponse(BaseModel):
    sent: bool
    message: str
    provider: str


class OtpVerifyBody(BaseModel):
    channel: str
    identifier: str
    otp: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class OtpVerifyResponse(BaseModel):
    verified: bool
    user: Optional[dict] = None
    message: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_provider() -> str:
    """Return the configured OTP provider name, lower-cased."""
    return os.getenv("AEROAQI_OTP_PROVIDER", "none").strip().lower()


def _generate_otp() -> str:
    """Return a cryptographically adequate 6-digit OTP string."""
    return str(random.SystemRandom().randint(0, 999999)).zfill(_OTP_DIGITS)


def _otp_key(channel: str, identifier: str) -> tuple:
    return (channel.strip().lower(), identifier.strip().lower())


def _store_otp(channel: str, identifier: str, otp: str) -> None:
    """Store OTP hash with expiry.  The raw OTP is never kept."""
    import hashlib
    key = _otp_key(channel, identifier)
    otp_hash = hashlib.sha256(otp.encode()).hexdigest()
    _OTP_STORE[key] = {
        "otp_hash": otp_hash,
        "expires_at": time.monotonic() + _OTP_TTL_SECONDS,
        "used": False,
    }


def _verify_and_consume_otp(channel: str, identifier: str, otp: str) -> bool:
    """
    Return True if the OTP matches and has not expired or been used.
    Marks the entry as used on success.
    """
    import hashlib
    key = _otp_key(channel, identifier)
    entry = _OTP_STORE.get(key)

    if entry is None:
        return False
    if entry["used"]:
        return False
    if time.monotonic() > entry["expires_at"]:
        _OTP_STORE.pop(key, None)
        return False

    otp_hash = hashlib.sha256(otp.encode()).hexdigest()
    if otp_hash != entry["otp_hash"]:
        return False

    # Single-use: mark as consumed
    entry["used"] = True
    return True


def _send_otp_email(to_address: str, otp: str) -> None:
    """
    Send OTP via email using the configured provider.
    Currently supports SMTP (via smtplib) when credentials are present.
    Raises RuntimeError if sending fails.
    Does NOT log the OTP value.
    """
    smtp_host = os.getenv("AEROAQI_SMTP_HOST", "")
    smtp_port = int(os.getenv("AEROAQI_SMTP_PORT", "587"))
    smtp_user = os.getenv("AEROAQI_SMTP_USER", "")
    smtp_pass = os.getenv("AEROAQI_SMTP_PASS", "")
    from_addr = os.getenv("AEROAQI_OTP_FROM", smtp_user)

    if not smtp_host or not smtp_user or not smtp_pass:
        raise RuntimeError(
            "Email OTP requires AEROAQI_SMTP_HOST, AEROAQI_SMTP_USER, "
            "AEROAQI_SMTP_PASS in .env"
        )

    import smtplib
    from email.mime.text import MIMEText

    body = (
        f"Your AeroAQI verification code is: {otp}\n\n"
        f"This code is valid for {_OTP_TTL_SECONDS // 60} minutes.\n"
        f"Do not share this code with anyone."
    )
    msg = MIMEText(body)
    msg["Subject"] = "AeroAQI — Your verification code"
    msg["From"] = from_addr
    msg["To"] = to_address

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_addr, [to_address], msg.as_string())
        log.info(f"[auth] OTP email sent to {to_address[:3]}***")
    except Exception as exc:
        raise RuntimeError(f"SMTP send failed: {exc}") from exc


def _send_otp_sms(to_number: str, otp: str) -> None:
    """
    Send OTP via SMS using the configured provider.
    Currently supports Twilio when credentials are present.
    Raises RuntimeError if sending fails.
    Does NOT log the OTP value.
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    auth_token  = os.getenv("TWILIO_AUTH_TOKEN", "")
    from_number = os.getenv("AEROAQI_OTP_FROM", "")

    if not account_sid or not auth_token or not from_number:
        raise RuntimeError(
            "SMS OTP requires TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, "
            "AEROAQI_OTP_FROM in .env"
        )

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        client.messages.create(
            body=f"Your AeroAQI code: {otp} (valid {_OTP_TTL_SECONDS // 60} min)",
            from_=from_number,
            to=to_number,
        )
        log.info(f"[auth] OTP SMS sent to ***{to_number[-4:]}")
    except ImportError:
        raise RuntimeError(
            "twilio package is not installed. "
            "Run: pip install twilio  or switch to email OTP."
        )
    except Exception as exc:
        raise RuntimeError(f"Twilio SMS send failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/otp/request",
    response_model=OtpRequestResponse,
    summary="Request an OTP for email or phone login",
    description=(
        "Generates a 6-digit one-time password and sends it to the provided "
        "email address or phone number. \n\n"
        "**Requires** `AEROAQI_OTP_PROVIDER` to be set in the server `.env` "
        "file.  Returns HTTP 503 with a clear message when no provider is "
        "configured — it never pretends to have sent an OTP."
    ),
)
def request_otp(body: OtpRequestBody) -> OtpRequestResponse:
    """Generate and send an OTP, or explain why it cannot be sent."""
    provider = _get_provider()

    if provider == "none":
        log.info(
            "[auth] OTP request received but AEROAQI_OTP_PROVIDER is not "
            "configured — returning 503."
        )
        raise HTTPException(
            status_code=503,
            detail={
                "code": "OTP_PROVIDER_NOT_CONFIGURED",
                "message": (
                    "OTP delivery is not configured on this server. "
                    "Set AEROAQI_OTP_PROVIDER (email or sms) and the "
                    "corresponding credentials in the server .env file."
                ),
                "provider": "none",
            },
        )

    channel = body.channel.strip().lower()
    identifier = body.identifier.strip()

    if channel not in ("email", "phone"):
        raise HTTPException(
            status_code=422,
            detail="channel must be 'email' or 'phone'.",
        )

    otp = _generate_otp()
    _store_otp(channel, identifier, otp)

    try:
        if channel == "email":
            _send_otp_email(identifier, otp)
        else:
            _send_otp_sms(identifier, otp)
    except RuntimeError as exc:
        # Clean up the stored OTP — it was never delivered
        _OTP_STORE.pop(_otp_key(channel, identifier), None)
        log.error(f"[auth] OTP delivery failed for channel={channel}: {exc}")
        raise HTTPException(
            status_code=502,
            detail={
                "code": "OTP_DELIVERY_FAILED",
                "message": str(exc),
                "provider": provider,
            },
        ) from exc

    return OtpRequestResponse(
        sent=True,
        message=f"OTP sent via {channel}.",
        provider=provider,
    )


@router.post(
    "/otp/verify",
    response_model=OtpVerifyResponse,
    summary="Verify an OTP and obtain a user session",
    description=(
        "Verifies a 6-digit OTP previously sent by POST /auth/otp/request. "
        "Returns the user profile on success. "
        "The OTP is single-use and expires after 10 minutes."
    ),
)
def verify_otp(body: OtpVerifyBody) -> OtpVerifyResponse:
    """Verify the OTP and return a user profile on success."""
    channel    = body.channel.strip().lower()
    identifier = body.identifier.strip()

    if _get_provider() == "none":
        raise HTTPException(
            status_code=503,
            detail={
                "code": "OTP_PROVIDER_NOT_CONFIGURED",
                "message": (
                    "OTP verification is not available because no OTP provider "
                    "is configured.  Set AEROAQI_OTP_PROVIDER in the server .env file."
                ),
            },
        )

    valid = _verify_and_consume_otp(channel, identifier, body.otp)

    if not valid:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "OTP_INVALID_OR_EXPIRED",
                "message": (
                    "The OTP is invalid or has expired. "
                    "Request a new one via POST /auth/otp/request."
                ),
            },
        )

    # Build a minimal user profile from the identifier
    if channel == "email":
        name = identifier.split("@")[0].replace(".", " ").title()
        user = {"name": name, "email": identifier, "phone": ""}
    else:
        user = {"name": "AeroAQI User", "email": "", "phone": identifier}

    log.info(f"[auth] OTP verified for channel={channel} identifier=***")

    return OtpVerifyResponse(
        verified=True,
        user=user,
        message="OTP verified successfully.",
    )


@router.get(
    "/otp/status",
    summary="OTP provider configuration status",
    description=(
        "Returns the OTP provider status so the frontend can show the "
        "correct UI state without attempting to send an OTP first."
    ),
    response_model=dict,
)
def otp_status() -> dict:
    """Return whether the OTP provider is configured (never reveals credentials)."""
    provider = _get_provider()
    return {
        "configured": provider != "none",
        "provider": provider if provider != "none" else None,
        "message": (
            f"OTP provider '{provider}' is configured."
            if provider != "none"
            else (
                "No OTP provider configured. Set AEROAQI_OTP_PROVIDER in "
                "the server .env file to enable email or SMS OTP login."
            )
        ),
    }
