from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Diagnosis:
    text: str
    rationale: str


class DiagnosisProvider(Protocol):
    def diagnose(self, failure: object) -> Diagnosis:
        raise NotImplementedError


class TemplateDiagnosisProvider:
    """Deterministic diagnosis provider for the hackathon vertical slice."""

    _TEMPLATES = {
        "check_that_local_does_not_exist": Diagnosis(
            text=(
                "The app package contains a local/ directory. AppInspect blocks this "
                "because local configuration is instance-specific and should not ship "
                "inside a distributable Splunk app."
            ),
            rationale=(
                "Remove local/ from the packaged working copy and keep distributable "
                "defaults under default/."
            ),
        ),
        "check_user_seed_conf_deny_list": Diagnosis(
            text=(
                "The app ships default/user-seed.conf. AppInspect blocks this because "
                "app-delivered default credentials are not allowed for Splunk Cloud."
            ),
            rationale=(
                "Remove default/user-seed.conf; user provisioning belongs to Splunk "
                "authentication, not app package content."
            ),
        ),
        "check_if_outputs_conf_exists": Diagnosis(
            text=(
                "The app ships default/outputs.conf with forwarding enabled. AppInspect "
                "blocks this because packaged apps must not configure external forwarding "
                "by default."
            ),
            rationale=(
                "Remove default/outputs.conf from the package so the app cannot silently "
                "redirect data to external indexers."
            ),
        ),
    }

    def diagnose(self, failure: object) -> Diagnosis:
        check = getattr(failure, "check", "")
        return self._TEMPLATES.get(
            check,
            Diagnosis(
                text=f"AppInspect reported {check or 'an unsupported check'} as a failure.",
                rationale=(
                    "No free-form file edit is attempted; only deterministic patchers "
                    "from the registry may change files."
                ),
            ),
        )
