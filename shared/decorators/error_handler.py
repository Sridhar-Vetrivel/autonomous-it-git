"""
Reusable error-handling decorators for agent skills and reasoners.

Usage:
    @app.skill()
    @handle_errors("fetch_data")
    async def fetch_data(arguments: Dict) -> Dict:
        ...

    @app.reasoner()
    @handle_errors("analyze", raise_on_error=False)
    async def analyze(arguments: Dict) -> Dict:
        ...
"""
import asyncio
import traceback
from functools import wraps
from typing import Any, Callable

from shared.exceptions.agent_exceptions import (
    AgentCommunicationError,
    AgentError,
    AgentProcessingError,
    AgentTimeoutError,
    ValidationError,
)


def handle_errors(operation_name: str, notify: bool = True, raise_on_error: bool = True):
    """
    Decorator for consistent error handling across all skills and reasoners.

    Args:
        operation_name: Name used in log output.
        notify:         Print error details to the terminal (default True).
        raise_on_error: Re-raise the exception after logging (default True).
                        Set False for non-critical operations where returning
                        None on failure is acceptable.
    """
    def decorator(func: Callable) -> Callable:

        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            try:
                return await func(*args, **kwargs)

            except AgentCommunicationError as e:
                if notify:
                    print(f"[ERROR][{operation_name}] Communication error: {e}")
                if raise_on_error:
                    raise
                return None

            except AgentTimeoutError as e:
                if notify:
                    print(f"[ERROR][{operation_name}] Timeout: {e}")
                if raise_on_error:
                    raise
                return None

            except ValidationError as e:
                if notify:
                    print(f"[ERROR][{operation_name}] Validation error: {e}")
                if raise_on_error:
                    raise
                return None

            except AgentError as e:
                if notify:
                    print(f"[ERROR][{operation_name}] Agent error ({type(e).__name__}): {e}")
                if raise_on_error:
                    raise
                return None

            except asyncio.TimeoutError as e:
                if notify:
                    print(f"[ERROR][{operation_name}] Async timeout")
                if raise_on_error:
                    raise AgentTimeoutError(f"Timeout in {operation_name}") from e
                return None

            except Exception as e:
                if notify:
                    print(
                        f"[ERROR][{operation_name}] Unexpected {type(e).__name__}: {e}\n"
                        f"{traceback.format_exc()}"
                    )
                if raise_on_error:
                    raise AgentProcessingError(
                        f"Unexpected error in {operation_name}: {e}"
                    ) from e
                return None

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)

            except AgentError as e:
                if notify:
                    print(f"[ERROR][{operation_name}] Agent error ({type(e).__name__}): {e}")
                if raise_on_error:
                    raise
                return None

            except ValidationError as e:
                if notify:
                    print(f"[ERROR][{operation_name}] Validation error: {e}")
                if raise_on_error:
                    raise
                return None

            except Exception as e:
                if notify:
                    print(
                        f"[ERROR][{operation_name}] Unexpected {type(e).__name__}: {e}\n"
                        f"{traceback.format_exc()}"
                    )
                if raise_on_error:
                    raise AgentProcessingError(
                        f"Unexpected error in {operation_name}: {e}"
                    ) from e
                return None

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


def handle_errors_silently(operation_name: str):
    """Handle errors without re-raising — returns None on failure.

    Use for non-critical operations where a missing result is acceptable
    (e.g. optional enrichment lookups).
    """
    return handle_errors(operation_name, notify=True, raise_on_error=False)


def handle_errors_without_notification(operation_name: str):
    """Re-raise errors without printing — avoids log spam on hot paths."""
    return handle_errors(operation_name, notify=False, raise_on_error=True)
