"""Monitoring and metrics utilities."""
import time
from functools import wraps
from typing import Callable, Any
from app.core.logging import logger
import json
from datetime import datetime


class MetricsCollector:
    """Simple in-memory metrics collector."""
    
    def __init__(self):
        self.metrics = {
            "request_count": 0,
            "error_count": 0,
            "webhook_count": 0,
            "message_count": 0,
            "response_times": []
        }
    
    def increment(self, metric: str, value: int = 1):
        """Increment a counter metric."""
        if metric in self.metrics:
            self.metrics[metric] += value
        else:
            self.metrics[metric] = value
    
    def record_response_time(self, time_ms: float):
        """Record a response time."""
        self.metrics["response_times"].append(time_ms)
        # Keep only last 1000 measurements
        if len(self.metrics["response_times"]) > 1000:
            self.metrics["response_times"] = self.metrics["response_times"][-1000:]
    
    def get_metrics(self) -> dict:
        """Get all metrics."""
        metrics = self.metrics.copy()
        
        # Calculate average response time
        if metrics["response_times"]:
            metrics["avg_response_time_ms"] = sum(metrics["response_times"]) / len(metrics["response_times"])
        else:
            metrics["avg_response_time_ms"] = 0
        
        # Remove raw response times from output
        del metrics["response_times"]
        
        return metrics
    
    def reset(self):
        """Reset all metrics."""
        self.__init__()


# Global metrics collector
_metrics = MetricsCollector()


def get_metrics() -> dict:
    """Get current metrics."""
    return _metrics.get_metrics()


def increment_metric(metric: str, value: int = 1):
    """Increment a metric."""
    _metrics.increment(metric, value)


def record_response_time(time_ms: float):
    """Record response time."""
    _metrics.record_response_time(time_ms)


def track_time(func: Callable) -> Callable:
    """
    Decorator to track function execution time.
    
    Usage:
        @track_time
        async def my_function():
            pass
    """
    @wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            elapsed_ms = (time.time() - start_time) * 1000
            record_response_time(elapsed_ms)
            logger.debug(f"{func.__name__} took {elapsed_ms:.2f}ms")
    
    @wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            elapsed_ms = (time.time() - start_time) * 1000
            record_response_time(elapsed_ms)
            logger.debug(f"{func.__name__} took {elapsed_ms:.2f}ms")
    
    # Return appropriate wrapper based on function type
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


class StructuredLogger:
    """Structured JSON logger for better log parsing."""
    
    @staticmethod
    def log_event(
        event_type: str,
        message: str,
        level: str = "info",
        **extra_fields
    ):
        """
        Log a structured event as JSON.
        
        Args:
            event_type: Type of event (e.g., "webhook_received", "message_sent")
            message: Human-readable message
            level: Log level (debug, info, warning, error)
            **extra_fields: Additional fields to include in log
        """
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "message": message,
            "level": level,
            **extra_fields
        }
        
        log_message = json.dumps(log_data)
        
        if level == "debug":
            logger.debug(log_message)
        elif level == "info":
            logger.info(log_message)
        elif level == "warning":
            logger.warning(log_message)
        elif level == "error":
            logger.error(log_message)
        else:
            logger.info(log_message)


# Global structured logger
structured_logger = StructuredLogger()

