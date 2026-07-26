from __future__ import annotations

from dataclasses import dataclass


SUPPORTED_AUTHORITY_STAGES = frozenset({"legacy", "shadow-read"})


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
    if stage in SUPPORTED_AUTHORITY_STAGES:
        return True, {}
    return False, {
        "reason": "unsupported_authority_stage",
        "error_code": "new_authority_not_supported",
        "recovery": "停止服务并恢复经验证的切换前备份，然后重新启动。",
    }
