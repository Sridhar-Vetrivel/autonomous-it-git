"""
main.py — Entry point for the Autonomous IT Service Management Agent

Starts all 9 agents and exposes a simple HTTP health endpoint.
Each agent connects to the AgentField control plane independently;
the pipeline is driven by agent-to-agent calls, not by this process.

Usage:
    python main.py
"""

import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


async def start_all_agents() -> None:
    """Import and start every agent runtime in parallel."""
    from agents.ingestion_agent import app as ingestion_app
    from agents.classification_agent import app as classification_app
    from agents.enrichment_agent import app as enrichment_app
    from agents.decision_planning_agent import app as decision_planning_app
    from agents.execution_agent import app as execution_app
    from agents.validation_agent import app as validation_app
    from agents.communication_agent import app as communication_app
    from agents.learning_agent import app as learning_app
    from agents.human_review_agent import app as human_review_app

    agents = [
        ingestion_app,
        classification_app,
        enrichment_app,
        decision_planning_app,
        execution_app,
        validation_app,
        communication_app,
        learning_app,
        human_review_app,
    ]

    logger.info("Starting %d agents …", len(agents))
    print(f"\n{'='*60}")
    print(f"  AUTONOMOUS IT AGENT PIPELINE STARTING")
    print(f"  Launching {len(agents)} agents...")
    agent_names = [
        "ingestion_agent", "classification_agent", "enrichment_agent",
        "decision_planning_agent", "execution_agent", "validation_agent",
        "communication_agent", "learning_agent", "human_review_agent",
    ]
    for name in agent_names:
        print(f"  [STARTUP] Registering: {name}")
    print(f"{'='*60}\n")

    # Each AgentField app exposes a .start() coroutine that blocks while
    # listening for work from the control plane.
    await asyncio.gather(*[a.start() for a in agents])


def main() -> None:
    logger.info("Autonomous IT Service Management Agent initialising …")

    try:
        asyncio.run(start_all_agents())
    except KeyboardInterrupt:
        logger.info("Shutting down.")
        sys.exit(0)


if __name__ == "__main__":
    main()
