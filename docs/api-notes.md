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
| Account and device list | `GET {client}/v1/users/me` | Seen 2026-09-18 |
| Everything about a pod | `GET {client}/v1/devices/{deviceId}` | Seen 2026-09-18 |
| Cheap field subset | `GET {client}/v1/devices/{id}?filter=leftUserId,rightUserId,awaySides` | In code |
| Current device / side | `GET {client}/v1/users/{userId}/current-device` | In code |
| User profile | `GET {client}/v1/users/{userId}` | Seen 2026-09-19 |
| Sleep history | `GET {client}/v1/users/{userId}/trends?tz=…&from=YYYY-MM-DD&to=…&include-main=false&include-all-sessions=true&model-version=v2` | Seen 2026-10-05 |
| Households (device picker) | `GET {app}/v1/household/users/{userId}/summary` | In code |
| Subscriptions | `GET {app}/v1/users/{userId}/subscriptions` | Seen 2026-09-24 |
| Temperature state | `GET {app}/v1/users/{userId}/temperature` | In code |
| All zones + schedules | `GET {app}/v1/users/{userId}/temperature/all` | Seen 2026-09-22 |
| Pillow zone | `GET {app}/v1/users/{userId}/temperature/pillow` | Seen 2026-11-03 |
| Alarms | `GET {app}/v2/users/{userId}/alarms` | Seen 2026-09-21 |
| Routines | `GET {app}/v2/users/{userId}/routines` | In code |
| Adjustable base | `GET {app}/v1/users/{userId}/base` | In code |
| Speaker probe (Pod 5) | `GET {app}/v1/users/{userId}/audio/player` (404 = no speaker) | In code |
| Audio tracks | `GET {app}/v1/users/{userId}/audio/tracks` | In code |
| Away mode | `GET {app}/v1/users/{userId}/away-mode` → `{"isAway": false}` | Seen 2026-11-03 |
| Autopilot state | `GET {app}/v1/users/{userId}/autopilotDetails` | Seen 2026-11-03 |
| Autopilot temperature events | `GET {app}/v1/users/{userId}/temp-events?from=…&to=…` | Unverified (upstream #168) |
| Bedtime recommendation | `GET {app}/v1/users/{userId}/bedtime/recommendation` | Unverified (upstream #169) |
| Water insert maintenance | `GET {app}/v1/user/{userId}/device_maintenance/maintenance_insert?v=2` (note singular `user`) | Unverified (upstream #171) |
| Level suggestions | `GET {app}/v1/users/{userId}/level-suggestions` | Seen 2026-11-03 |
| Streak challenges | `GET {app}/v1/users/{userId}/challenges` | Seen 2026-11-03 |
| Travel | `GET {app}/v1/users/{userId}/travel/trips` | Seen 2026-11-03 |

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
- `temperatureSettings` can't be emptied. `DELETE …/temperature` and
  `DELETE …/temperature/{profile}` are **405**; the other attempts are 404 or
  200 with no change. The nearest reset is smart levels 0/0/0 and
  `{"schedules": []}`. (Seen 2026-09-21.)

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
