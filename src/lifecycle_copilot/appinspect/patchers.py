from __future__ import annotations

import shutil
from pathlib import Path

from lifecycle_copilot.self_heal import PatchResult

from .parser import AppInspectFailure


class AppInspectPatchError(RuntimeError):
    pass


PATCH_PRIORITY = (
    "check_that_local_does_not_exist",
    "check_user_seed_conf_deny_list",
    "check_if_outputs_conf_exists",
)


def select_appinspect_failure(failures: list[AppInspectFailure] | tuple[AppInspectFailure, ...]):
    for check in PATCH_PRIORITY:
        for failure in failures:
            if failure.check == check:
                return failure
    checks = ", ".join(sorted({failure.check for failure in failures}))
    raise AppInspectPatchError(f"No deterministic AppInspect patcher for failures: {checks}")


def apply_appinspect_patch(app_dir: Path, failure: AppInspectFailure) -> PatchResult:
    patcher = PATCHERS.get(failure.check)
    if patcher is None:
        raise AppInspectPatchError(f"No deterministic AppInspect patcher for {failure.check}")
    return patcher(Path(app_dir))


def safe_child_path(root: Path, relative_path: str) -> Path:
    resolved_root = Path(root).resolve()
    target = (resolved_root / relative_path).resolve()
    if not target.is_relative_to(resolved_root):
        raise AppInspectPatchError(f"Refusing to patch outside app root: {relative_path}")
    return target


def _remove_local_dir(app_dir: Path) -> PatchResult:
    target = safe_child_path(app_dir, "local")
    if not target.exists():
        return PatchResult(
            patch_id="appinspect.remove_local_dir",
            summary="local/ already absent from working copy.",
        )
    if not target.is_dir():
        raise AppInspectPatchError(f"Expected local/ to be a directory: {target}")
    shutil.rmtree(target)
    return PatchResult(
        patch_id="appinspect.remove_local_dir",
        summary="Removed packaged local/ directory from the working copy.",
        changed_paths=("local/",),
    )


def _remove_user_seed(app_dir: Path) -> PatchResult:
    return _remove_file(
        app_dir,
        "default/user-seed.conf",
        patch_id="appinspect.remove_user_seed",
        summary="Removed default/user-seed.conf from the working copy.",
    )


def _remove_outputs(app_dir: Path) -> PatchResult:
    return _remove_file(
        app_dir,
        "default/outputs.conf",
        patch_id="appinspect.remove_outputs_conf",
        summary="Removed default/outputs.conf from the working copy.",
    )


def _remove_file(app_dir: Path, relative_path: str, *, patch_id: str, summary: str) -> PatchResult:
    target = safe_child_path(app_dir, relative_path)
    if not target.exists():
        return PatchResult(
            patch_id=patch_id,
            summary=f"{relative_path} already absent from working copy.",
        )
    if not target.is_file():
        raise AppInspectPatchError(f"Expected {relative_path} to be a file: {target}")
    target.unlink()
    return PatchResult(
        patch_id=patch_id,
        summary=summary,
        changed_paths=(relative_path,),
    )


PATCHERS = {
    "check_that_local_does_not_exist": _remove_local_dir,
    "check_user_seed_conf_deny_list": _remove_user_seed,
    "check_if_outputs_conf_exists": _remove_outputs,
}
