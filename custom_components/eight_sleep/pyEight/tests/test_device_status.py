"""Device status (fork issue #11).

Fixtures are synthetic: the shape comes from one iOS-app capture
(2026-11-03/04), the values are invented.
"""
import unittest
from unittest.mock import AsyncMock

from custom_components.eight_sleep.pyEight.eight import EightSleep
from custom_components.eight_sleep.pyEight.exceptions import RequestError

READY = {
    "status": "ready",
    "ready": True,
    "hasWater": True,
    "needsPrime": False,
    "firmwareVersion": "abc1234",
    "firmwareUpdated": True,
    "firmwareUpdating": False,
    "lastConnected": "2026-01-02T10:00:00.000Z",
}

UPDATING = {
    **READY,
    "status": "updating",
    "ready": False,
    "firmwareUpdated": False,
    "firmwareUpdating": True,
}

DRY = {
    **READY,
    "hasWater": False,
    "needsPrime": True,
}


class TestDeviceStatus(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.eight = EightSleep("u@example.com", "pw", "UTC")
        self.eight.device_id = "device_1"

    async def test_reads_the_status_endpoint_on_app_api(self):
        self.eight.api_request = AsyncMock(return_value=READY)

        await self.eight.device_status()

        method, url = self.eight.api_request.await_args[0][:2]
        self.assertEqual(method, "get")
        self.assertIn("app-api", url)
        self.assertTrue(url.endswith("v1/devices/device_1/status"), url)

    async def test_ready(self):
        self.eight.api_request = AsyncMock(return_value=READY)

        status = await self.eight.device_status()

        self.assertEqual(status.status, "ready")
        self.assertTrue(status.ready)
        self.assertTrue(status.has_water)
        self.assertFalse(status.needs_prime)
        self.assertEqual(status.firmware_version, "abc1234")
        self.assertTrue(status.firmware_updated)
        self.assertFalse(status.firmware_updating)
        self.assertEqual(
            status.last_connected.isoformat(), "2026-01-02T10:00:00+00:00"
        )

    async def test_updating(self):
        self.eight.api_request = AsyncMock(return_value=UPDATING)

        status = await self.eight.device_status()

        self.assertEqual(status.status, "updating")
        self.assertFalse(status.ready)
        self.assertFalse(status.firmware_updated)
        self.assertTrue(status.firmware_updating)

    async def test_dry(self):
        self.eight.api_request = AsyncMock(return_value=DRY)

        status = await self.eight.device_status()

        self.assertFalse(status.has_water)
        self.assertTrue(status.needs_prime)

    async def test_missing_keys_are_none(self):
        self.eight.api_request = AsyncMock(return_value={})

        status = await self.eight.device_status()

        for field in (
            "status",
            "ready",
            "has_water",
            "needs_prime",
            "firmware_version",
            "firmware_updated",
            "firmware_updating",
            "last_connected",
        ):
            self.assertIsNone(getattr(status, field), field)

    async def test_404_is_none(self):
        self.eight.api_request = AsyncMock(
            side_effect=RequestError("not found", status=404)
        )

        self.assertIsNone(await self.eight.device_status())

    async def test_docstring_explains_the_priming_field_names(self):
        doc = EightSleep.device_status.__doc__
        self.assertIn("needsPrime", doc)
        self.assertIn("needsPriming", doc)


if __name__ == "__main__":
    unittest.main()
