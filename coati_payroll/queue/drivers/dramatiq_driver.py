# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Dramatiq driver for high-performance queue processing with Redis."""

from __future__ import annotations

from typing import Any, Callable, cast

from coati_payroll.log import log
from coati_payroll.queue.driver import QueueDriver

# Error messages
ERROR_DRAMATIQ_NOT_AVAILABLE = "Dramatiq driver not available"

try:
    import threading
    import dramatiq

    class FlaskAPPContextMiddleware(dramatiq.Middleware):
        """Dramatiq middleware that manages the Flask application context for each task.

        This ensures that when tasks are executed in background threads, they
        have access to the Flask app context and `db.session` works correctly.
        """

        def __init__(self):
            super().__init__()
            self._local = threading.local()
            self._app = None

        def _get_app(self):
            if self._app is None:
                try:
                    import importlib

                    module = importlib.import_module("coati_payroll")
                    create_app = module.create_app
                    from coati_payroll.config import configuration

                    # Create the Flask application instance once.
                    self._app = create_app(dict(configuration))
                except Exception as e:
                    log.error("Failed to create Flask app inside Dramatiq middleware: %s", e)
                    raise
            return self._app

        def before_process_message(self, broker, message):
            app = self._get_app()
            if app is not None:
                ctx = app.app_context()
                ctx.push()
                self._local.ctx = ctx

        def after_process_message(self, broker, message, *, result=None, exception=None):
            ctx = getattr(self._local, "ctx", None)
            if ctx is not None:
                ctx.pop()
                self._local.ctx = None

        def after_skip_message(self, broker, message):
            ctx = getattr(self._local, "ctx", None)
            if ctx is not None:
                ctx.pop()
                self._local.ctx = None

except ImportError:
    # Fallback/stub for environments where dramatiq is not installed or mocked
    class FlaskAPPContextMiddleware:  # type: ignore
        pass


class DramatiqDriver(QueueDriver):
    """Queue driver using Dramatiq with Redis backend.

    This driver provides high-performance, distributed job processing
    suitable for production environments with Redis available.

    Features:
    - Multi-threaded workers
    - Automatic retries with exponential backoff
    - Distributed processing across multiple workers
    - Results backend (optional)
    """

    def __init__(self, redis_url: str | None = None):
        """Initialize Dramatiq driver.

        Args:
            redis_url: Redis connection URL (default: redis://localhost:6379/0)
        """
        self._redis_url = redis_url or "redis://localhost:6379/0"
        self._broker: Any | None = None
        self._tasks: dict[str, Any] = {}
        self._results_backend: Any | None = None
        self._available = self._initialize_broker()

    def _initialize_broker(self) -> bool:
        """Initialize the Dramatiq broker.

        Returns:
            True if broker initialized successfully, False otherwise
        """
        try:
            import dramatiq
            from dramatiq.brokers.redis import RedisBroker
            from dramatiq.middleware import AgeLimit, Retries, TimeLimit
            import dramatiq.middleware as dramatiq_middleware
            import dramatiq.results as dramatiq_results

            # Test Redis connection
            import redis

            client = redis.from_url(self._redis_url, socket_connect_timeout=2)
            client.ping()

            # Configure broker with middleware
            self._broker = RedisBroker(url=self._redis_url)
            broker = self._broker

            # RedisBroker already ships with the standard middleware. Add the
            # configured instances only when they are not present, otherwise
            # Dramatiq applies retries/time limits twice.
            existing_middleware_types = {type(middleware) for middleware in broker.middleware}
            for middleware in (
                Retries(max_retries=3, min_backoff=15000, max_backoff=86400000),
                TimeLimit(time_limit=3600000),  # 1 hour max
                AgeLimit(max_age=86400000),  # 24 hours max age
            ):
                if type(middleware) not in existing_middleware_types:
                    broker.add_middleware(middleware)
            broker.add_middleware(FlaskAPPContextMiddleware())

            results_cls = cast(Any, getattr(dramatiq_middleware, "Results", None))
            redis_backend_cls = cast(Any, getattr(dramatiq_results, "RedisBackend", None))
            if callable(results_cls) and callable(redis_backend_cls):
                backend_cls = cast(Any, redis_backend_cls)
                middleware_cls = cast(Any, results_cls)
                # Dynamically loaded classes validated as callable above.
                # pylint: disable=not-callable
                self._results_backend = backend_cls(url=self._redis_url)
                broker.add_middleware(middleware_cls(backend=self._results_backend))

            # Set as default broker
            dramatiq.set_broker(cast(Any, broker))

            log.info("Dramatiq driver initialized with Redis at %s", self._redis_url)
            return True

        except ImportError as e:
            log.warning("Dramatiq not available: %s", e)
            return False
        except Exception as e:
            log.warning("Failed to connect to Redis for Dramatiq: %s", e)
            return False

    def enqueue(self, task_name: str, *args: Any, delay: int | None = None, **kwargs: Any) -> Any:
        """Enqueue a task for background processing.

        Args:
            task_name: Name of the registered task
            *args: Positional arguments for the task
            delay: Optional delay in seconds before execution
            **kwargs: Keyword arguments for the task

        Returns:
            Dramatiq message object

        Raises:
            ValueError: If task is not registered
            RuntimeError: If driver is not available
        """
        if not self._available:
            raise RuntimeError("Dramatiq driver is not available")

        if task_name not in self._tasks:
            raise ValueError(f"Task '{task_name}' not registered")

        task = self._tasks[task_name]

        if delay:
            # Convert seconds to milliseconds for Dramatiq
            return task.send_with_options(args=args, kwargs=kwargs, delay=delay * 1000)
        return task.send(*args, **kwargs)

    def register_task(
        self,
        func: Callable,
        name: str | None = None,
        max_retries: int = 3,
        min_backoff: int = 15000,
        max_backoff: int = 86400000,
    ) -> Callable:
        """Register a function as a Dramatiq actor.

        Args:
            func: Function to register
            name: Optional task name (defaults to function name)
            max_retries: Maximum retry attempts
            min_backoff: Minimum backoff in milliseconds
            max_backoff: Maximum backoff in milliseconds

        Returns:
            Dramatiq actor that can be called or enqueued
        """
        if not self._available:
            log.warning("Cannot register task '%s': Dramatiq not available", name or func.__name__)
            return func

        try:
            import dramatiq

            task_name = name or func.__name__

            # Decorate with dramatiq.actor
            actor_decorator = dramatiq.actor(
                actor_name=task_name,
                max_retries=max_retries,
                min_backoff=min_backoff,
                max_backoff=max_backoff,
            )
            actor = actor_decorator(func)

            self._tasks[task_name] = actor
            log.debug("Registered Dramatiq task: %s", task_name)

            return actor

        except Exception as e:
            log.error("Failed to register task '%s': %s", name or func.__name__, e)
            return func

    def is_available(self) -> bool:
        """Check if Dramatiq driver is available.

        Returns:
            True if driver initialized successfully
        """
        return self._available

    def get_stats(self) -> dict[str, Any]:
        """Get queue statistics from Redis.

        Returns:
            Dictionary with queue statistics
        """
        if not self._available or not self._broker:
            return {"error": ERROR_DRAMATIQ_NOT_AVAILABLE}

        try:
            import redis

            client = redis.from_url(self._redis_url)

            # Get basic stats from Redis
            stats: dict[str, Any] = {
                "driver": "dramatiq",
                "backend": "redis",
                "available": True,
                "registered_tasks": list(self._tasks.keys()),
            }

            # Try to get queue lengths
            try:
                keys = cast(list[bytes], client.keys("dramatiq:*:msgs"))
                stats["queues"] = {}
                for key in keys:
                    queue_name = key.decode("utf-8").split(":")[1]
                    length = client.llen(key)
                    stats["queues"][queue_name] = length
            except Exception as e:
                log.debug("Could not fetch queue lengths: %s", e)

            return stats

        except Exception as e:
            log.error("Failed to get Dramatiq stats: %s", e)
            return {"error": str(e)}

    def get_task_result(self, task_id: Any) -> dict[str, Any]:
        """Get the result of a task by its ID.

        Note: Dramatiq doesn't have built-in result storage by default.
        This returns limited information based on message ID.

        Args:
            task_id: Dramatiq message object

        Returns:
            Dictionary with task status (limited in Dramatiq without results backend)
        """
        if not self._available:
            return {"status": "error", "error": ERROR_DRAMATIQ_NOT_AVAILABLE}

        try:
            if not self._results_backend:
                return {
                    "status": "pending",
                    "message": "Dramatiq task enqueued. Result tracking requires Results middleware.",
                    "task_id": str(task_id) if task_id else None,
                }

            try:
                result = self._results_backend.get_result(task_id, block=False)
                return {
                    "status": "completed",
                    "result": result,
                    "task_id": str(task_id) if task_id else None,
                }
            except Exception as e:
                error_name = type(e).__name__
                if error_name in {"ResultMissing", "ResultTimeout"}:
                    return {
                        "status": "pending",
                        "message": "Task is still processing",
                        "task_id": str(task_id) if task_id else None,
                    }
                raise
        except Exception as e:
            log.error("Failed to get task result: %s", e)
            return {"status": "error", "error": str(e)}

    def get_bulk_results(self, task_ids: list[Any]) -> dict[str, Any]:
        """Get results for multiple tasks (for bulk feedback: x of y completed).

        Note: Without Results middleware, Dramatiq cannot track task completion.
        This returns estimated status based on queue inspection.

        Args:
            task_ids: List of Dramatiq message objects

        Returns:
            Dictionary with aggregated status (limited without Results backend)
        """
        if not self._available:
            return {"error": ERROR_DRAMATIQ_NOT_AVAILABLE}

        total = len(task_ids)

        completed = 0
        failed = 0
        pending = 0
        tasks = {}

        for index, task_id in enumerate(task_ids):
            result_info = self.get_task_result(task_id)
            status = result_info.get("status", "unknown")
            tasks[f"task_{index}"] = result_info
            if status == "completed":
                completed += 1
            elif status in {"error", "failed"}:
                failed += 1
            else:
                pending += 1

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "processing": 0,
            "tasks": tasks,
            "progress_percentage": round((completed / total * 100) if total > 0 else 0, 2),
        }
