#!/usr/bin/env python3
"""Read-only probe of the Eight Sleep endpoints in docs/api-notes.md.

Logs in with EIGHT_SLEEP_EMAIL / EIGHT_SLEEP_PASSWORD, finds the user id and
first device id via users/me, then GETs every endpoint below and prints one
line each:

    GET {app}/v1/devices/{deviceId}/status → 200, firmwareVersion, hasWater, …

That line is how an endpoint in docs/api-notes.md earns "Seen <date>".

It prints status codes and top-level key names only: never values, tokens or
ids. It sends GET and nothing else.

    python scripts/probe_endpoints.py

Credentials come from the environment, or from `.env.local` at the repo root
(gitignored) for any variable not already set.

Needs only httpx. Optional: EIGHT_SLEEP_TZ (default America/Los_Angeles).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import importlib.util
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Callable, Iterable

import httpx

LOGIN_PAUSE_SECONDS = 4
RATE_LIMIT_BACKOFF_SECONDS = 30
MAX_ATTEMPTS = 3
TIMEOUT_SECONDS = 20

HOSTS = {
    "auth": "https://auth-api.8slp.net",
    "client": "https://client-api.8slp.net",
    "app": "https://app-api.8slp.net",
}

# (path template, query params). Templates are what gets printed, so they must
# never be filled in on output. {today}, {yesterday} and {tz} are filled in the
# query only.
ENDPOINTS: list[tuple[str, dict[str, str]]] = [
    # The "Reads" table.
    ("{client}/v1/users/me", {}),
    ("{client}/v1/devices/{deviceId}", {}),
    ("{client}/v1/devices/{deviceId}", {"filter": "leftUserId,rightUserId,awaySides"}),
    ("{client}/v1/users/{userId}/current-device", {}),
    ("{client}/v1/users/{userId}", {}),
    (
        "{client}/v1/users/{userId}/trends",
        {
            "tz": "{tz}",
            "from": "{yesterday}",
            "to": "{today}",
            "include-main": "false",
            "include-all-sessions": "true",
            "model-version": "v2",
        },
    ),
    ("{app}/v1/household/users/{userId}/summary", {}),
    ("{app}/v1/users/{userId}/subscriptions", {}),
    ("{app}/v1/users/{userId}/temperature", {}),
    ("{app}/v1/users/{userId}/temperature/all", {}),
    ("{app}/v1/users/{userId}/temperature/pillow", {}),
    ("{app}/v2/users/{userId}/alarms", {}),
    ("{app}/v2/users/{userId}/routines", {}),
    ("{app}/v1/users/{userId}/base", {}),
    ("{app}/v1/users/{userId}/audio/player", {}),
    ("{app}/v1/users/{userId}/audio/tracks", {}),
    ("{app}/v1/users/{userId}/away-mode", {}),
    ("{app}/v1/users/{userId}/autopilotDetails", {}),
    # Takes full ISO timestamps; bare dates answer 400 (seen 2026-11-06).
    ("{app}/v1/users/{userId}/temp-events", {"from": "{day_ago_iso}", "to": "{now_iso}"}),
    ("{app}/v1/users/{userId}/bedtime/recommendation", {}),
    ("{app}/v1/user/{userId}/device_maintenance/maintenance_insert", {"v": "2"}),
    ("{app}/v1/users/{userId}/level-suggestions", {}),
    ("{app}/v1/users/{userId}/challenges", {}),
    ("{app}/v1/users/{userId}/travel/trips", {}),
    # The app capture (2026-11-03). The events websocket is left out.
    ("{app}/v1/devices/{deviceId}/status", {}),
    ("{app}/v1/devices/{deviceId}/priming/tasks/latest", {}),
    ("{app}/v1/devices/{deviceId}/priming/schedule", {}),
    ("{app}/v1/devices/{deviceId}/live", {}),
    ("{app}/v3/users/{userId}/subscriptions", {}),
    ("{app}/v1/users/{userId}/app-state/onboard", {}),
    ("{app}/v1/users/{userId}/app-state/messages", {}),
    ("{auth}/v1/grants", {}),
    ("{client}/v1/users/{userId}/intervals", {}),
    ("{client}/v1/users/{userId}/temperature", {}),
    ("{app}/v1/users/{userId}/release-features", {}),
    ("{app}/v1/users/{userId}/temperature/hot-flash-mode", {}),
    ("{app}/v1/users/{userId}/active-mode", {}),
    ("{app}/v1/users/{userId}/level-suggestions-mode", {}),
    (
        "{app}/v1/users/{userId}/autopilotDetails/autopilotRecap",
        {"day": "{yesterday}", "tz": "{tz}"},
    ),
    ("{app}/v1/users/{userId}/days/count", {}),
    ("{app}/v1/users/{userId}/devices/all/tap-settings", {}),
    ("{app}/v1/users/{userId}/notifications", {"active": "true", "limit": "10"}),
    ("{app}/v1/users/{userId}/llm-insights/settings", {}),
    ("{app}/v1/users/{userId}/tags/days", {}),
    ("{app}/v1/users/{userId}/tags/recommendations", {}),
    ("{app}/v1/users/{userId}/truth-tags", {}),
    ("{app}/v1/users/{userId}/health-integrations/metadata", {}),
    ("{app}/v1/intelligence/{userId}/podai/bio-age", {}),
    ("{app}/v1/sms/users/{userId}", {}),
    ("{app}/v1/health-survey/test-drive", {}),
    ("{app}/v1/audio/categories", {}),
    ("{app}/v2/users/{userId}/referral/campaigns", {}),
]

# Key names that are themselves an id (a run of hex, as in uuids and device
# ids, or a Stripe id) are hidden.
_ID_LIKE = re.compile(r"[0-9a-fA-F]{12,}|^sub_")


def _load_constants() -> Any:
    """Load pyEight/constants.py by path; the package import pulls in HA."""
    path = (
        Path(__file__).resolve().parent.parent
        / "custom_components/eight_sleep/pyEight/constants.py"
    )
    spec = importlib.util.spec_from_file_location("eight_constants", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _safe_key(key: Any, secrets: Iterable[str]) -> str:
    key = str(key)
    if any(s and s in key for s in secrets) or _ID_LIKE.search(key):
        return "<id>"
    return key


def describe(body: Any, secrets: Iterable[str] = ()) -> str:
    """Describe a response body by shape only: key names, never values."""
    secrets = [s for s in secrets if s]
    if isinstance(body, dict):
        keys = sorted({_safe_key(k, secrets) for k in body})
        return ", ".join(keys) if keys else "{}"
    if isinstance(body, list):
        return f"list[{len(body)}]"
    if body is None:
        return "no body"
    return type(body).__name__


def format_line(template: str, status: int, body: Any, secrets: Iterable[str] = ()) -> str:
    return f"GET {template} → {status}, {describe(body, secrets)}"


class Probe:
    """A GET-only client with login pacing and 429 back-off."""

    def __init__(
        self,
        client: httpx.Client,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._sleep = sleep
        self._clock = clock
        self._last_login: float | None = None
        self.token: str | None = None

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Send a request, backing off on 429. Refuses anything but GET."""
        if method.upper() != "GET":
            raise ValueError(f"probe is read-only; refusing {method}")
        return self._with_backoff(lambda: self._client.request("GET", url, **kwargs))

    def _with_backoff(self, send: Callable[[], httpx.Response]) -> httpx.Response:
        for attempt in range(MAX_ATTEMPTS):
            response = send()
            if response.status_code != 429 or attempt == MAX_ATTEMPTS - 1:
                return response
            self._sleep(RATE_LIMIT_BACKOFF_SECONDS)
        return response

    def login(self, email: str, password: str, constants: Any) -> str:
        """Log in once. The only POST this script sends, to the token host."""

        def send() -> httpx.Response:
            if self._last_login is not None:
                wait = LOGIN_PAUSE_SECONDS - (self._clock() - self._last_login)
                if wait > 0:
                    self._sleep(wait)
            self._last_login = self._clock()
            return self._client.post(
                constants.AUTH_URL,
                headers={"user-agent": "okhttp/4.9.3", "accept": "application/json"},
                json={
                    "client_id": constants.KNOWN_CLIENT_ID,
                    "client_secret": constants.KNOWN_CLIENT_SECRET,
                    "grant_type": "password",
                    "username": email,
                    "password": password,
                },
            )

        response = self._with_backoff(send)
        if response.status_code != 200:
            raise SystemExit(f"login failed: {response.status_code}")
        self.token = response.json()["access_token"]
        return self.token


def _fill(template: str, ids: dict[str, str]) -> str:
    return template.format(**HOSTS, **ids)


def _query(params: dict[str, str], tz: str) -> dict[str, str]:
    today = date.today()
    now = datetime.now(timezone.utc)
    iso = "%Y-%m-%dT%H:%M:%S.000Z"
    fills = {
        "today": today.isoformat(),
        "yesterday": (today - timedelta(days=1)).isoformat(),
        "now_iso": now.strftime(iso),
        "day_ago_iso": (now - timedelta(days=1)).strftime(iso),
        "tz": tz,
    }
    return {k: v.format(**fills) for k, v in params.items()}


def _json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return None


def _load_env_local() -> None:
    """Fill unset variables from the repo's .env.local (gitignored)."""
    path = Path(__file__).resolve().parent.parent / ".env.local"
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def main() -> int:
    _load_env_local()
    email = os.environ.get("EIGHT_SLEEP_EMAIL")
    password = os.environ.get("EIGHT_SLEEP_PASSWORD")
    if not email or not password:
        print("set EIGHT_SLEEP_EMAIL and EIGHT_SLEEP_PASSWORD", file=sys.stderr)
        return 2
    tz = os.environ.get("EIGHT_SLEEP_TZ", "America/Los_Angeles")

    with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
        probe = Probe(client)
        token = probe.login(email, password, _load_constants())
        headers = {
            "authorization": f"Bearer {token}",
            "user-agent": "okhttp/4.9.3",
            "accept": "application/json",
        }

        me = _json(probe.request("GET", f"{HOSTS['client']}/v1/users/me", headers=headers))
        user = (me or {}).get("user") or {}
        user_id = user.get("userId") or ""
        devices = user.get("devices") or []
        device_id = devices[0] if devices else ""
        secrets = [token, user_id, device_id, email, password]
        print(f"# {date.today().isoformat()}, account has {len(devices)} device(s)")

        for template, params in ENDPOINTS:
            if "{deviceId}" in template and not device_id:
                print(f"GET {template} → skipped, no device")
                continue
            url = _fill(template, {"userId": user_id, "deviceId": device_id})
            try:
                response = probe.request(
                    "GET", url, headers=headers, params=_query(params, tz)
                )
            except httpx.HTTPError as err:
                print(f"GET {template} → {type(err).__name__}")
                continue
            print(format_line(template, response.status_code, _json(response), secrets))
    return 0


if __name__ == "__main__":
    sys.exit(main())
