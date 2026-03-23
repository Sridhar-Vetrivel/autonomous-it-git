"""
Unit tests for individual agent skills that contain pure logic
(no AgentField SDK calls, no memory, no AI).
"""

import pytest
from datetime import datetime, timezone

# Import the helper functions directly (not through the agent app object)
from agents.ingestion_agent import (
    _categorize_service_type,
    batch_ticket_from_servicenow,
    normalize_ticket_fields,
    extract_attachments,
)
from skills.utils import truncate, mask_sensitive


# ── _categorize_service_type ──────────────────────────────────────────────────

class TestCategorizeServiceType:
    @pytest.mark.parametrize(
        "item,expected",
        [
            ("VPN License", "vpn"),
            ("corporate vpn access", "vpn"),
            ("Microsoft Office License", "software"),
            ("Dell Laptop", "hardware"),
            ("Admin Permission Grant", "access"),
            ("Desk booking", "general"),
        ],
    )
    def test_mapping(self, item, expected):
        assert _categorize_service_type(item) == expected


# ── batch_ticket_from_servicenow (pure parsing, no SDK) ───────────────────────

class TestBatchTicketFromServiceNow:
    """
    The skill itself imports `app` from agentfield, but the parsing logic
    is deterministic. We test it by calling the inner function directly.
    """

    def _minimal_payload(self, **overrides):
        base = {
            "number": "SCTASK001",
            "short_description": "VPN access",
            "requested_for": "a@b.com",
            "requested_item": "VPN",
            "priority": "high",
            "state": "new",
            "opened": "2025-01-01T00:00:00Z",
            "updated": "2025-01-01T00:00:00Z",
            "opened_by": "admin",
        }
        base.update(overrides)
        return base

    @pytest.mark.asyncio
    async def test_valid_payload_returns_dict(self):
        result = await batch_ticket_from_servicenow(
            {"ticket_payload": self._minimal_payload()}
        )
        assert result["number"] == "SCTASK001"
        assert result["priority"] == "high"

    @pytest.mark.asyncio
    async def test_missing_required_field_raises(self):
        payload = self._minimal_payload()
        del payload["number"]
        with pytest.raises((ValueError, KeyError)):
            await batch_ticket_from_servicenow({"ticket_payload": payload})

    @pytest.mark.asyncio
    async def test_attachments_default_to_empty(self):
        result = await batch_ticket_from_servicenow(
            {"ticket_payload": self._minimal_payload()}
        )
        assert result["attachments"] == []

    @pytest.mark.asyncio
    async def test_invalid_priority_raises(self):
        with pytest.raises(Exception):
            await batch_ticket_from_servicenow(
                {"ticket_payload": self._minimal_payload(priority="super_urgent")}
            )


# ── normalize_ticket_fields ───────────────────────────────────────────────────

class TestNormalizeTicketFields:
    def _ticket_dict(self, **overrides):
        base = {
            "number": "SCTASK001",
            "short_description": "VPN access",
            "description": "Needs VPN",
            "requested_for": "a@b.com",
            "requested_item": "VPN",
            "priority": "high",
            "state": "new",
            "opened": "2025-01-01T00:00:00Z",
            "updated": "2025-01-01T00:00:00Z",
            "opened_by": "admin",
        }
        base.update(overrides)
        return base

    @pytest.mark.asyncio
    async def test_high_priority_urgency(self):
        result = await normalize_ticket_fields({"ticket_data": self._ticket_dict()})
        assert result["urgency"] == "urgent"
        assert result["impact"] == "high"

    @pytest.mark.asyncio
    async def test_low_priority_urgency(self):
        result = await normalize_ticket_fields(
            {"ticket_data": self._ticket_dict(priority="low")}
        )
        assert result["urgency"] == "low"
        assert result["impact"] == "low"

    @pytest.mark.asyncio
    async def test_service_type_vpn(self):
        result = await normalize_ticket_fields(
            {"ticket_data": self._ticket_dict(requested_item="VPN License")}
        )
        assert result["service_type"] == "vpn"

    @pytest.mark.asyncio
    async def test_ticket_id_mapped(self):
        result = await normalize_ticket_fields({"ticket_data": self._ticket_dict()})
        assert result["ticket_id"] == "SCTASK001"


# ── extract_attachments ───────────────────────────────────────────────────────

class TestExtractAttachments:
    @pytest.mark.asyncio
    async def test_no_attachments(self):
        result = await extract_attachments(
            {"ticket_data": {"number": "X", "attachments": []}}
        )
        assert result["attachment_count"] == 0

    @pytest.mark.asyncio
    async def test_with_attachments(self):
        urls = ["http://example.com/file1.pdf", "http://example.com/file2.png"]
        result = await extract_attachments(
            {"ticket_data": {"number": "X", "attachments": urls}}
        )
        assert result["attachment_count"] == 2
        assert result["attachments"] == urls


# ── Utility functions ─────────────────────────────────────────────────────────

class TestUtils:
    def test_truncate_short(self):
        assert truncate("hello", 100) == "hello"

    def test_truncate_long(self):
        result = truncate("a" * 200, 50)
        assert len(result) == 50
        assert result.endswith("…")

    def test_mask_sensitive(self):
        data = {"username": "alice", "api_key": "supersecret", "token": "abc123"}
        masked = mask_sensitive(data)
        assert masked["username"] == "alice"
        assert masked["api_key"] == "***"
        assert masked["token"] == "***"
