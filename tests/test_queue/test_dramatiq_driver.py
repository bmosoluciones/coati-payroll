from __future__ import annotations

import builtins
import importlib.util
import pathlib
import sys
import types
import unittest
from typing import Any
from unittest.mock import MagicMock, patch


class DummyLogger:
    def debug(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def info(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def warning(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def error(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class DummyRedisClient:
    def __init__(self, ping_error: Exception | None = None):
        self._ping_error = ping_error
        self._keys: list[bytes] = [b"dramatiq:default:msgs"]
        self.raise_keys = False

    def ping(self) -> bool:
        if self._ping_error:
            raise self._ping_error
        return True

    def keys(self, _pattern: str) -> list[bytes]:
        if self.raise_keys:
            raise RuntimeError("boom")
        return self._keys

    def llen(self, _key: bytes) -> int:
        return 3


class DummyBroker:
    def __init__(self, url: str):
        self.url = url
        self.middlewares: list[Any] = []

    def add_middleware(self, middleware: Any) -> None:
        self.middlewares.append(middleware)


class DummyActor:
    def send(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"mode": "send", "args": args, "kwargs": kwargs}

    def send_with_options(self, *, args: Any, kwargs: Any, delay: int) -> dict[str, Any]:
        return {"mode": "send_with_options", "args": args, "kwargs": kwargs, "delay": delay}


class DummyResultsBackend:
    def __init__(self, url: str):
        self.url = url
        self.to_raise: Exception | None = None
        self.value: Any = "done"

    def get_result(self, task_id: Any, block: bool = False) -> Any:  # noqa: FBT002
        if self.to_raise:
            raise self.to_raise
        return {"task_id": task_id, "block": block, "value": self.value}


class DramatiqDriverTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.original_modules = dict(sys.modules)
        cls._install_minimal_coati_stubs()
        cls.dramatiq_driver = cls._load_target_module()
        cls.DramatiqDriver = cls.dramatiq_driver.DramatiqDriver

    @classmethod
    def tearDownClass(cls) -> None:
        sys.modules.clear()
        sys.modules.update(cls.original_modules)

    @classmethod
    def _install_minimal_coati_stubs(cls) -> None:
        coati_pkg = types.ModuleType("coati_payroll")
        coati_pkg.__path__ = []  # type: ignore[attr-defined]
        queue_pkg = types.ModuleType("coati_payroll.queue")
        queue_pkg.__path__ = []  # type: ignore[attr-defined]

        driver_module = types.ModuleType("coati_payroll.queue.driver")

        class QueueDriver:  # pylint: disable=too-few-public-methods
            pass

        driver_module.QueueDriver = QueueDriver  # type: ignore[attr-defined]

        log_module = types.ModuleType("coati_payroll.log")
        log_module.log = DummyLogger()  # type: ignore[attr-defined]

        sys.modules["coati_payroll"] = coati_pkg
        sys.modules["coati_payroll.queue"] = queue_pkg
        sys.modules["coati_payroll.queue.driver"] = driver_module
        sys.modules["coati_payroll.log"] = log_module

    @classmethod
    def _load_target_module(cls):
        root = pathlib.Path(__file__).resolve().parents[2]
        module_path = root / "coati_payroll" / "queue" / "drivers" / "dramatiq_driver.py"
        spec = importlib.util.spec_from_file_location(
            "coati_payroll.queue.drivers.dramatiq_driver",
            module_path,
        )
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def setUp(self) -> None:
        self.clean_modules = dict(sys.modules)

    def tearDown(self) -> None:
        sys.modules.clear()
        sys.modules.update(self.clean_modules)

    def install_fake_modules(self, ping_error: Exception | None = None) -> dict[str, Any]:
        set_broker_calls: list[Any] = []

        dramatiq_mod = types.ModuleType("dramatiq")

        def actor(**opts: Any):
            def decorator(func: Any):
                return {"func": func, "opts": opts}

            return decorator

        def set_broker(broker: Any) -> None:
            set_broker_calls.append(broker)

        dramatiq_mod.actor = actor  # type: ignore[attr-defined]
        dramatiq_mod.set_broker = set_broker  # type: ignore[attr-defined]

        redis_broker_mod = types.ModuleType("dramatiq.brokers.redis")
        redis_broker_mod.RedisBroker = DummyBroker  # type: ignore[attr-defined]

        middleware_mod = types.ModuleType("dramatiq.middleware")
        middleware_mod.Retries = lambda **kwargs: ("Retries", kwargs)  # type: ignore[attr-defined]
        middleware_mod.TimeLimit = lambda **kwargs: ("TimeLimit", kwargs)  # type: ignore[attr-defined]
        middleware_mod.AgeLimit = lambda **kwargs: ("AgeLimit", kwargs)  # type: ignore[attr-defined]
        middleware_mod.Results = lambda backend: ("Results", backend)  # type: ignore[attr-defined]

        results_mod = types.ModuleType("dramatiq.results")
        results_mod.RedisBackend = DummyResultsBackend  # type: ignore[attr-defined]

        redis_mod = types.ModuleType("redis")
        client = DummyRedisClient(ping_error=ping_error)
        redis_mod.from_url = lambda *_args, **_kwargs: client  # type: ignore[attr-defined]

        sys.modules["dramatiq"] = dramatiq_mod
        sys.modules["dramatiq.brokers.redis"] = redis_broker_mod
        sys.modules["dramatiq.middleware"] = middleware_mod
        sys.modules["dramatiq.results"] = results_mod
        sys.modules["redis"] = redis_mod

        return {"client": client, "set_broker_calls": set_broker_calls, "dramatiq": dramatiq_mod}

    def test_initialize_broker_success_and_enqueue(self) -> None:
        fake_modules = self.install_fake_modules()
        driver = self.DramatiqDriver(redis_url="redis://example")

        self.assertTrue(driver.is_available())
        self.assertEqual(len(driver._broker.middlewares), 5)

        # Verify the custom Flask app context middleware is registered
        from coati_payroll.queue.drivers.dramatiq_driver import FlaskAPPContextMiddleware
        self.assertTrue(any(isinstance(m, FlaskAPPContextMiddleware) for m in driver._broker.middlewares))

        self.assertEqual(fake_modules["set_broker_calls"], [driver._broker])

        actor = DummyActor()
        driver._tasks["sample"] = actor

        immediate = driver.enqueue("sample", 1, a=2)
        delayed = driver.enqueue("sample", 9, delay=4, b=5)

        self.assertEqual(immediate["mode"], "send")
        self.assertEqual(delayed["delay"], 4000)

    def test_initialize_broker_import_error(self) -> None:
        real_import = builtins.__import__

        def fail_dramatiq_import(name: str, *args: Any, **kwargs: Any):
            if name == "dramatiq":
                raise ImportError("missing dramatiq")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fail_dramatiq_import):
            driver = self.DramatiqDriver()

        self.assertFalse(driver.is_available())

    def test_initialize_broker_redis_failure(self) -> None:
        self.install_fake_modules(ping_error=RuntimeError("redis down"))
        driver = self.DramatiqDriver()
        self.assertFalse(driver.is_available())

    def test_enqueue_errors(self) -> None:
        driver = self.DramatiqDriver.__new__(self.DramatiqDriver)
        driver._available = False
        driver._tasks = {}

        with self.assertRaises(RuntimeError):
            driver.enqueue("missing")

        driver._available = True
        with self.assertRaises(ValueError):
            driver.enqueue("missing")

    def test_register_task_paths(self) -> None:
        fake_modules = self.install_fake_modules()
        driver = self.DramatiqDriver()

        def fn(x: int) -> int:
            return x

        actor = driver.register_task(fn, name="my_task", max_retries=7, min_backoff=1, max_backoff=2)
        self.assertEqual(actor["opts"]["actor_name"], "my_task")
        self.assertEqual(driver._tasks["my_task"], actor)

        def exploding_actor(**_kwargs: Any):
            raise RuntimeError("bad decorator")

        fake_modules["dramatiq"].actor = exploding_actor
        self.assertIs(driver.register_task(fn, name="broken"), fn)

    def test_register_task_when_unavailable_returns_original_function(self) -> None:
        driver = self.DramatiqDriver.__new__(self.DramatiqDriver)
        driver._available = False

        def fn() -> str:
            return "ok"

        self.assertIs(driver.register_task(fn), fn)

    def test_get_stats_success_and_error_paths(self) -> None:
        fake_modules = self.install_fake_modules()
        driver = self.DramatiqDriver()

        stats = driver.get_stats()
        self.assertEqual(stats["driver"], "dramatiq")
        self.assertEqual(stats["queues"]["default"], 3)

        fake_modules["client"].raise_keys = True
        stats_without_queues = driver.get_stats()
        self.assertNotIn("queues", stats_without_queues)

        unavailable = self.DramatiqDriver.__new__(self.DramatiqDriver)
        unavailable._available = False
        unavailable._broker = None
        self.assertEqual(
            unavailable.get_stats(),
            {"error": self.dramatiq_driver.ERROR_DRAMATIQ_NOT_AVAILABLE},
        )

        redis_mod = sys.modules["redis"]

        def fail_from_url(*_args: Any, **_kwargs: Any):
            raise RuntimeError("cannot connect")

        redis_mod.from_url = fail_from_url  # type: ignore[attr-defined]
        self.assertEqual(driver.get_stats(), {"error": "cannot connect"})

    def test_get_task_result_all_paths(self) -> None:
        self.install_fake_modules()

        unavailable = self.DramatiqDriver.__new__(self.DramatiqDriver)
        unavailable._available = False
        self.assertEqual(
            unavailable.get_task_result("x"),
            {"status": "error", "error": self.dramatiq_driver.ERROR_DRAMATIQ_NOT_AVAILABLE},
        )

        driver = self.DramatiqDriver()
        driver._results_backend = None
        pending = driver.get_task_result("abc")
        self.assertEqual(pending["status"], "pending")

        backend = DummyResultsBackend("redis://x")
        driver._results_backend = backend
        completed = driver.get_task_result("t1")
        self.assertEqual(completed["status"], "completed")

        result_missing = type("ResultMissing", (Exception,), {})
        backend.to_raise = result_missing("still running")
        still_pending = driver.get_task_result("t2")
        self.assertEqual(still_pending["status"], "pending")

        backend.to_raise = RuntimeError("kaput")
        failed = driver.get_task_result("t3")
        self.assertEqual(failed["status"], "error")

    def test_get_bulk_results(self) -> None:
        unavailable = self.DramatiqDriver.__new__(self.DramatiqDriver)
        unavailable._available = False
        self.assertEqual(
            unavailable.get_bulk_results([1]),
            {"error": self.dramatiq_driver.ERROR_DRAMATIQ_NOT_AVAILABLE},
        )

        driver = self.DramatiqDriver.__new__(self.DramatiqDriver)
        driver._available = True

        statuses = [
            {"status": "completed"},
            {"status": "failed"},
            {"status": "error"},
            {"status": "pending"},
        ]

        def fake_get_task_result(_task_id: Any) -> dict[str, Any]:
            return statuses.pop(0)

        driver.get_task_result = fake_get_task_result  # type: ignore[assignment]
        summary = driver.get_bulk_results(["a", "b", "c", "d"])

        self.assertEqual(summary["total"], 4)
        self.assertEqual(summary["completed"], 1)
        self.assertEqual(summary["failed"], 2)
        self.assertEqual(summary["pending"], 1)
        self.assertEqual(summary["progress_percentage"], 25.0)

        self.assertEqual(driver.get_bulk_results([])["progress_percentage"], 0)

    def test_flask_app_context_middleware_lifecycle(self) -> None:
        from coati_payroll.queue.drivers.dramatiq_driver import FlaskAPPContextMiddleware

        middleware = FlaskAPPContextMiddleware()

        # Mock Flask app and app_context
        mock_ctx = MagicMock()
        mock_app = MagicMock()
        mock_app.app_context.return_value = mock_ctx

        # Override _get_app to return our mock_app
        middleware._get_app = lambda: mock_app

        # Call before_process_message
        middleware.before_process_message(None, None)
        mock_app.app_context.assert_called_once()
        mock_ctx.push.assert_called_once()

        # Call after_process_message
        middleware.after_process_message(None, None)
        mock_ctx.pop.assert_called_once()
        self.assertIsNone(getattr(middleware._local, "ctx", None))

    def test_flask_app_context_middleware_skip_message(self) -> None:
        from coati_payroll.queue.drivers.dramatiq_driver import FlaskAPPContextMiddleware

        middleware = FlaskAPPContextMiddleware()

        mock_ctx = MagicMock()
        mock_app = MagicMock()
        mock_app.app_context.return_value = mock_ctx

        middleware._get_app = lambda: mock_app

        middleware.before_process_message(None, None)
        middleware.after_skip_message(None, None)
        mock_ctx.pop.assert_called_once()
        self.assertIsNone(getattr(middleware._local, "ctx", None))

    def test_flask_app_context_middleware_get_app_success(self) -> None:
        from coati_payroll.queue.drivers.dramatiq_driver import FlaskAPPContextMiddleware

        middleware = FlaskAPPContextMiddleware()

        mock_app = MagicMock()
        mock_create_app = MagicMock(return_value=mock_app)

        # Stub coati_payroll.create_app on the sys.modules stub
        import sys
        coati_mod = sys.modules["coati_payroll"]
        coati_mod.create_app = mock_create_app

        app = middleware._get_app()

        self.assertIs(app, mock_app)
        mock_create_app.assert_called_once_with(None)

        # Subsequent calls should return the cached app
        app_cached = middleware._get_app()
        self.assertIs(app_cached, mock_app)
        self.assertEqual(mock_create_app.call_count, 1)

    def test_flask_app_context_middleware_get_app_failure(self) -> None:
        from coati_payroll.queue.drivers.dramatiq_driver import FlaskAPPContextMiddleware

        middleware = FlaskAPPContextMiddleware()

        mock_create_app = MagicMock(side_effect=RuntimeError("creation failed"))

        import sys
        coati_mod = sys.modules["coati_payroll"]
        coati_mod.create_app = mock_create_app

        with self.assertRaises(RuntimeError):
            middleware._get_app()


if __name__ == "__main__":
    unittest.main()
