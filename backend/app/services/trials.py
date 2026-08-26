import enum
from datetime import UTC, datetime

from app.db.models import User


class AccessState(str, enum.Enum):
    TRIAL_ACTIVE = "TRIAL_ACTIVE"
    TRIAL_EXPIRED = "TRIAL_EXPIRED"
    SUBSCRIBED = "SUBSCRIBED"
    ACCESS_EXPIRED = "ACCESS_EXPIRED"


class TrialService:
    """Determine access state without implementing subscription payment logic."""

    def determine_access_state(
        self,
        user: User,
        now: datetime | None = None,
        *,
        is_subscribed: bool = False,
    ) -> AccessState:
        if is_subscribed:
            return AccessState.SUBSCRIBED

        current_time = now or datetime.now(UTC)
        if user.trial_ends_at is None:
            return AccessState.ACCESS_EXPIRED
        if current_time < user.trial_ends_at:
            return AccessState.TRIAL_ACTIVE
        return AccessState.TRIAL_EXPIRED
