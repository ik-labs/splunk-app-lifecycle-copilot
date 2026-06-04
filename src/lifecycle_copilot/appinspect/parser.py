from __future__ import annotations

from dataclasses import dataclass
from typing import Any


TARGET_BY_CHECK = {
    "check_that_local_does_not_exist": "local/",
    "check_user_seed_conf_deny_list": "default/user-seed.conf",
    "check_if_outputs_conf_exists": "default/outputs.conf",
}


@dataclass(frozen=True)
class AppInspectMessage:
    message: str
    file: str | None
    line: int | None
    raw: dict[str, Any]


@dataclass(frozen=True)
class AppInspectFailure:
    failure_id: str
    group: str
    check: str
    file: str | None
    line: int | None
    message: str
    messages: tuple[AppInspectMessage, ...]
    raw_check: dict[str, Any]


def parse_appinspect_report(report: dict[str, Any]) -> tuple[dict[str, Any], list[AppInspectFailure]]:
    summary = dict(report.get("summary", {}))
    grouped: dict[tuple[str, str | None], dict[str, Any]] = {}

    for app_report in report.get("reports", []):
        for group in app_report.get("groups", []):
            group_name = str(group.get("name", ""))
            for check in group.get("checks", []):
                if check.get("result") != "failure":
                    continue

                check_name = str(check.get("name", ""))
                messages = tuple(_parse_message(message) for message in check.get("messages", []))
                target_file = _target_file(check_name, messages)
                key = (check_name, target_file)

                if key not in grouped:
                    grouped[key] = {
                        "group": group_name,
                        "check": check_name,
                        "file": target_file,
                        "messages": [],
                        "raw_check": check,
                    }
                grouped[key]["messages"].extend(messages)

    failures: list[AppInspectFailure] = []
    for (check_name, target_file), item in grouped.items():
        messages = tuple(item["messages"])
        failures.append(
            AppInspectFailure(
                failure_id=f"appinspect:{check_name}:{target_file or 'app'}",
                group=item["group"],
                check=check_name,
                file=target_file,
                line=_first_line(messages),
                message=_summarize_messages(target_file, messages),
                messages=messages,
                raw_check=item["raw_check"],
            )
        )

    return summary, failures


def _parse_message(raw_message: dict[str, Any]) -> AppInspectMessage:
    return AppInspectMessage(
        message=str(raw_message.get("message", "")),
        file=_clean_filename(raw_message.get("message_filename")),
        line=raw_message.get("message_line"),
        raw=raw_message,
    )


def _target_file(check_name: str, messages: tuple[AppInspectMessage, ...]) -> str | None:
    for message in messages:
        if message.file:
            return message.file
    return TARGET_BY_CHECK.get(check_name)


def _clean_filename(value: Any) -> str | None:
    if value is None:
        return None
    filename = str(value)
    if not filename or filename == "None":
        return None
    return filename


def _first_line(messages: tuple[AppInspectMessage, ...]) -> int | None:
    for message in messages:
        if message.line is not None:
            return int(message.line)
    return None


def _summarize_messages(target_file: str | None, messages: tuple[AppInspectMessage, ...]) -> str:
    if not messages:
        return f"AppInspect reported a failure for {target_file or 'the app'}."
    if len(messages) == 1:
        return messages[0].message
    return (
        f"{len(messages)} AppInspect failure messages for {target_file or 'the app'}: "
        f"{messages[0].message}"
    )
