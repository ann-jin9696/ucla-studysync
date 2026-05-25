from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def disable_resend_delivery(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
