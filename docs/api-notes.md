# Eight Sleep API notes

What this fork knows about the private Eight Sleep API: every endpoint the
vendored `pyEight` calls, plus the gotchas found by running a fleet of Pod 4
and Pod 5 beds against it.

**The live API beats this file.** Nothing here came from Eight Sleep. It is a
reverse-engineered mobile-app API with no docs and no versioning promise. If
you see the API behave differently, the API is right: fix this file in the same
change and put the date on the line. "Seen 2026-09-19" tells the next reader how
stale a claim is; a confident sentence with no date doesn't.

Each claim is marked one of three ways:

- **Seen _date_**: observed live on real accounts on that date.
- **In code**: the client calls it and it works for users, but nobody here has
  checked the response shape by hand.
- **Unverified**: comes from an upstream PR; not yet read live.

## Why there is no official client

Home Assistant removed its built-in Eight Sleep integration in October 2023
([home-assistant/core#102669](https://github.com/home-assistant/core/pull/102669)).
The API had moved to OAuth, and there is no way to apply for your own client
keys. `mezz64/pyEight`, built for the old API, was archived on 2026-03-13. Every
working client, this one included, reuses the mobile app's client id and secret.

**`pip install pyeight` installs the dead 0.3.2 from 2022.** The PyPI name still
belongs to the original author. Vendor the source from this repo instead.

## Hosts

| Host | Carries |
| --- | --- |
| `auth-api.8slp.net` | tokens only |
| `client-api.8slp.net` | users, devices, trends |
| `app-api.8slp.net` | temperature, alarms, away mode, subscriptions, priming, audio, base, autopilot |

**A path on the wrong host answers 404 with an HTML page.** That, not a wrong
path, is the usual cause of a JSON parse error. Priming, for example, is on
`app-api`; on `client-api` it 404s. (Seen 2026-09-19.)

In the code: `AUTH_URL`, `CLIENT_API_URL` (includes `/v1`), `APP_API_URL`
(ends in `/`, no version) in `pyEight/constants.py`.

## Auth

`POST {auth}/v1/tokens` with `client_id`, `client_secret`,
`grant_type: "password"`, `username`, `password`.

- Returns a JWT `access_token` that lasts **20 hours** (`expires_in: 72000`),
  plus a `refresh_token`. The JWT's `sub` claim is the user id. (Seen 2026-09-18.)
- Bad email or password: **400 `invalid_grant`**.
- **Rate limited: 429 under back-to-back logins.** Four or five logins in a row
  with no pause got answers; every attempt after that got 429. Pausing ~4 s
  between accounts and backing off 30 s on a 429 got most through. It is a
  throttle, not a ban. (Seen 2026-09-19.) Cache tokens; don't log in per poll.
- A kept token that Eight Sleep refuses early answers **401**. Log in once more.
  This client does that (`401 → re-login` retry in `eight.py`).
- **403 is not an expired token.** It means this token may not read that
  resource. See subscriptions and alarms below.
- Every token carries `write_device`. There is no read-only scope.
- Send `User-Agent: okhttp/4.9.3`, the mobile app's, to stay on the same server
  path the app gets.

**If the client id, secret or user-agent ever change here, every other client
using the same pair breaks at once.** Mirror the change everywhere on the same
day.

## Endpoints

`{client}` = `https://client-api.8slp.net`, `{app}` = `https://app-api.8slp.net`.

### Reads

| Purpose | Request | Status |
| --- | --- | --- |
| Account and device list | `GET {client}/v1/users/me` | Seen 2026-11-06 |
| Everything about a pod | `GET {client}/v1/devices/{deviceId}` | Seen 2026-11-06 |
| Cheap field subset | `GET {client}/v1/devices/{id}?filter=leftUserId,rightUserId,awaySides` | Seen 2026-11-06 |
| Current device / side | `GET {client}/v1/users/{userId}/current-device` → `id`, `side`, `specialization`, `timeZone` | Seen 2026-11-06 |
| User profile | `GET {client}/v1/users/{userId}` | Seen 2026-11-06 |
| Sleep history | `GET {client}/v1/users/{userId}/trends?tz=…&from=YYYY-MM-DD&to=…&include-main=false&include-all-sessions=true&model-version=v2` | Seen 2026-11-06 |
| Households (device picker) | `GET {app}/v1/household/users/{userId}/summary` → `currentSet`, `households` | Seen 2026-11-06 |
| Subscriptions | `GET {app}/v1/users/{userId}/subscriptions` | Seen 2026-11-06 |
| Temperature state | `GET {app}/v1/users/{userId}/temperature` | Seen 2026-11-06 |
| All zones + schedules | `GET {app}/v1/users/{userId}/temperature/all` | Seen 2026-11-06 |
| Pillow zone | `GET {app}/v1/users/{userId}/temperature/pillow` | Seen 2026-11-06 |
| Alarms | `GET {app}/v2/users/{userId}/alarms` → `alarms`, `recommendedAlarm` | Seen 2026-11-06 |
| Routines | `GET {app}/v2/users/{userId}/routines` → `settings`, `state` | Seen 2026-11-06 |
| Adjustable base | `GET {app}/v1/users/{userId}/base` (404 with no base) | Seen 2026-11-06 (404 only) |
| Speaker probe (Pod 5) | `GET {app}/v1/users/{userId}/audio/player` (404 = no speaker) | Seen 2026-11-06 (404 only) |
| Audio tracks | `GET {app}/v1/users/{userId}/audio/tracks` | Seen 2026-11-06 |
| Away mode | `GET {app}/v1/users/{userId}/away-mode` → `{"isAway": false}` | Seen 2026-11-06 |
| Autopilot state | `GET {app}/v1/users/{userId}/autopilotDetails` | Seen 2026-11-06 |
| Autopilot temperature events | `GET {app}/v1/users/{userId}/temp-events?from=…&to=…` (full ISO timestamps; bare dates are 400) → `events`, `phases` | Seen 2026-11-06 |
| Bedtime recommendation | `GET {app}/v1/users/{userId}/bedtime/recommendation` → `daysAnalyzed`, `recommendedBedtime`, `standardDeviation`, `topPerformingDays` | Seen 2026-11-06 |
| Water insert maintenance | `GET {app}/v1/user/{userId}/device_maintenance/maintenance_insert?v=2` (note singular `user`) → a list, one entry per device | Seen 2026-11-06 |
| Level suggestions | `GET {app}/v1/users/{userId}/level-suggestions` | Seen 2026-11-06 |
| Streak challenges | `GET {app}/v1/users/{userId}/challenges` | Seen 2026-11-06 |
| Travel | `GET {app}/v1/users/{userId}/travel/trips` | Seen 2026-11-06 |

### Writes

| Purpose | Request | Body | Status |
| --- | --- | --- | --- |
| Create an account | `POST {client}/v1/users` (no auth header) | profile: `email`, `password`, `firstName`, `lastName`, `dob`, `gender`, `zip`, `tempPreference` | Seen 2026-09-19 |
| Edit profile | `PUT {client}/v1/users/{userId}` | any subset; merges | Seen 2026-09-19 |
| Set bed side | `PUT {client}/v1/users/{userId}/current-device` | `{"side": "left"\|"right"\|"solo"}` | In code |
| LED brightness | `PUT {client}/v1/devices/{deviceId}` | `{"ledBrightnessLevel": 0-100}` | Seen 2026-09-19 |
| Prime the pump | `POST {app}/v1/devices/{deviceId}/priming/tasks` | `{"notifications":{"users":["<userId>"],"meta":"rePriming"}}` | Seen 2026-09-19 |
| Heating level | `PUT {app}/v1/users/{userId}/temperature` | `{"currentLevel": n}`, `{"timeBased":{"level":n,"durationSeconds":s}}` | In code |
| Smart stage levels | `PUT {app}/v1/users/{userId}/temperature` | `{"smart":{"bedTimeLevel","initialSleepLevel","finalSleepLevel"}}` | Seen 2026-09-19 |
| Side on / off | `PUT {app}/v1/users/{userId}/temperature` | `{"currentState":{"type":"smart"\|"off"}}` | Seen 2026-09-19 |
| Pillow | `PUT {app}/v1/users/{userId}/temperature/pillow` | `{"currentLevel": n}` | In code |
| Bedtime schedules | `PUT {app}/v1/users/{userId}/bedtime` | `{"schedules":[…]}`; replaces the whole set | Seen 2026-09-20 |
| Away mode | `PUT {app}/v1/users/{userId}/away-mode` | `{"awayPeriod":{"start"\|"end":"<ISO>"}}` | In code |
| Create one-off alarm | `POST {app}/v1/users/{userId}/alarms` | `time` (string), `enabled`, `vibration`, `thermal` | In code |
| Edit alarm | `PUT {app}/v1/users/{userId}/alarms/{alarmId}` | alarm fields | In code |
| Delete alarm | `DELETE {app}/v1/users/{userId}/alarms/{alarmId}` | none | Seen 2026-09-21 |
| Snooze / dismiss | `PUT {app}/v1/users/{userId}/alarms/{id}/snooze` \| `/dismiss` | | In code |
| Base angle / preset | `POST {app}/v1/users/{userId}/base/angle?ignoreDeviceErrors=false` | angle payload | In code |
| Speaker | `PUT {app}/v1/users/{userId}/audio/player/state` \| `/volume` \| `/currentTrack` | | In code |

### Paths that don't work

All seen 2026-11-03 unless dated otherwise.

- `autopilot-details` (kebab-case) is **404**; only `autopilotDetails` works.
- `GET {app}/v1/users/{id}/bedtime` is **405**. It is write-only.
- `DELETE {app}/v2/users/{id}/alarms/{id}` is **404**. Delete is on `v1` even
  though the list is on `v2`. (Seen 2026-09-21.)
- `GET {app}/v1/users/{id}/temperature/schedules` is **400**, asking for a
  `specialization` it won't take from the query string. Read schedules off
  `temperature/all`. (Seen 2026-09-22.)
- **404** on both hosts: `/health-integrations`, `/feature-flags`, `/settings`,
  `/hot-flash-mode`, `/onboarding`, `/checklist`, `/tasks`, `/preferences`,
  `/experiments`, `{app}/v1/devices/{id}`, `{app}/v1/devices/{id}/settings`.
  Several of these exist one level down; see the app capture below
  (`temperature/hot-flash-mode`, `health-integrations/metadata`,
  `app-state/onboard`, `{app}/v1/devices/{id}/status`).
- `temperatureSettings` can't be emptied. `DELETE …/temperature` and
  `DELETE …/temperature/{profile}` are **405**; the other attempts are 404 or
  200 with no change. The nearest reset is smart levels 0/0/0 and
  `{"schedules": []}`. (Seen 2026-09-21.)

### From an app capture (2026-11-03)

Endpoints the iOS app called on 2026-11-03 and 2026-11-04, captured with a
proxy on one account. Shapes are top-level keys plus enum values seen. These
are **Seen 2026-11-03**, but only from that one account.

**2026-11-06: read live from code** with `scripts/probe_endpoints.py` on a
second account (one pod, no base, no speaker). Every endpoint in this section
answered 200 with the keys listed, except: `{app}/v1/devices/{id}/live` drops
the connection (it is probably a stream, like `events`), and `tags/days` and
`tags/recommendations` answer 400 without query parameters (the right ones are
unknown). Not yet read on an account without a pod, and not with another
account's token.

The client reads five of them, each called live on 2026-11-06 and parsed
correctly:

| Request | Client method |
| --- | --- |
| `{app}/v1/devices/{id}/status` | `EightSleep.device_status()` → `DeviceStatus`, None on 404 |
| `{app}/v1/devices/{id}/priming/tasks/latest` | `EightSleep.latest_prime_task()` → `PrimeTask` with `ran_dry`, None on 404 or no `task` |
| `{app}/v1/devices/{id}/priming/schedule` | `EightSleep.priming_schedule()` → raw list, None on 404 |
| `{app}/v3/users/{id}/subscriptions` | `EightUser.subscription()` → `SubscriptionState`; 403 → `unavailable` |
| `{app}/v1/users/{id}/app-state/onboard` | `EightUser.onboarding_state()` → `OnboardingState`, None on 404 |

To check them live, run `scripts/probe_endpoints.py` (read-only; prints status
and top-level key names, never values or ids).

**Pod health and priming**: the most useful for monitoring a fleet.

| Request | Answers |
| --- | --- |
| `GET {app}/v1/devices/{deviceId}/status` | `status` (`"updating"`, `"ready"` seen), `ready`, `hasWater`, `needsPrime`, `firmwareVersion`, `firmwareUpdated`, `firmwareUpdating`, `lastConnected`, `peripherals` (seen 2026-11-06). A compact health read. Note `needsPrime` here vs `needsPriming` on the device record |
| `GET {app}/v1/devices/{deviceId}/priming/tasks/latest` | `task`: `status` (`finished`), `reason` (`requested` \| `scheduled`), `outcome` (`succeeded` \| `out-of-water`), `outcomeReason` (`flagCleared` \| `noWater`), `created`, `started`, `finished`, `isBlanketPriming`, `coverInfo.label` |
| `GET {app}/v1/devices/{deviceId}/priming/schedule` | `schedule`: a list of strings, one per day, like `"Monday 03:00"` (seen 2026-11-06, 7 entries) |
| `GET {app}/v1/devices/{deviceId}/live` | not answered in the capture; drops the connection when called from code (2026-11-06) |

`outcome: "out-of-water"` on the latest prime is a direct "this bed ran dry"
signal. `reason: "scheduled"` shows pods prime on a schedule as well as on request.

**Subscriptions v3.** The app reads `GET {app}/v3/users/{userId}/subscriptions`,
not v1. On top of `subscriptions` and `primarySubscription` it answers with
computed flags: `hasAccessToPremiumFeatures`, `hasAccessToBasicFeatures`,
`hasBasic`, `isInGracePeriod`, `isUnpaidPremium`, `churned`,
`cancellationReason` (`temporary` \| `user_initiated`), `capabilities: [...]` and
`captureStatus` (`type: "recapture"` plus the lapsed subscription). Each
record adds `status` (`active` \| `inactive`), `provider` (`stripe` \|
`eight_internal`), `subscriptionTier` (`plus` \| `pro`), `subscriptionFrequency`
(`yearly` \| `lifetime`), `gracePeriodEnd`, `lastPaymentDate`, `isRental`,
`ownerUserId`, `subscriberRelationship` (`self`). **This may replace
hand-picking a record by id prefix.** Whether v3 has the same own-token-only
403 as v1 is untested. `POST {app}/v3/users/{userId}/subscriptions/redeem`
takes `{code, userId}`.

Read live 2026-11-06 on a second account: top level had the computed flags
but no `cancellationReason` or `captureStatus` (probably only present on a
churned account). Records also carry `isActive`, `isActiveBasic`,
`isActivePremium`, `inGracePeriod`, `hasBillingFailure`, `type` (`premium`),
`subscriptionProductName`, `createdAt`, `expiresAt`, `willRenew`. That account
had a **new record kind, `pool-seat-<n>`**, with `provider: "pool"`,
`status: "active"`, `willRenew: false` and a future `expiresAt`, as primary
beside an expired `eight-internal-temporary-…` placeholder (`status: "inactive"`).
The id field is `subscriptionId`; there is no `id` key.

The client (2026-11-06) judges v3 by id prefix, not by `status` / `provider`.
`provider: "eight_internal"` covers both the never-paid placeholder and the
granted membership, and nobody has seen `status` on a granted record. A pool
seat is judged by `expiresAt` alone, because `willRenew` is false while it is
live. The computed flags are passed through raw.

**Onboarding state exists after all.** `GET {app}/v1/users/{userId}/app-state/onboard`
→ `{"value": {lastOnboardTime, testDriveCompletedTimestamp, pod5TestDriveCompletedTimestamp}}`,
and the app writes it with `PATCH {app}/v1/users/{userId}/app-state/onboard`
and the same body: `{"value": {"lastOnboardTime": "<ISO>", "testDriveCompletedTimestamp": "<ISO>", "pod5TestDriveCompletedTimestamp": "<ISO>"}}`.
Whether a `PATCH` merges keys inside `value` or replaces it is unknown. This
client reads it only and has no write. This is likely what the phone's "test
drive" nag reads. `app-state/messages` (GET/PUT
`{"value": ...}`) is the same pattern.

**Other reads seen:**

| Request | Answers |
| --- | --- |
| `GET {auth}/v1/grants` | `grants: [...]` |
| `GET {client}/v1/users/{userId}/intervals?next=…` | Sleep sessions, paged: `stageSummary`, `stages`, `timeseries` (`heartRate`, `hrv`, `rmssd`, `respiratoryRate`, `tempBedC`, `tempRoomC`, `heating`, `tnt`, …), `score`, `device.{id,side,specialization}` |
| `GET {client}/v1/users/{userId}/temperature` | `currentLevel`, `currentState`, `currentSchedule`, `nextSchedule`, `nextBedtimeDisplayWindow`, `settings` (on `client-api`, not just `app-api`) |
| `GET {app}/v1/users/{userId}/release-features` | Per-account feature flags: `autoPriming`, `primingCancellation`, `enableHotFlashMode`, `enableMultipodV3`, `enableSensorDisconnectWarning`, `deviceAlarmSupport`, `supportedPatterns`, … (~90 keys) |
| `GET {app}/v1/users/{userId}/temperature/hot-flash-mode` | `enabled`, `hotFlashDuration` (`"0:15:00"`), `levelDelta` |
| `GET {app}/v1/users/{userId}/active-mode` | `mode` (`standard` seen) |
| `GET {app}/v1/users/{userId}/level-suggestions-mode` | `autopilotEnabled`, `autopilotMode`, `autopilotOptions` |
| `GET {app}/v1/users/{userId}/autopilotDetails/autopilotRecap?day=…&tz=…` | Per-night temperature, pillow and elevation adjustment counts and lists, `isProcessingComplete` |
| `GET {app}/v1/users/{userId}/days/count` | `count` (nights recorded) |
| `GET {app}/v1/users/{userId}/devices/all/tap-settings` | Per-device double/quad-tap actions and options |
| `GET {app}/v1/users/{userId}/notifications?active&limit` | `notifications`, `pagination.{cursor,hasMore,limit}` |
| `GET {app}/v1/users/{userId}/metrics/summary?from&to&tz&metrics&periods` | `days` |
| `GET {app}/v1/users/{userId}/metrics/aggregate?to&tz&metrics&periods` | `periods` |
| `GET {app}/v1/users/{userId}/insights?date=…`, `/llm-insights?from&to`, `/llm-insights/settings` | Insight text; settings are `length`, `tone` |
| `GET {app}/v1/users/{userId}/tags/days`, `/tags/recommendations`, `/truth-tags` | Sleep tags |
| `GET {app}/v1/users/{userId}/health-integrations/metadata` | Connected health sources and sync summary |
| `GET {app}/v1/intelligence/{userId}/podai/bio-age[/trend]` | Biological age estimate |
| `GET {app}/v1/sms/users/{userId}` | SMS enrolment (404 when not enrolled) |
| `GET {app}/v1/health-survey/test-drive`, `/v1/audio/categories`, `/v2/users/{userId}/referral/campaigns` | App content |
| `GET {app}/v1/users/{userId}/events` | **101 Switching Protocols**: a websocket for live events |

**Writes seen:** `PUT {app}/v1/users/{userId}/temperature/pod?ignoreDeviceErrors=…`
with `{"currentLevel": n}` (200); `PUT {app}/v1/users/{userId}/temperature/all`
with `currentState` (400 in the capture); `PUT {client}/v1/users/me?enableValidation=…`
with `devices`, `notifications`; push-target registration under
`{client}/v1/users/me/push-targets/…`; health-data upload under
`{app}/v1/users/{userId}/health-integrations/sources/…` and
`{app}/v2/users/{userId}/health-integrations/sources/apple-health/batches`.

## Gotchas

### A 200 is not proof a write landed

- **LED writes in a burst can answer 200, echo the value, and still be lost.**
  A later write can be overtaken by an earlier one, and the pod settles on
  something else. Only a fresh GET confirms. Read back and retry. (Seen 2026-09-19.)
- **Device-keyed writes on an account with no pod answer 200 and do nothing.**
  Smart levels and bedtime schedules have no device to hang off. (Seen 2026-09-20.)
- **One smart-levels write answered 404 and still took.** Only the read-back
  counts. (Seen 2026-11-03.)
- An offline pod is expected to take a write with 200 and change nothing.
  Untested.

### Subscription gates (403)

- `PUT …/bedtime` answers **403 `{"message":"Subscription required."}`** on an
  unpaid account. It didn't the day before. (Seen 2026-09-20.)
- `GET {app}/v2/users/{id}/alarms` answered **403** on 2 of 30 accounts, and not
  on a simple paid/unpaid split. Treat 403 as a fact about the account, not a
  bad request. (Seen 2026-09-21.)
- Writing `autopilotEnabled: true` via the profile `PUT` succeeded on every
  account tried, paid or not. Whether that is the same switch the app calls
  Autopilot is unconfirmed. (Seen 2026-11-03.)

### A pod re-paired to another account stays readable by the old one

After a pod moves to a new account, the old account's token still reads
`GET {client}/v1/devices/{id}` with **200** and the full record.
`GET {client}/v1/users/me` on the old account shows `devices: []`, and that is
the only place it shows as gone. **`result.ownerId` names the new owner**, and
it is the only field that says whose bed it is. How long the old account keeps
read access is unknown. (Seen 2026-09-20.)

### Firmware fields

- **`firmwareUpdated` is the hub's last report, not a comparison with the
  latest release.** Offline Pod 4s on old builds read `true`. Four online Pod 5s
  read `firmwareUpdated: false, firmwareUpdating: true` while the rest of the
  fleet was a build ahead. (Seen 2026-11-03.) The Firmware Updating binary
  sensor (upstream #156) reports exactly this, so "updating" can stay on for days.
- `lastFirmwareUpdateStart` is always the epoch (`1970-01-01`). Ignore it.
- There is no call to start an update. Eight Sleep pushes them.

### Water and priming

- **`hasWater` is the field that reports a dry reservoir.** `needsPriming`
  stayed `false` on a pod that had just gone dry. (Seen 2026-09-19.)
- **Priming is how a pod finds out it is short of water.** A part-full tank
  reads `hasWater: true` until a prime circulates it. Then it reads `false`.
- A prime takes about 2 minutes. `priming` turns `true` 15–30 s after the 200,
  not straight away.
- `lastLowWater` tracks the latest reading, not when the pod went dry.
- `lastPrime` can be months old on a healthy pod, and can be missing. This
  client returns `None` then.
- `isTemperatureAvailable` tracked `hasWater` exactly on four pods.
- Nothing distinguishes a removed tank from an empty one.

### Subscriptions

`GET {app}/v1/users/{userId}/subscriptions` →
`{ "subscriptions": [...], "primarySubscription": {...} }`

- **Only the account's own token can read it. Any other token gets 403.** On a
  two-user bed, the partner's side can't be read with the main token: show it
  as unavailable, not "no subscription". (Seen 2026-09-24.)
- **`primarySubscription` is absent when nothing is live.** Reading only it
  turns a lapsed, billing-failed account into "unknown". (Seen 2026-09-19.)
- Picking a record: the primary if present → else the newest **bought** record
  (`sub_…`, Stripe) → else a placeholder. A lapsed purchase can sit beside a
  newer placeholder; newest-wins picks the wrong one. (Seen 2026-09-24.)
- Record kinds, by id prefix:
  - `sub_…`: a Stripe purchase. Can carry `hasBillingFailure: true`.
  - `pool-seat-<n>`: a seat from a pooled plan, `provider: "pool"`.
    `willRenew: false` even while live, so judge it by `expiresAt` only.
    (Seen 2026-11-06, on v3.)
  - `eight-internal-temporary-<uuid>`: account created, never paid.
    `isActive: false`, `expiresAt == createdAt`.
  - `exclusive-member-<uuid>`: membership granted by Eight Sleep.
    `isActive: true`, `willRenew: false`, **no `expiresAt` key at all**.
    Treat as active and open-ended. (Seen 2026-10-05.)
- **Judge by `expiresAt`, not `willRenew`.** Granted memberships never renew.
- An account can return an empty list and no primary. That's "unknown".

### Accounts

- `POST {client}/v1/users` is unauthenticated and answers **201** with a live
  session. No email verification. A duplicate address answers **409**.
  (Seen 2026-09-19, 2026-10-14.)
- `tempPreference` in the creation body is dropped. Only the profile `PUT`
  makes it stick. (Seen 2026-09-20.)
- `zip` reads back as a number even when written as a string. (Seen 2026-09-25.)
- Pairing a pod from the phone asks for birthday and ZIP code again.
- On an account with no pod, `temperature/all` omits `schedules` entirely
  rather than returning `[]`. Check for the key before the length. (Seen 2026-09-22.)

### Trends

- **Most beds have no sleep data.** An account nobody slept on as that user
  answers 200 with `days: []`; half of one fleet did. Build on device health,
  not sleep metrics. (Seen 2026-10-05.)
- Each day carries `score`, `sleepQualityScore`, `sleepRoutineScore`,
  `sleepDuration`, `presenceDuration` (seconds), `presenceStart`/`presenceEnd`,
  `sleepStart`/`sleepEnd` (UTC ISO), `deepPercent`, `remPercent` (fractions),
  `deep/light/remDuration`, snore fields, `tnt`, `sessions`, `sessionIds`.
  (Seen 2026-10-05.)
- Fields the upstream sensor PRs read (unverified by hand):
  - Snoring (#165): `snoreDuration`, `snorePercent`, `heavySnoreDuration`, `heavySnorePercent`
  - Latency and debt (#166): `sleepRoutineScore.latencyAsleepSeconds.current`, `sleepRoutineScore.latencyOutSeconds.current`, `sleepQualityScore.sleepDebt.dailySleepDebtSeconds` (can be negative; ignore while `isCalibrating`)
  - Base snore mitigation (#167): `mitigationEvents`, `snoringReductionPercent`, `elevationDuration`
  - Personal range (#170): `sleepQualityScore.<metric>` → `current`, `lowerRange`, `upperRange`, `inclusive7DayAverage` for `heartRate`, `hrv`, `respiratoryRate`
  - Measured bed temperature (#164): `tempBedC` in the session timeseries
  - Performance windows (#169): under `performanceWindows` (check `isAvailable`): `exerciseWindow`, `cognitiveWindow`, `chronotype.chronoClass`, `socialJetlag.socialJetlagSeconds`

### Device record (`GET {client}/v1/devices/{id}`)

One call returns online state, `lastHeard`, `wifiInfo` (SSID, IP, MAC, signal
in dBm), both serials, firmware, water and priming state, LED level, per-side
heating state and schedules, `ownerId`, `timezone` (per device, not per
account) and `features`.

- `hubSerial` is the hub (pump unit); `sensorInfo.serialNumber` is the cover.
  **A serial's prefix doesn't tell you which one it is.** Match a printed serial
  against both. (Seen 2026-09-20.)
- `modelString` is `Pod 4` / `Pod 5`.
- A Pod 5 lists `buttonControls` in `features` where a Pod 4 lists
  `tapControls`. (Seen 2026-09-19.)
- Cover faults (`sides.*.fault`) stayed `false` on a dry pod. Don't expect a
  dry hub to raise one.
- Heating levels run −100…+100, negative is cooling. They are not degrees;
  `util.py` has lookup tables.

## Keeping up with upstream

This fork tracks [lukas-clarke/eight_sleep](https://github.com/lukas-clarke/eight_sleep).
The log of what was carried over, skipped, and why is in
[`docs/upstream-log.md`](upstream-log.md).
