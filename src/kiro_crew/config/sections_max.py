"""MAX is disabled by default and has exactly one numeric owner."""

from dataclasses import dataclass, field

from kiro_crew.config.fields import _meta


@dataclass
class MaxConfig:
    enabled: bool = field(
        default=False, metadata=_meta("Enabled", "Enable the owner-only MAX channel.")
    )
    delivery_mode: str = field(
        default="polling",
        metadata=_meta(
            "Delivery mode",
            "polling for development; webhook for production. Subscription is configured separately.",
        ),
    )
    allowed_user_ids: list[int] = field(
        default_factory=list,
        metadata=_meta("Owner", "Exactly one numeric owner. Empty denies everyone until paired."),
    )
