"""
Integration / workflow tests.

These tests mock the AgentField memory and call APIs to verify the
end-to-end data flow through ingestion → normalization without needing
a live control plane.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from schemas.ticket import TicketData, NormalizedTicket
from schemas.classification import ClassificationResult
from schemas.planning import ExecutionStep, ResolutionPlan
from schemas.execution import ExecutionLog, ExecutionStepResult


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_ticket_payload():
    return {
        "number": "SCTASK0802841",
        "short_description": "VPN Access Required",
        "description": "User needs VPN access for remote work from home.",
        "requested_for": "john.doe@company.com",
        "requested_item": "VPN License",
        "priority": "high",
        "state": "new",
        "assignment_group": "IT Support",
        "opened": "2025-03-18T09:00:00Z",
        "updated": "2025-03-18T09:00:00Z",
        "opened_by": "admin",
    }


@pytest.fixture
def sample_normalized_ticket():
    return NormalizedTicket(
        ticket_id="SCTASK0802841",
        title="VPN Access Required",
        description="User needs VPN access for remote work from home.",
        requester_email="john.doe@company.com",
        service_type="vpn",
        priority="high",
        urgency="urgent",
        impact="high",
        received_at=datetime.now(timezone.utc),
        metadata={"servicenow_id": "SCTASK0802841"},
    )


@pytest.fixture
def sample_classification():
    return ClassificationResult(
        ticket_id="SCTASK0802841",
        ticket_type="request",
        category="vpn_access",
        priority="high",
        severity="2",
        confidence_score=0.92,
        reasoning="Clear VPN access request",
        requires_human_review=False,
        suggested_assignment_group="Network & Access",
    )


@pytest.fixture
def sample_plan():
    step = ExecutionStep(
        step_id=1,
        action="Provision VPN licence",
        skill_or_tool="provision_resources",
        parameters={"licence_type": "vpn", "user": "john.doe@company.com"},
        expected_duration_minutes=5,
        required_permissions=["vpn.admin"],
        rollback_instruction="Revoke VPN licence for john.doe@company.com",
    )
    return ResolutionPlan(
        ticket_id="SCTASK0802841",
        plan_id="PLAN-TEST001",
        steps=[step],
        total_estimated_minutes=10,
        risk_level="low",
        risk_description="Standard provisioning — low risk.",
        requires_approval=False,
        rollback_procedure="Revoke all granted licences.",
        success_criteria=["User can connect to corporate VPN"],
    )


# ─── Ingestion pipeline ────────────────────────────────────────────────────────

class TestIngestionPipeline:
    @pytest.mark.asyncio
    async def test_parse_then_normalize(self, sample_ticket_payload):
        from agents.ingestion_agent import batch_ticket_from_servicenow, normalize_ticket_fields

        ticket_dict = await batch_ticket_from_servicenow({"ticket_payload": sample_ticket_payload})
        assert ticket_dict["number"] == "SCTASK0802841"

        normalized = await normalize_ticket_fields({"ticket_data": ticket_dict})
        assert normalized["ticket_id"] == "SCTASK0802841"
        assert normalized["service_type"] == "vpn"
        assert normalized["urgency"] == "urgent"

    @pytest.mark.asyncio
    async def test_full_pipeline_with_mocked_memory(self, sample_ticket_payload):
        """Verify process_incoming_ticket wires up all steps."""
        from agents import ingestion_agent

        mock_memory = MagicMock()
        mock_memory.set = AsyncMock()
        mock_memory.get = AsyncMock(return_value=[])

        mock_call = AsyncMock(return_value={"status": "ok"})

        with (
            patch.object(ingestion_agent.app, "memory", mock_memory),
            patch.object(ingestion_agent.app, "call", mock_call),
        ):
            result = await ingestion_agent.process_incoming_ticket(sample_ticket_payload)

        assert result["status"] == "success"
        assert result["ticket_id"] == "SCTASK0802841"
        assert result["next_step"] == "classification_agent"
        # memory.set should have been called at least twice (current_ticket + history)
        assert mock_memory.set.call_count >= 2
        # app.call should trigger classification
        mock_call.assert_awaited_once_with(
            "classification_agent.classify_ticket_type",
            input={"ticket_id": "SCTASK0802841"},
        )


# ─── Classification routing ────────────────────────────────────────────────────

class TestClassificationRouting:
    @pytest.mark.asyncio
    async def test_high_confidence_routes_to_enrichment(self, sample_normalized_ticket):
        from agents import classification_agent

        mock_memory = MagicMock()
        mock_memory.get = AsyncMock(return_value=sample_normalized_ticket.model_dump(mode="json"))
        mock_memory.set = AsyncMock()

        high_conf_result = ClassificationResult(
            ticket_id="SCTASK0802841",
            ticket_type="request",
            category="vpn_access",
            priority="high",
            severity="2",
            confidence_score=0.95,
            reasoning="Clear request",
            requires_human_review=False,
        )

        mock_call = AsyncMock()

        with (
            patch.object(classification_agent.app, "memory", mock_memory),
            patch.object(classification_agent.app, "call", mock_call),
            patch.object(classification_agent.app, "ai", AsyncMock(return_value=high_conf_result)),
        ):
            result = await classification_agent.classify_ticket_type({"ticket_id": "SCTASK0802841"})

        assert result["requires_human_review"] is False
        mock_call.assert_awaited_once_with(
            "enrichment_agent.enrich_ticket",
            input={"ticket_id": "SCTASK0802841"},
        )

    @pytest.mark.asyncio
    async def test_low_confidence_routes_to_human_review(self, sample_normalized_ticket):
        from agents import classification_agent

        mock_memory = MagicMock()
        mock_memory.get = AsyncMock(return_value=sample_normalized_ticket.model_dump(mode="json"))
        mock_memory.set = AsyncMock()

        low_conf_result = ClassificationResult(
            ticket_id="SCTASK0802841",
            ticket_type="incident",
            category="other",
            priority="medium",
            severity="3",
            confidence_score=0.45,
            reasoning="Ambiguous description",
            requires_human_review=False,
        )

        mock_call = AsyncMock()

        with (
            patch.object(classification_agent.app, "memory", mock_memory),
            patch.object(classification_agent.app, "call", mock_call),
            patch.object(classification_agent.app, "ai", AsyncMock(return_value=low_conf_result)),
        ):
            result = await classification_agent.classify_ticket_type({"ticket_id": "SCTASK0802841"})

        assert result["requires_human_review"] is True
        mock_call.assert_awaited_once_with(
            "human_review_agent.queue_for_review",
            input={"ticket_id": "SCTASK0802841", "stage": "classification"},
        )


# ─── Execution retry logic ────────────────────────────────────────────────────

class TestExecutionRetry:
    @pytest.mark.asyncio
    async def test_step_succeeds_on_first_attempt(self, sample_plan):
        from agents.execution_agent import _run_step_with_retry

        step_dict = sample_plan.steps[0].model_dump()

        with patch(
            "agents.execution_agent._dispatch_step",
            AsyncMock(return_value={"status": "provisioned"}),
        ):
            result = await _run_step_with_retry(step_dict, "EXEC-TEST")

        assert result.status == "success"
        assert result.retry_count == 0

    @pytest.mark.asyncio
    async def test_step_retries_on_transient_error(self, sample_plan):
        from agents.execution_agent import _run_step_with_retry

        step_dict = sample_plan.steps[0].model_dump()
        call_count = {"n": 0}

        async def flaky(*_):
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise ConnectionError("transient")
            return {"status": "ok"}

        with patch("agents.execution_agent._dispatch_step", flaky):
            result = await _run_step_with_retry(step_dict, "EXEC-TEST")

        assert result.status == "success"
        assert result.retry_count == 2

    @pytest.mark.asyncio
    async def test_step_fails_after_max_retries(self, sample_plan):
        from agents.execution_agent import _run_step_with_retry

        step_dict = sample_plan.steps[0].model_dump()

        with patch(
            "agents.execution_agent._dispatch_step",
            AsyncMock(side_effect=RuntimeError("always fails")),
        ):
            result = await _run_step_with_retry(step_dict, "EXEC-TEST")

        assert result.status == "failure"
        assert "always fails" in (result.error_message or "")


# ─── Schema round-trip ────────────────────────────────────────────────────────

class TestSchemaRoundTrip:
    def test_ticket_data_round_trip(self):
        original = TicketData(
            number="SCTASK999",
            short_description="Test ticket",
            requested_for="user@test.com",
            requested_item="Software",
            priority="medium",
            state="new",
            opened="2025-01-01T00:00:00Z",
            updated="2025-01-01T00:00:00Z",
            opened_by="system",
        )
        dumped = original.model_dump()
        restored = TicketData(**dumped)
        assert restored == original

    def test_execution_log_round_trip(self):
        now = datetime.now(timezone.utc)
        step = ExecutionStepResult(
            step_id=1,
            status="success",
            start_time=now,
            end_time=now,
            duration_seconds=1.0,
        )
        log = ExecutionLog(
            ticket_id="X",
            plan_id="P",
            execution_id="E",
            started_at=now,
            overall_status="success",
            step_results=[step],
            total_duration_seconds=1.0,
        )
        restored = ExecutionLog.model_validate(log.model_dump(mode="json"))
        assert restored.ticket_id == "X"
        assert restored.step_results[0].status == "success"
