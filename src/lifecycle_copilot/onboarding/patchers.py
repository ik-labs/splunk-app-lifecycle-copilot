from __future__ import annotations

from lifecycle_copilot.self_heal import PatchResult

from .models import OnboardingFailure


PATCH_PRIORITY = (
    "field_coverage_gap",
    "timestamp_coverage_gap",
    "cim_mapping_gap",
    "pii_flag_gap",
)


class OnboardingPatchError(RuntimeError):
    pass


class CandidateState:
    def __init__(self, candidate_id: str = "candidate-00") -> None:
        self.candidate_id = candidate_id


def select_onboarding_failure(
    failures: list[OnboardingFailure] | tuple[OnboardingFailure, ...],
) -> OnboardingFailure:
    for check in PATCH_PRIORITY:
        for failure in failures:
            if failure.check == check:
                return failure
    checks = ", ".join(sorted({failure.check for failure in failures}))
    raise OnboardingPatchError(f"No deterministic onboarding patcher for failures: {checks}")


def apply_onboarding_patch(state: CandidateState, failure: OnboardingFailure) -> PatchResult:
    if failure.check not in PATCH_PRIORITY:
        raise OnboardingPatchError(f"No deterministic onboarding patcher for {failure.check}")

    previous = state.candidate_id
    state.candidate_id = "candidate-01"
    if previous == "candidate-01":
        return PatchResult(
            patch_id="onboarding.use_key_value_candidate",
            summary="Robust key/value extraction candidate was already active.",
        )
    return PatchResult(
        patch_id="onboarding.use_key_value_candidate",
        summary=(
            "Replaced naive positional extraction with robust key/value extraction, "
            "CIM aliases, timestamp handling, and PII flags."
        ),
        changed_paths=("onboarding/candidate-01.spl",),
    )
