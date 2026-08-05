from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


SUPPORTED_AUTHORITY_STAGES = frozenset({"legacy", "shadow-read"})
CapabilityName = Literal[
    "legacy_holding_writes",
    "shadow_diagnostics",
    "risk_budget_reads",
    "risk_plan_previews",
    "risk_covered_position_creation",
    "position_lifecycle_writes",
    "csv_portability",
    "webhook_delivery",
    "browser_notifications",
    "desktop_notifications",
    "ai_holding_reviews",
]


@dataclass(frozen=True)
class RuntimeCapabilities:
    legacy_holding_writes: bool = False
    shadow_diagnostics: bool = False
    risk_budget_reads: bool = False
    risk_plan_previews: bool = False
    risk_covered_position_creation: bool = False
    position_lifecycle_writes: bool = False
    csv_portability: bool = False
    webhook_delivery: bool = False
    browser_notifications: bool = False
    desktop_notifications: bool = False
    ai_holding_reviews: bool = False


@dataclass(frozen=True)
class RuntimePolicy:
    authority_stage: str
    stable_runtime_supported: bool
    capabilities: RuntimeCapabilities


_POLICIES = {
    "legacy": RuntimeCapabilities(
        legacy_holding_writes=True,
        risk_budget_reads=True,
        risk_plan_previews=True,
        browser_notifications=True,
        desktop_notifications=True,
        ai_holding_reviews=True,
    ),
    "shadow-read": RuntimeCapabilities(
        legacy_holding_writes=True,
        shadow_diagnostics=True,
        risk_budget_reads=True,
        risk_plan_previews=True,
        browser_notifications=True,
        desktop_notifications=True,
        ai_holding_reviews=True,
    ),
    # The stable application still rejects this stage at readiness. These flags
    # describe only the isolated APIs that already exist for migration testing.
    "new-authoritative": RuntimeCapabilities(
        risk_budget_reads=True,
        risk_plan_previews=True,
        risk_covered_position_creation=True,
    ),
}


def runtime_policy(stage: str) -> RuntimePolicy:
    return RuntimePolicy(
        authority_stage=stage,
        stable_runtime_supported=stage in SUPPORTED_AUTHORITY_STAGES,
        capabilities=_POLICIES.get(stage, RuntimeCapabilities()),
    )


def capability_available(stage: str, capability: CapabilityName) -> bool:
    return bool(getattr(runtime_policy(stage).capabilities, capability))


@dataclass(frozen=True)
class UnsupportedRuntimeOperation(RuntimeError):
    error_code: str
    message: str
    feature: str | None = None

    def __str__(self) -> str:
        return self.error_code


def reject_cutover() -> None:
    raise UnsupportedRuntimeOperation(
        error_code="cutover_not_supported",
        message="当前稳定版本不支持切换到 new-authoritative；请恢复切换前备份。",
        feature="authority_cutover",
    )


def feature_not_supported(feature: str) -> dict[str, str]:
    return {
        "message": "当前稳定版本不支持此功能",
        "error_code": "feature_not_supported",
        "feature": feature,
    }


def authority_readiness(stage: str) -> tuple[bool, dict[str, str]]:
    if runtime_policy(stage).stable_runtime_supported:
        return True, {}
    return False, {
        "reason": "unsupported_authority_stage",
        "error_code": "new_authority_not_supported",
        "recovery": "停止服务并恢复经验证的切换前备份，然后重新启动。",
    }
