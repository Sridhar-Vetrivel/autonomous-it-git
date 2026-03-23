"""
Unit tests for Pydantic schemas — pure validation, no I/O.
"""

import pytest
from datetime import datetime, timezone

from schemas.ticket import TicketData, NormalizedTicket
from schemas.classification import ClassificationResult
from schemas.enrichment import UserProfile, RelatedTicket, EnrichmentResult
from schemas.planning import ExecutionStep, ResolutionPlan
from schemas.execution import ExecutionStepResult, ExecutionLog, ValidationResult


# ── TicketData ────────────────────────────────────────────────────────────────

class TestTicketData:
    def _valid_payload(self, **overrides):
        base = {
            "number": "SCTASK0802841",
            "short_description": "VPN Access Required",
            "description": "User needs VPN access for remote work",
            "requested_for": "john.doe@company.com",
            "requested_item": "VPN License",
            "priority": "high",
            "state": "new",
            "opened": "2025-03-18T09:00:00Z",
            "updated": "2025-03-18T09:00:00Z",
            "opened_by": "admin",
        }
        base.update(overrides)
        return base

    def test_valid_ticket(self):
        ticket = TicketData(**self._valid_payload())
        assert ticket.number == "SCTASK0802841"
        assert ticket.priority == "high"

    def test_invalid_priority_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            TicketData(**self._valid_payload(priority="urgent"))

    def test_optional_fields_default(self):
        ticket = TicketData(**self._valid_payload())
        assert ticket.attachments == []
        assert ticket.assignment_group is None

    def test_extra_fields_forbidden(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            TicketData(**self._valid_payload(unknown_field="x"))


# ── NormalizedTicket ──────────────────────────────────────────────────────────

class TestNormalizedTicket:
    def test_valid(self):
        ticket = NormalizedTicket(
            ticket_id="SCTASK001",
            title="VPN Access",
            description="Need VPN",
            requester_email="a@b.com",
            service_type="vpn",
            priority="high",
            urgency="urgent",
            impact="high",
            received_at=datetime.now(timezone.utc),
        )
        assert ticket.service_type == "vpn"

    def test_invalid_priority(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            NormalizedTicket(
                ticket_id="X",
                title="T",
                description="D",
                requester_email="e@f.com",
                service_type="general",
                priority="very_high",
                urgency="urgent",
                impact="high",
                received_at=datetime.now(timezone.utc),
            )


# ── ClassificationResult ──────────────────────────────────────────────────────

class TestClassificationResult:
    def _valid(self, **kw):
        base = {
            "ticket_id": "SCTASK001",
            "ticket_type": "request",
            "category": "vpn_access",
            "priority": "high",
            "severity": "2",
            "confidence_score": 0.92,
            "reasoning": "Clear VPN request",
            "requires_human_review": False,
        }
        base.update(kw)
        return base

    def test_valid(self):
        r = ClassificationResult(**self._valid())
        assert r.confidence_score == 0.92

    def test_confidence_out_of_range(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ClassificationResult(**self._valid(confidence_score=1.5))

    def test_invalid_severity(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ClassificationResult(**self._valid(severity="5"))


# ── ResolutionPlan ────────────────────────────────────────────────────────────

class TestResolutionPlan:
    def _valid_step(self, step_id=1):
        return {
            "step_id": step_id,
            "action": "Grant VPN licence",
            "skill_or_tool": "provision_resources",
            "parameters": {"licence_type": "vpn"},
            "expected_duration_minutes": 5,
        }

    def test_valid_plan(self):
        plan = ResolutionPlan(
            ticket_id="SCTASK001",
            plan_id="PLAN-ABC123",
            steps=[ExecutionStep(**self._valid_step())],
            total_estimated_minutes=10,
            risk_level="low",
            risk_description="Standard access provisioning",
            requires_approval=False,
            rollback_procedure="Revoke licence",
            success_criteria=["User can connect to VPN"],
        )
        assert plan.risk_level == "low"
        assert len(plan.steps) == 1

    def test_invalid_risk_level(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ResolutionPlan(
                ticket_id="X",
                plan_id="P",
                steps=[],
                total_estimated_minutes=5,
                risk_level="extreme",
                risk_description="",
                requires_approval=False,
                rollback_procedure="",
                success_criteria=[],
            )


# ── ExecutionLog ──────────────────────────────────────────────────────────────

class TestExecutionLog:
    def test_valid_log(self):
        now = datetime.now(timezone.utc)
        step = ExecutionStepResult(
            step_id=1,
            status="success",
            start_time=now,
            end_time=now,
            duration_seconds=2.5,
        )
        log = ExecutionLog(
            ticket_id="SCTASK001",
            plan_id="PLAN-ABC",
            execution_id="EXEC-001",
            started_at=now,
            overall_status="success",
            step_results=[step],
            total_duration_seconds=2.5,
        )
        assert log.overall_status == "success"
        assert log.rollback_performed is False

    def test_invalid_status(self):
        from pydantic import ValidationError
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError):
            ExecutionLog(
                ticket_id="X",
                plan_id="P",
                execution_id="E",
                started_at=now,
                overall_status="unknown_status",
                step_results=[],
                total_duration_seconds=0,
            )


# ── ValidationResult ──────────────────────────────────────────────────────────

class TestValidationResult:
    def test_valid(self):
        result = ValidationResult(
            ticket_id="SCTASK001",
            execution_id="EXEC-001",
            all_checks_passed=True,
            recommended_action="close",
        )
        assert result.recommended_action == "close"

    def test_invalid_action(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ValidationResult(
                ticket_id="X",
                execution_id="E",
                all_checks_passed=False,
                recommended_action="delete",
            )
