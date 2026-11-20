"""Latest prime task and priming schedule (fork issue #10).

Fixtures are synthetic: the shape comes from one iOS-app capture
(2026-11-03/04), the values are invented.
"""
from datetime import datetime
import unittest
from unittest.mock import AsyncMock, MagicMock

from custom_components.eight_sleep.pyEight.eight import EightSleep
from custom_components.eight_sleep.pyEight.exceptions import RequestError
from custom_components.eight_sleep.pyEight.structs import Token

SUCCEEDED = {
    "task": {
        "taskId": "task-1",
        "status": "finished",
        "reason": "requested",
        "outcome": "succeeded",
        "outcomeReason": "flagCleared",
        "created": "2026-01-02T10:00:00.000Z",
        "started": "2026-01-02T10:00:05.000Z",
        "finished": "2026-01-02T10:02:10.000Z",
        "isBlanketPriming": False,
        "notifications": {"users": ["user-1"], "meta": "rePriming"},
        "coverInfo": {"label": "cover"},
    }
}

OUT_OF_WATER = {
    "task": {
        **SUCCEEDED["task"],
        "outcome": "out-of-water",
        "outcomeReason": "noWater",
    }
}

SCHEDULED = {
    "task": {
        **SUCCEEDED["task"],
        "reason": "scheduled",
    }
}


class TestLatestPrimeTask(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.eight = EightSleep("u@example.com", "pw", "UTC")
        self.eight.device_id = "device_1"

    async def test_reads_the_latest_task_endpoint(self):
        self.eight.api_request = AsyncMock(return_value=SUCCEEDED)

        await self.eight.latest_prime_task()

        method, url = self.eight.api_request.await_args[0][:2]
        self.assertEqual(method, "get")
        self.assertTrue(
            url.endswith("v1/devices/device_1/priming/tasks/latest"), url
        )
        self.assertIn("app-api", url)

    async def test_succeeded(self):
        self.eight.api_request = AsyncMock(return_value=SUCCEEDED)

        task = await self.eight.latest_prime_task()

        self.assertEqual(task.status, "finished")
        self.assertEqual(task.reason, "requested")
        self.assertEqual(task.outcome, "succeeded")
        self.assertEqual(task.outcome_reason, "flagCleared")
        self.assertFalse(task.ran_dry)
        self.assertIsInstance(task.created, datetime)
        self.assertEqual(task.finished.isoformat(), "2026-01-02T10:02:10+00:00")

    async def test_out_of_water_means_ran_dry(self):
        self.eight.api_request = AsyncMock(return_value=OUT_OF_WATER)

        task = await self.eight.latest_prime_task()

        self.assertTrue(task.ran_dry)
        self.assertEqual(task.outcome_reason, "noWater")

    async def test_scheduled(self):
        self.eight.api_request = AsyncMock(return_value=SCHEDULED)

        task = await self.eight.latest_prime_task()

        self.assertEqual(task.reason, "scheduled")
        self.assertFalse(task.ran_dry)

    async def test_no_task_404_is_none(self):
        self.eight.api_request = AsyncMock(
            side_effect=RequestError("not found", status=404)
        )

        self.assertIsNone(await self.eight.latest_prime_task())

    async def test_no_task_key_is_none(self):
        self.eight.api_request = AsyncMock(return_value={})

        self.assertIsNone(await self.eight.latest_prime_task())

    async def test_other_errors_still_raise(self):
        self.eight.api_request = AsyncMock(
            side_effect=RequestError("boom", status=500)
        )

        with self.assertRaises(RequestError):
            await self.eight.latest_prime_task()

    async def test_missing_keys_are_none(self):
        self.eight.api_request = AsyncMock(return_value={"task": {"status": "running"}})

        task = await self.eight.latest_prime_task()

        self.assertEqual(task.status, "running")
        self.assertIsNone(task.reason)
        self.assertIsNone(task.outcome)
        self.assertIsNone(task.outcome_reason)
        self.assertIsNone(task.created)
        self.assertIsNone(task.started)
        self.assertIsNone(task.finished)
        self.assertIsNone(task.ran_dry)

    async def test_bad_timestamp_is_none(self):
        self.eight.api_request = AsyncMock(
            return_value={"task": {**SUCCEEDED["task"], "finished": "not a date"}}
        )

        task = await self.eight.latest_prime_task()

        self.assertIsNone(task.finished)


class TestPrimingSchedule(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.eight = EightSleep("u@example.com", "pw", "UTC")
        self.eight.device_id = "device_1"

    async def test_reads_the_schedule_endpoint(self):
        self.eight.api_request = AsyncMock(return_value={"schedule": []})

        await self.eight.priming_schedule()

        url = self.eight.api_request.await_args[0][1]
        self.assertTrue(url.endswith("v1/devices/device_1/priming/schedule"), url)

    async def test_empty_schedule(self):
        self.eight.api_request = AsyncMock(return_value={"schedule": []})

        self.assertEqual(await self.eight.priming_schedule(), [])

    async def test_items_are_returned_as_is(self):
        """The item shape was not captured, so items pass through raw."""
        items = [{"time": "03:00"}]
        self.eight.api_request = AsyncMock(return_value={"schedule": items})

        self.assertEqual(await self.eight.priming_schedule(), items)

    async def test_missing_key_is_none(self):
        self.eight.api_request = AsyncMock(return_value={})

        self.assertIsNone(await self.eight.priming_schedule())

    async def test_404_is_none(self):
        self.eight.api_request = AsyncMock(
            side_effect=RequestError("not found", status=404)
        )

        self.assertIsNone(await self.eight.priming_schedule())


class TestExpectedStatusLogging(unittest.IsolatedAsyncioTestCase):
    """A 404 that means "no task" must not log at ERROR every poll."""

    def setUp(self):
        self.eight = EightSleep("u@example.com", "pw", "UTC")
        self.eight.device_id = "device_1"
        self.eight._token = Token("tok", 9e12, "user-1")
        resp = MagicMock(status=404)
        resp.json = AsyncMock(return_value={"message": "not found"})
        self.eight._api_session = MagicMock()
        self.eight._api_session.request = AsyncMock(return_value=resp)

    async def test_expected_status_logs_at_debug(self):
        with self.assertLogs(
            "custom_components.eight_sleep.pyEight.eight", level="DEBUG"
        ) as logs:
            self.assertIsNone(await self.eight.latest_prime_task())

        self.assertTrue(logs.records)
        self.assertFalse([r for r in logs.records if r.levelname == "ERROR"])

    async def test_unexpected_status_still_logs_at_error(self):
        with self.assertLogs(
            "custom_components.eight_sleep.pyEight.eight", level="ERROR"
        ):
            with self.assertRaises(RequestError):
                await self.eight.api_request("get", "https://example.invalid/x")


if __name__ == "__main__":
    unittest.main()
