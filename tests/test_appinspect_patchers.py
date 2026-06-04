from pathlib import Path

import pytest

from lifecycle_copilot.appinspect.parser import AppInspectFailure
from lifecycle_copilot.appinspect.patchers import (
    AppInspectPatchError,
    apply_appinspect_patch,
    safe_child_path,
)


def make_failure(check: str, file: str | None) -> AppInspectFailure:
    return AppInspectFailure(
        failure_id=f"appinspect:{check}:{file or 'app'}",
        group="test_group",
        check=check,
        file=file,
        line=None,
        message="test failure",
        messages=(),
        raw_check={},
    )


def make_app(tmp_path: Path) -> Path:
    app = tmp_path / "broken_app"
    (app / "local").mkdir(parents=True)
    (app / "local" / "app.conf").write_text("[install]\n", encoding="utf-8")
    (app / "default").mkdir()
    (app / "default" / "app.conf").write_text("[launcher]\n", encoding="utf-8")
    (app / "default" / "user-seed.conf").write_text("[user_info]\n", encoding="utf-8")
    (app / "default" / "outputs.conf").write_text("[tcpout]\ndefaultGroup=x\n", encoding="utf-8")
    return app


@pytest.mark.parametrize(
    ("check", "target", "survivor"),
    [
        ("check_that_local_does_not_exist", "local", "default/user-seed.conf"),
        ("check_user_seed_conf_deny_list", "default/user-seed.conf", "default/outputs.conf"),
        ("check_if_outputs_conf_exists", "default/outputs.conf", "default/user-seed.conf"),
    ],
)
def test_patchers_remove_only_their_target(
    tmp_path: Path,
    check: str,
    target: str,
    survivor: str,
) -> None:
    app = make_app(tmp_path)
    result = apply_appinspect_patch(app, make_failure(check, target))

    assert result.changed_paths
    assert not (app / target).exists()
    assert (app / survivor).exists()


def test_patchers_are_idempotent(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    failure = make_failure("check_user_seed_conf_deny_list", "default/user-seed.conf")

    first = apply_appinspect_patch(app, failure)
    second = apply_appinspect_patch(app, failure)

    assert first.changed_paths == ("default/user-seed.conf",)
    assert second.changed_paths == ()
    assert "already absent" in second.summary


def test_safe_child_path_rejects_paths_outside_app_root(tmp_path: Path) -> None:
    app = make_app(tmp_path)

    with pytest.raises(AppInspectPatchError):
        safe_child_path(app, "../outside.conf")


def test_patcher_ignores_forged_failure_file(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    outside = tmp_path / "outside.conf"
    outside.write_text("do not delete\n", encoding="utf-8")
    forged_failure = make_failure("check_user_seed_conf_deny_list", "../outside.conf")

    apply_appinspect_patch(app, forged_failure)

    assert outside.exists()
    assert not (app / "default" / "user-seed.conf").exists()
