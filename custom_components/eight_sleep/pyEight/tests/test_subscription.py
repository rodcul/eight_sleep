"""v3 subscriptions (fork issue #12).

The rules below were learned live on v1 (see docs/api-notes.md,
"Subscriptions"). Fixtures are synthetic: the v3 shape comes from one iOS-app
capture (2026-11-03/04), the values are invented.
"""
from datetime import datetime, timezone
import unittest
from unittest.mock import AsyncMock

from custom_components.eight_sleep.pyEight.eight import EightSleep
from custom_components.eight_sleep.pyEight.exceptions import RequestError
from custom_components.eight_sleep.pyEight.subscription import judge_subscription
from custom_components.eight_sleep.pyEight.user import EightUser

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)

FLAGS = {
    "hasAccessToPremiumFeatures": True,
    "hasAccessToBasicFeatures": True,
    "hasBasic": False,
    "isInGracePeriod": False,
    "isUnpaidPremium": False,
    "churned": False,
    "capabilities": ["autopilot"],
}


def stripe(expires="2027-01-01T00:00:00Z", renews=True, created="2026-01-01T00:00:00Z"):
    return {
        "subscriptionId": "sub_abc123",
        "status": "active",
        "provider": "stripe",
        "subscriptionTier": "pro",
        "subscriptionFrequency": "yearly",
        "createdAt": created,
        "expiresAt": expires,
        "willRenew": renews,
        "isRental": False,
        "ownerUserId": "user-1",
        "subscriberRelationship": "self",
    }


def temporary(created="2026-02-01T00:00:00Z"):
    return {
        "subscriptionId": "eight-internal-temporary-0000-1111",
        "status": "inactive",
        "provider": "eight_internal",
        "createdAt": created,
        "expiresAt": created,
        "willRenew": False,
    }


def exclusive_member():
    """Granted by Eight Sleep: no expiresAt key at all, never renews."""
    return {
        "subscriptionId": "exclusive-member-2222-3333",
        "status": "active",
        "provider": "eight_internal",
        "subscriptionFrequency": "lifetime",
        "createdAt": "2026-01-01T00:00:00Z",
        "willRenew": False,
    }


def pool_seat(expires="2027-01-01T00:00:00Z", created="2026-01-01T00:00:00Z"):
    """A seat from a pooled plan. Seen live 2026-11-06: never renews."""
    return {
        "subscriptionId": "pool-seat-12345",
        "status": "active",
        "provider": "pool",
        "type": "premium",
        "subscriptionTier": "plus",
        "subscriptionFrequency": "yearly",
        "isActive": True,
        "createdAt": created,
        "expiresAt": expires,
        "willRenew": False,
    }


class TestJudgePoolSeat(unittest.TestCase):
    """Seen live 2026-11-06, as primary beside an expired placeholder."""

    def test_live_pool_seat_is_active_though_it_never_renews(self):
        seat = pool_seat()
        body = {"subscriptions": [temporary(), seat], "primarySubscription": seat}
        self.assertEqual(judge_subscription(body, NOW).state, "active")

    def test_expired_pool_seat_is_lapsed(self):
        seat = pool_seat(expires="2026-03-01T00:00:00Z")
        self.assertEqual(
            judge_subscription({"subscriptions": [seat]}, NOW).state, "lapsed"
        )

    def test_pool_seat_beats_a_newer_placeholder(self):
        seat = pool_seat(created="2025-01-01T00:00:00Z")
        newer = temporary(created="2026-04-01T00:00:00Z")
        self.assertEqual(
            judge_subscription({"subscriptions": [newer, seat]}, NOW).state,
            "active",
        )


class TestJudgeSubscriptionV1Rules(unittest.TestCase):
    """The rules from v1, ported as tests first."""

    def judge(self, body):
        return judge_subscription(body, NOW).state

    def test_stripe_primary_renewing_is_active(self):
        rec = stripe()
        self.assertEqual(
            self.judge({"subscriptions": [rec], "primarySubscription": rec}),
            "active",
        )

    def test_stripe_live_but_not_renewing_is_expiring(self):
        rec = stripe(renews=False)
        self.assertEqual(
            self.judge({"subscriptions": [rec], "primarySubscription": rec}),
            "expiring",
        )

    def test_primary_absent_when_nothing_live_reads_records(self):
        """Reading only the primary turns a lapsed account into unknown."""
        rec = stripe(expires="2026-03-01T00:00:00Z")
        self.assertEqual(self.judge({"subscriptions": [rec]}), "lapsed")

    def test_judge_by_expires_at_not_will_renew(self):
        """willRenew true on a record whose expiresAt has passed is lapsed."""
        rec = stripe(expires="2026-03-01T00:00:00Z", renews=True)
        self.assertEqual(self.judge({"subscriptions": [rec]}), "lapsed")

    def test_internal_temporary_is_never_started(self):
        self.assertEqual(
            self.judge({"subscriptions": [temporary()]}), "never_started"
        )

    def test_exclusive_member_is_granted(self):
        rec = exclusive_member()
        self.assertEqual(
            self.judge({"subscriptions": [rec], "primarySubscription": rec}),
            "granted",
        )

    def test_exclusive_member_without_primary_is_still_granted(self):
        self.assertEqual(
            self.judge({"subscriptions": [exclusive_member()]}), "granted"
        )

    def test_bought_record_beats_a_newer_placeholder(self):
        """Newest-wins would pick the placeholder and say never_started."""
        bought = stripe(expires="2026-03-01T00:00:00Z", created="2025-01-01T00:00:00Z")
        newer = temporary(created="2026-04-01T00:00:00Z")
        self.assertEqual(
            self.judge({"subscriptions": [newer, bought]}), "lapsed"
        )

    def test_newest_bought_record_wins(self):
        old = stripe(expires="2025-01-01T00:00:00Z", created="2024-01-01T00:00:00Z")
        new = stripe(expires="2026-03-01T00:00:00Z", created="2025-03-01T00:00:00Z")
        new["subscriptionId"] = "sub_newer"
        result = judge_subscription({"subscriptions": [old, new]}, NOW)
        self.assertEqual(result.record["subscriptionId"], "sub_newer")

    def test_empty_list_and_no_primary_is_unknown(self):
        self.assertEqual(self.judge({"subscriptions": []}), "unknown")

    def test_empty_body_is_unknown(self):
        self.assertEqual(self.judge({}), "unknown")

    def test_bought_record_without_expires_at_is_unknown(self):
        rec = stripe()
        del rec["expiresAt"]
        self.assertEqual(self.judge({"subscriptions": [rec]}), "unknown")

    def test_unreadable_expires_at_is_unknown(self):
        rec = stripe(expires="soon")
        self.assertEqual(self.judge({"subscriptions": [rec]}), "unknown")

    def test_unrecognised_record_is_unknown(self):
        rec = {"subscriptionId": "something-new", "expiresAt": "2027-01-01T00:00:00Z"}
        self.assertEqual(self.judge({"subscriptions": [rec]}), "unknown")


class TestJudgeSubscriptionV3Flags(unittest.TestCase):
    def test_raw_computed_flags_are_returned(self):
        rec = stripe()
        body = {"subscriptions": [rec], "primarySubscription": rec, **FLAGS}

        result = judge_subscription(body, NOW)

        self.assertEqual(result.flags, FLAGS)

    def test_absent_flags_are_left_out(self):
        result = judge_subscription({"subscriptions": []}, NOW)

        self.assertEqual(result.flags, {})


class TestUserSubscription(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.eight = EightSleep("u@example.com", "pw", "UTC")
        self.user = EightUser(self.eight, "user-1", "left")

    async def test_reads_v3(self):
        self.eight.api_request = AsyncMock(return_value={"subscriptions": []})

        await self.user.subscription()

        method, url = self.eight.api_request.await_args[0][:2]
        self.assertEqual(method, "get")
        self.assertIn("app-api", url)
        self.assertTrue(url.endswith("v3/users/user-1/subscriptions"), url)

    async def test_403_is_unavailable_not_no_subscription(self):
        """A partner's side can't be read with the main account's token."""
        self.eight.api_request = AsyncMock(
            side_effect=RequestError("forbidden", status=403)
        )

        result = await self.user.subscription()

        self.assertEqual(result.state, "unavailable")
        self.assertIsNone(result.record)

    async def test_other_errors_raise(self):
        self.eight.api_request = AsyncMock(
            side_effect=RequestError("boom", status=500)
        )

        with self.assertRaises(RequestError):
            await self.user.subscription()

    async def test_judges_the_answer(self):
        rec = stripe(expires="2099-01-01T00:00:00Z")
        self.eight.api_request = AsyncMock(
            return_value={"subscriptions": [rec], "primarySubscription": rec}
        )

        result = await self.user.subscription()

        self.assertEqual(result.state, "active")


if __name__ == "__main__":
    unittest.main()
