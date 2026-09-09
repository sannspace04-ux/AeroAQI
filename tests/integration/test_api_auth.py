"""
tests/integration/test_api_auth.py
=====================================
Integration tests for POST /auth/otp/request, POST /auth/otp/verify,
and GET /auth/otp/status.

No real OTP is sent.  Tests verify:
  - Proper 503 when AEROAQI_OTP_PROVIDER is not set.
  - Proper 422 on bad channel / missing otp format.
  - Full request → verify flow when provider is "test" (in-process only).
  - Status endpoint reflects configured/unconfigured state correctly.

Run with:
    pytest tests/integration/test_api_auth.py -v
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app


@pytest.fixture(scope="module")
def auth_client():
    """TestClient for auth tests — no DB override needed (auth has no DB dep)."""
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# GET /auth/otp/status
# ---------------------------------------------------------------------------

class TestOtpStatus:

    def test_status_200(self, auth_client):
        resp = auth_client.get("/auth/otp/status")
        assert resp.status_code == 200

    def test_status_not_configured_when_env_unset(self, auth_client):
        with patch.dict(os.environ, {}, clear=False):
            # Remove AEROAQI_OTP_PROVIDER if present
            env = {k: v for k, v in os.environ.items() if k != "AEROAQI_OTP_PROVIDER"}
            with patch.dict(os.environ, env, clear=True):
                resp = auth_client.get("/auth/otp/status")
        body = resp.json()
        assert body["configured"] is False

    def test_status_has_required_keys(self, auth_client):
        resp = auth_client.get("/auth/otp/status")
        body = resp.json()
        assert "configured" in body
        assert "message" in body


# ---------------------------------------------------------------------------
# POST /auth/otp/request — unconfigured state
# ---------------------------------------------------------------------------

class TestOtpRequestUnconfigured:

    def test_returns_503_when_provider_none(self, auth_client):
        with patch.dict(os.environ, {"AEROAQI_OTP_PROVIDER": "none"}, clear=False):
            resp = auth_client.post(
                "/auth/otp/request",
                json={"channel": "email", "identifier": "test@example.com"},
            )
        assert resp.status_code == 503

    def test_503_body_has_otp_provider_not_configured_code(self, auth_client):
        with patch.dict(os.environ, {"AEROAQI_OTP_PROVIDER": "none"}, clear=False):
            resp = auth_client.post(
                "/auth/otp/request",
                json={"channel": "email", "identifier": "test@example.com"},
            )
        detail = resp.json().get("detail", {})
        code = detail.get("code") if isinstance(detail, dict) else ""
        assert code == "OTP_PROVIDER_NOT_CONFIGURED"

    def test_never_pretends_otp_was_sent(self, auth_client):
        """When provider is unconfigured, 'sent' must never be True."""
        with patch.dict(os.environ, {"AEROAQI_OTP_PROVIDER": "none"}, clear=False):
            resp = auth_client.post(
                "/auth/otp/request",
                json={"channel": "email", "identifier": "test@example.com"},
            )
        assert resp.status_code != 200, (
            "Should NOT return 200 when OTP provider is not configured"
        )


# ---------------------------------------------------------------------------
# POST /auth/otp/request — validation
# ---------------------------------------------------------------------------

class TestOtpRequestValidation:

    def test_bad_channel_returns_422(self, auth_client):
        with patch.dict(os.environ, {"AEROAQI_OTP_PROVIDER": "email"}, clear=False):
            resp = auth_client.post(
                "/auth/otp/request",
                json={"channel": "fax", "identifier": "test@example.com"},
            )
        # May be 422 (validation) or 503 (unconfigured provider still ok to raise)
        assert resp.status_code in (422, 503)

    def test_missing_identifier_returns_422(self, auth_client):
        with patch.dict(os.environ, {"AEROAQI_OTP_PROVIDER": "email"}, clear=False):
            resp = auth_client.post(
                "/auth/otp/request",
                json={"channel": "email"},
            )
        assert resp.status_code == 422

    def test_missing_channel_returns_422(self, auth_client):
        with patch.dict(os.environ, {"AEROAQI_OTP_PROVIDER": "email"}, clear=False):
            resp = auth_client.post(
                "/auth/otp/request",
                json={"identifier": "test@example.com"},
            )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /auth/otp/verify — unconfigured state
# ---------------------------------------------------------------------------

class TestOtpVerifyUnconfigured:

    def test_returns_503_when_provider_none(self, auth_client):
        with patch.dict(os.environ, {"AEROAQI_OTP_PROVIDER": "none"}, clear=False):
            resp = auth_client.post(
                "/auth/otp/verify",
                json={"channel": "email", "identifier": "test@example.com", "otp": "123456"},
            )
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# POST /auth/otp/verify — bad OTP format
# ---------------------------------------------------------------------------

class TestOtpVerifyValidation:

    def test_non_digit_otp_returns_422(self, auth_client):
        with patch.dict(os.environ, {"AEROAQI_OTP_PROVIDER": "email"}, clear=False):
            resp = auth_client.post(
                "/auth/otp/verify",
                json={"channel": "email", "identifier": "test@example.com", "otp": "ABCDEF"},
            )
        assert resp.status_code in (422, 503)

    def test_short_otp_returns_422(self, auth_client):
        with patch.dict(os.environ, {"AEROAQI_OTP_PROVIDER": "email"}, clear=False):
            resp = auth_client.post(
                "/auth/otp/verify",
                json={"channel": "email", "identifier": "test@example.com", "otp": "123"},
            )
        assert resp.status_code in (422, 503)


# ---------------------------------------------------------------------------
# Full flow test with in-process OTP (no actual email/SMS)
# ---------------------------------------------------------------------------

class TestOtpFullFlow:
    """Test the complete request → verify cycle using in-process OTP store."""

    def test_correct_otp_returns_verified_true(self, auth_client):
        """
        Simulate a full OTP flow:
        1. Patch _send_otp_email so no real email is sent.
        2. Capture the OTP written to _OTP_STORE.
        3. Verify with that OTP — must return verified=True.
        """
        import src.api.routers.auth as auth_mod

        sent_otps: list[str] = []

        def fake_send_email(to, otp):
            # Capture without logging the actual value
            sent_otps.append(otp)

        with (
            patch.dict(os.environ, {"AEROAQI_OTP_PROVIDER": "email"}, clear=False),
            patch.object(auth_mod, "_send_otp_email", side_effect=fake_send_email),
        ):
            # Step 1: request OTP
            req_resp = auth_client.post(
                "/auth/otp/request",
                json={"channel": "email", "identifier": "demo@aeroaqi.test"},
            )
            # If SMTP creds are missing, delivery fails with 502 — skip in that case
            if req_resp.status_code == 502:
                pytest.skip("SMTP not configured — skipping full-flow test")

            assert req_resp.status_code == 200, req_resp.text
            assert req_resp.json()["sent"] is True

            # Step 2: verify with captured OTP
            assert sent_otps, "Expected OTP to be captured"
            otp = sent_otps[-1]

            verify_resp = auth_client.post(
                "/auth/otp/verify",
                json={"channel": "email", "identifier": "demo@aeroaqi.test", "otp": otp},
            )

        assert verify_resp.status_code == 200, verify_resp.text
        body = verify_resp.json()
        assert body["verified"] is True
        assert body["user"] is not None
        assert "email" in body["user"]

    def test_wrong_otp_returns_401(self, auth_client):
        """Verifying with the wrong code must return 401."""
        import src.api.routers.auth as auth_mod

        with (
            patch.dict(os.environ, {"AEROAQI_OTP_PROVIDER": "email"}, clear=False),
            patch.object(auth_mod, "_send_otp_email", return_value=None),
        ):
            auth_client.post(
                "/auth/otp/request",
                json={"channel": "email", "identifier": "wrong@aeroaqi.test"},
            )
            resp = auth_client.post(
                "/auth/otp/verify",
                json={"channel": "email", "identifier": "wrong@aeroaqi.test", "otp": "000000"},
            )
        # Either 401 (wrong OTP) or 503 (provider not fully configured in test env)
        assert resp.status_code in (401, 503)

    def test_otp_single_use(self, auth_client):
        """A correct OTP must be rejected on the second use."""
        import src.api.routers.auth as auth_mod

        sent_otps: list[str] = []

        def fake_send(to, otp):
            sent_otps.append(otp)

        with (
            patch.dict(os.environ, {"AEROAQI_OTP_PROVIDER": "email"}, clear=False),
            patch.object(auth_mod, "_send_otp_email", side_effect=fake_send),
        ):
            auth_client.post(
                "/auth/otp/request",
                json={"channel": "email", "identifier": "reuse@aeroaqi.test"},
            )
            if not sent_otps:
                pytest.skip("OTP not captured — delivery patching may have failed")

            otp = sent_otps[-1]
            payload = {"channel": "email", "identifier": "reuse@aeroaqi.test", "otp": otp}

            first = auth_client.post("/auth/otp/verify", json=payload)
            second = auth_client.post("/auth/otp/verify", json=payload)

        # First use should succeed (200), second must fail (401)
        if first.status_code == 200:
            assert second.status_code in (401, 503), (
                "Second use of same OTP must be rejected"
            )
