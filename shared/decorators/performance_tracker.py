"""
Reusable performance-tracking decorators for agent skills and reasoners.

Usage:
    @app.skill()
    @track_performance("enrich_ticket")
    async def enrich_ticket(arguments: Dict) -> Dict:
        ...

    @app.reasoner()
    @track_slow_operation("generate_plan", warn_seconds=10.0, critical_seconds=30.0)
    async def generate_resolution_plan(arguments: Dict) -> Dict:
        ...
"""
import asyncio
import time
from functools import wraps
from typing import Any, Callable, Optional


def track_performance(
    operation_name: str,
    notify: bool = True,
    warn_threshold_seconds: Optional[float] = None,
    critical_threshold_seconds: Optional[float] = None,
):
    """
    Decorator that prints execution time for a skill or reasoner.

    Args:
        operation_name:             Label used in log output.
        notify:                     Print timing to the terminal (default True).
        warn_threshold_seconds:     Print a WARNING if execution exceeds this.
        critical_threshold_seconds: Print a CRITICAL if execution exceeds this.
    """
    def decorator(func: Callable) -> Callable:

        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            start = time.perf_counter()
            success = False
            try:
                result = await func(*args, **kwargs)
                success = True
                return result
            except Exception:
                raise
            finally:
                duration = time.perf_counter() - start
                if notify:
                    _log_timing(operation_name, duration, success,
                                warn_threshold_seconds, critical_threshold_seconds)

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            start = time.perf_counter()
            success = False
            try:
                result = func(*args, **kwargs)
                success = True
                return result
            except Exception:
                raise
            finally:
                duration = time.perf_counter() - start
                if notify:
                    _log_timing(operation_name, duration, success,
                                warn_threshold_seconds, critical_threshold_seconds)

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


def _log_timing(
    operation_name: str,
    duration: float,
    success: bool,
    warn_threshold: Optional[float],
    critical_threshold: Optional[float],
) -> None:
    status = "OK" if success else "FAILED"
    ms = duration * 1000

    if critical_threshold and duration > critical_threshold:
        level = "CRITICAL"
    elif warn_threshold and duration > warn_threshold:
        level = "WARN"
    else:
        level = "INFO"

    msg = f"[PERF][{level}][{operation_name}] {status} in {duration:.3f}s ({ms:.0f}ms)"
    if level == "WARN":
        msg += f" — exceeded warn threshold ({warn_threshold}s)"
    elif level == "CRITICAL":
        msg += f" — exceeded critical threshold ({critical_threshold}s)"

    print(msg)


def track_performance_silently(operation_name: str):
    """Track timing without printing — for high-frequency hot paths."""
    return track_performance(operation_name, notify=False)


def track_slow_operation(
    operation_name: str,
    warn_seconds: float = 5.0,
    critical_seconds: float = 10.0,
):
    """Track performance and warn automatically if thresholds are breached.

    Defaults: warn at 5s, critical at 10s — suitable for AI reasoner calls.
    """
    return track_performance(
        operation_name,
        notify=True,
        warn_threshold_seconds=warn_seconds,
        critical_threshold_seconds=critical_seconds,
    )
