from lifecycle_copilot.appinspect.parser import parse_appinspect_report


def test_parser_extracts_three_grouped_failures() -> None:
    report = {
        "summary": {"error": 0, "failure": 3, "warning": 6},
        "reports": [
            {
                "groups": [
                    {
                        "name": "check_cloud_simple_app",
                        "checks": [
                            {
                                "name": "check_user_seed_conf_deny_list",
                                "result": "failure",
                                "messages": [
                                    {
                                        "message": "Remove default/user-seed.conf",
                                        "result": "failure",
                                        "message_filename": "default/user-seed.conf",
                                        "message_line": None,
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "name": "check_outputs_configuration_file",
                        "checks": [
                            {
                                "name": "check_if_outputs_conf_exists",
                                "result": "failure",
                                "messages": [
                                    {
                                        "message": "tcpout is enabled",
                                        "result": "failure",
                                        "message_filename": "default/outputs.conf",
                                        "message_line": None,
                                    },
                                    {
                                        "message": "external indexers are enabled",
                                        "result": "failure",
                                        "message_filename": "default/outputs.conf",
                                        "message_line": None,
                                    },
                                ],
                            }
                        ],
                    },
                    {
                        "name": "check_application_structure",
                        "checks": [
                            {
                                "name": "check_that_local_does_not_exist",
                                "result": "failure",
                                "messages": [
                                    {
                                        "message": "A 'local' directory exists in the app.",
                                        "result": "failure",
                                        "message_filename": "None",
                                        "message_line": None,
                                    }
                                ],
                            }
                        ],
                    },
                ]
            }
        ],
    }

    summary, failures = parse_appinspect_report(report)

    assert summary["failure"] == 3
    assert len(failures) == 3
    by_check = {failure.check: failure for failure in failures}
    assert by_check["check_that_local_does_not_exist"].file == "local/"
    assert by_check["check_user_seed_conf_deny_list"].file == "default/user-seed.conf"
    outputs_failure = by_check["check_if_outputs_conf_exists"]
    assert outputs_failure.file == "default/outputs.conf"
    assert len(outputs_failure.messages) == 2
    assert outputs_failure.message.startswith("2 AppInspect failure messages")
