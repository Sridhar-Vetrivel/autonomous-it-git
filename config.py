import os
from dotenv import load_dotenv

load_dotenv(override=True)


class Config:
    # AgentField
    AGENTFIELD_SERVER = os.getenv("AGENTFIELD_SERVER", "http://localhost:8080")
    AI_MODEL = os.getenv("AI_MODEL", "openai/gpt-4o")

    # ServiceNow
    SERVICENOW_INSTANCE = os.getenv("SERVICENOW_INSTANCE")
    SERVICENOW_API_KEY = os.getenv("SERVICENOW_API_KEY")
    SERVICENOW_TABLE = os.getenv("SERVICENOW_TABLE", "sc_task")

    # Integration
    KNOWLEDGE_BASE_URL = os.getenv("KNOWLEDGE_BASE_URL")
    NOTIFICATION_WEBHOOK_URL = os.getenv("NOTIFICATION_WEBHOOK_URL")

    # Execution
    RETRY_ATTEMPTS = int(os.getenv("RETRY_ATTEMPTS", 3))
    TIMEOUT_SECONDS = int(os.getenv("TIMEOUT_SECONDS", 300))
    HUMAN_REVIEW_QUEUE_URL = os.getenv("HUMAN_REVIEW_QUEUE_URL")

    # Thresholds
    CLASSIFICATION_CONFIDENCE_THRESHOLD = float(
        os.getenv("CLASSIFICATION_CONFIDENCE_THRESHOLD", 0.7)
    )
    RISK_ESCALATION_THRESHOLD = float(
        os.getenv("RISK_ESCALATION_THRESHOLD", 0.6)
    )
    MAX_EXECUTION_RETRIES = 3
    VECTOR_SIMILARITY_TOP_K = 5
