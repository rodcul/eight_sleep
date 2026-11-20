# Upstream log

What this fork took from [lukas-clarke/eight_sleep](https://github.com/lukas-clarke/eight_sleep),
what it skipped, and why. Add a dated section each time you review upstream.

## 2026-11-03: the 13 open PRs

All 13 were read and cherry-picked with `git cherry-pick -x`, so each commit
keeps its original author and names its upstream source. They landed as a
chain of PRs on this fork, in this order:

| Order | Upstream PR | What | Notes |
| --- | --- | --- | --- |
| 1 | #162 | One-off alarm: coerce `time` to str | Crash fix |
| 1 | #160 | Thermostat setpoint no longer expires after 2 h | `heat_set` with `duration: 0` no longer sends a 0 s override |
| 2 | #156 | Hub binary sensors: online, firmware updating, has water, needs priming, is priming; `firmware_version`, `last_heard` | **Breaking:** three `sensor.*` priming/water entities become `binary_sensor.*_hub_*`. Fork adds: `last_prime` returns None when `lastPrime` is missing |
| 3 | #171 | Next Insert Replacement sensor | Rebased over #156: dropped its `else: CONF_BINARY_SENSORS` branch |
| 4 | #168 | Autopilot Active / Adjustments | Fork adds: `adjustments` kept out of the recorder (up to 50 dicts per change). A failing endpoint is still logged at ERROR by `api_request`, once an hour |
| 5 | #164 | Measured Bed Temperature | |
| 5 | #165 | Snoring sensors | |
| 5 | #166 | Sleep latency, daily sleep debt | |
| 5 | #167 | Base snore mitigation sensors | |
| 5 | #170 | Personal range attributes on HR/HRV/breath rate | |
| 6 | #169 | Exercise/cognitive windows, chronotype, social jetlag, bedtime | Fork adds: each of #168's and #169's tests now stubs the other's endpoint |

Skipped:

- **#144** (manifest version sync): main was already at 1.0.24.
- **#125** (debounce concurrent service calls): the owner's requested changes
  were never made. A failed call still opens the 2 s window, and the debounce
  key ignores the alarm payload, so two alarms set within 2 s lose one.

Tests: run in a throwaway venv with `homeassistant`, `pytest`,
`pytest-asyncio`. 150 pass. Four already fail on upstream main and are unrelated:
`test_auth::test_start_successful`, `test_eight::test_fetch_device_list_successful`,
and two in `test_speaker`.

Also seen on upstream that day: `prepare-1.0.25-release` (no new commits over
main), and a bot branch `feature/pr-analysis-consolidated-report-…` with an
analysis of old PRs #113, #118 and #120. Not reviewed.

## 2026-11-06: no new upstream activity

The 13 PRs logged on 2026-11-03 are still open upstream; nothing merged and
no new PRs. `upstream/main` is unchanged at `1f5d84e`.
