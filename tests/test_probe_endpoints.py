"""The read-only endpoint probe script (fork issue #9)."""
import importlib.util
from pathlib import Path
import unittest

import httpx

_PATH = Path(__file__).resolve().parent.parent / "scripts" / "probe_endpoints.py"
_spec = importlib.util.spec_from_file_location("probe_endpoints", _PATH)
probe_endpoints = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probe_endpoints)

TOKEN = "eyJhbGciOiJIUzI1NiJ9.c2VjcmV0LXRva2Vu.c2lnbmF0dXJl"
USER_ID = "0123456789abcdef0123456789abcdef"


class TestFormatter(unittest.TestCase):
    def test_token_is_absent_from_the_output(self):
        body = {
            "access_token": TOKEN,
            "user": {"token": TOKEN},
            TOKEN: "token as a key",
            "userId": USER_ID,
        }

        line = probe_endpoints.format_line(
            "{auth}/v1/tokens", 200, body, secrets=[TOKEN, USER_ID]
        )

        self.assertNotIn(TOKEN, line)
        self.assertNotIn(USER_ID, line)
        self.assertIn("access_token", line)
        self.assertIn("userId", line)

    def test_values_are_never_printed(self):
        body = {"email": "someone@example.com", "hubSerial": "ABC-123-XYZ"}

        line = probe_endpoints.format_line("{client}/v1/users/me", 200, body)

        self.assertNotIn("someone@example.com", line)
        self.assertNotIn("ABC-123-XYZ", line)

    def test_id_shaped_keys_are_hidden_even_if_not_known(self):
        line = probe_endpoints.describe(
            {"fedcba9876543210fedcba98": {}, "sub_1AbCdEf": {}, "settings": {}}
        )

        self.assertEqual(line, "<id>, settings")

    def test_real_key_names_with_digits_survive(self):
        line = probe_endpoints.describe({"pod5TestDriveCompletedTimestamp": 1})

        self.assertEqual(line, "pod5TestDriveCompletedTimestamp")

    def test_lists_print_only_their_length(self):
        self.assertEqual(probe_endpoints.describe([TOKEN, TOKEN]), "list[2]")

    def test_line_shape(self):
        line = probe_endpoints.format_line(
            "{app}/v1/devices/{deviceId}/status", 404, {"message": "x"}
        )

        self.assertEqual(line, "GET {app}/v1/devices/{deviceId}/status → 404, message")


def _client(*statuses):
    """An httpx client that answers each request with the next status."""
    answers = iter(statuses)
    seen = []

    def handler(request):
        seen.append(request.method)
        return httpx.Response(next(answers), json={"access_token": TOKEN})

    return httpx.Client(transport=httpx.MockTransport(handler)), seen


class TestProbe(unittest.TestCase):
    def test_refuses_anything_but_get(self):
        client, seen = _client(200)
        probe = probe_endpoints.Probe(client, sleep=lambda s: None)

        for method in ("POST", "PUT", "PATCH", "DELETE"):
            with self.assertRaises(ValueError):
                probe.request(method, "https://app-api.8slp.net/x")
        self.assertEqual(seen, [])

    def test_backs_off_30s_on_429(self):
        client, seen = _client(429, 200)
        slept = []
        probe = probe_endpoints.Probe(client, sleep=slept.append)

        response = probe.request("GET", "https://app-api.8slp.net/x")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(slept, [30])
        self.assertEqual(seen, ["GET", "GET"])

    def test_pauses_at_least_4s_between_logins(self):
        client, seen = _client(429, 200)
        slept = []
        now = [100.0]

        def sleep(seconds):
            slept.append(seconds)
            now[0] += seconds

        probe = probe_endpoints.Probe(client, sleep=sleep, clock=lambda: now[0])
        constants = probe_endpoints._load_constants()

        token = probe.login("u@example.com", "pw", constants)

        self.assertEqual(token, TOKEN)
        self.assertEqual(seen, ["POST", "POST"])
        self.assertGreaterEqual(sum(slept), 4)
        self.assertIn(30, slept)

    def test_every_endpoint_template_is_unfilled(self):
        """Printed paths must be templates, never real ids."""
        for template, _ in probe_endpoints.ENDPOINTS:
            self.assertTrue(template.startswith("{"), template)
            self.assertNotRegex(template, r"[0-9a-f]{12,}")


if __name__ == "__main__":
    unittest.main()
