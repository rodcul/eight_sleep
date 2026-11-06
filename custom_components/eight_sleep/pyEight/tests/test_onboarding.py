"""Onboarding app-state read (fork issue #13).

Fixtures are synthetic: the shape comes from one iOS-app capture
(2026-11-03/04), the values are invented.
"""
import unittest
from unittest.mock import AsyncMock

from custom_components.eight_sleep.pyEight.eight import EightSleep
from custom_components.eight_sleep.pyEight.exceptions import RequestError
from custom_components.eight_sleep.pyEight.user import EightUser


class TestOnboardingState(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.eight = EightSleep("u@example.com", "pw", "UTC")
        self.user = EightUser(self.eight, "user-1", "left")

    def answer(self, value):
        self.eight.api_request = AsyncMock(return_value=value)

    async def test_reads_the_app_state_endpoint(self):
        self.answer({"value": {}})

        await self.user.onboarding_state()

        method, url = self.eight.api_request.await_args[0][:2]
        self.assertEqual(method, "get")
        self.assertIn("app-api", url)
        self.assertTrue(url.endswith("v1/users/user-1/app-state/onboard"), url)

    async def test_full_answer(self):
        self.answer(
            {
                "value": {
                    "lastOnboardTime": "2026-01-02T10:00:00.000Z",
                    "testDriveCompletedTimestamp": "2026-01-03T10:00:00.000Z",
                }
            }
        )

        state = await self.user.onboarding_state()

        self.assertEqual(
            state.last_onboard_time.isoformat(), "2026-01-02T10:00:00+00:00"
        )
        self.assertTrue(state.test_drive_completed)

    async def test_pod5_test_drive_counts(self):
        self.answer(
            {"value": {"pod5TestDriveCompletedTimestamp": "2026-01-03T10:00:00Z"}}
        )

        state = await self.user.onboarding_state()

        self.assertTrue(state.test_drive_completed)
        self.assertIsNone(state.last_onboard_time)

    async def test_no_test_drive_timestamps_is_false(self):
        self.answer({"value": {"lastOnboardTime": "2026-01-02T10:00:00Z"}})

        state = await self.user.onboarding_state()

        self.assertFalse(state.test_drive_completed)

    async def test_missing_value_is_none_not_keyerror(self):
        self.answer({})

        state = await self.user.onboarding_state()

        self.assertIsNone(state.last_onboard_time)
        self.assertIsNone(state.test_drive_completed)

    async def test_404_is_none(self):
        self.eight.api_request = AsyncMock(
            side_effect=RequestError("not found", status=404)
        )

        self.assertIsNone(await self.user.onboarding_state())

    def test_there_is_no_write_method(self):
        writes = [
            name
            for name in dir(EightUser)
            if "onboard" in name and name != "onboarding_state"
        ]
        self.assertEqual(writes, [])


if __name__ == "__main__":
    unittest.main()
