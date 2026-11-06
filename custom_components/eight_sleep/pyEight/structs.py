from dataclasses import dataclass
from datetime import datetime


@dataclass
class Token:
    bearer_token: str
    expiration: float
    main_id: str


@dataclass
class DeviceStatus:
    """A compact health read of the pod.

    From `GET {app}/v1/devices/{deviceId}/status`. Any field the API leaves
    out is None.
    """

    status: str | None
    ready: bool | None
    has_water: bool | None
    needs_prime: bool | None
    firmware_version: str | None
    firmware_updated: bool | None
    firmware_updating: bool | None
    last_connected: datetime | None


@dataclass
class OnboardingState:
    """What the app recorded about a user's onboarding.

    From `GET {app}/v1/users/{userId}/app-state/onboard`. Both fields are None
    when the answer has no `value`.
    """

    last_onboard_time: datetime | None
    test_drive_completed: bool | None


@dataclass
class PrimeTask:
    """The pod's latest priming task.

    From `GET {app}/v1/devices/{deviceId}/priming/tasks/latest`. Any field the
    API leaves out is None.
    """

    status: str | None
    reason: str | None
    outcome: str | None
    outcome_reason: str | None
    created: datetime | None
    started: datetime | None
    finished: datetime | None

    @property
    def ran_dry(self) -> bool | None:
        """True when the prime ended because the bed ran out of water."""
        if self.outcome is None:
            return None
        return self.outcome == "out-of-water"
