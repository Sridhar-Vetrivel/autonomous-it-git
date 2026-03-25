"""
main.py — Entry point for the Autonomous IT Service Management Agent

Starts all 9 agents sequentially (one at a time) in background threads.
Each agent dynamically finds its own free port before starting, so there
is no collision even if common ports (8001-8009) are taken by other projects.

Usage:
    python main.py
"""

import asyncio
import logging
import socket
import sys
import time
import threading

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

SAMPLE_TICKET = {
    "number": "SCTASK0802841",
    "short_description": "VPN Access Required",
    "description": "User needs VPN access for remote work",
    "requested_for": "john.doe@company.com",
    "requested_item": "VPN License",
    "priority": "high",
    "state": "new",
    "assignment_group": "IT Support",
    "opened": "2025-03-18T09:00:00Z",
    "updated": "2025-03-18T09:00:00Z",
    "opened_by": "admin",
}


def find_free_port(start: int = 8001) -> int:
    """Scan ports starting from `start` and return the first one not in use."""
    for port in range(start, 9000):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free port found in range 8001-8999")


def start_agent_in_thread(agent, name: str, port: int) -> threading.Thread:
    """Start a single agent's serve() in a background daemon thread."""
    def _run():
        try:
            agent.serve(port=port)
        except Exception as e:
            logger.error("[STARTUP] %s failed: %s", name, e)

    t = threading.Thread(target=_run, name=name, daemon=True)
    t.start()
    return t


def main() -> None:
    from agents.ingestion_agent import app as ingestion_app, process_incoming_ticket
    from agents.classification_agent import app as classification_app
    from agents.enrichment_agent import app as enrichment_app
    from agents.decision_planning_agent import app as decision_planning_app
    from agents.execution_agent import app as execution_app
    from agents.validation_agent import app as validation_app
    from agents.communication_agent import app as communication_app
    from agents.learning_agent import app as learning_app
    from agents.human_review_agent import app as human_review_app

    agent_defs = [
        (ingestion_app,         "ingestion_agent"),
        (classification_app,    "classification_agent"),
        (enrichment_app,        "enrichment_agent"),
        (decision_planning_app, "decision_planning_agent"),
        (execution_app,         "execution_agent"),
        (validation_app,        "validation_agent"),
        (communication_app,     "communication_agent"),
        (learning_app,          "learning_agent"),
        (human_review_app,      "human_review_agent"),
    ]

    logger.info("Autonomous IT Service Management Agent initialising …")
    print(f"\n{'='*60}")
    print(f"  AUTONOMOUS IT AGENT PIPELINE STARTING")
    print(f"  Launching {len(agent_defs)} agents (sequential, dynamic ports)...")
    print(f"{'='*60}\n")

    # Start agents one by one — each claims its port before the next starts
    next_port = 8001
    for app, name in agent_defs:
        port = find_free_port(start=next_port)
        next_port = port + 1          # next agent starts scanning after this port
        print(f"  [STARTUP] {name} → port {port}")
        start_agent_in_thread(app, name, port)
        time.sleep(1)                 # wait for this agent to bind before scanning next

    logger.info("All agents started. Waiting for gateway registration...")
    time.sleep(2)
    logger.info("Triggering ingestion pipeline...")

    try:
        result = asyncio.run(process_incoming_ticket(SAMPLE_TICKET))
        print(f"\n[MAIN] Pipeline result: {result}")
    except KeyboardInterrupt:
        pass

    # Keep main thread alive so daemon threads (agents) stay running
    print("\n[MAIN] All agents running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down.")
        sys.exit(0)


if __name__ == "__main__":
    main()
