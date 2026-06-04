import json

import pytest
from mcp.types import CallToolResult, TextContent

from lifecycle_copilot.onboarding.mcp_client import (
    McpConfig,
    McpResultPayloadError,
    McpSplunkClient,
    McpToolUnavailableError,
    extract_rows_from_tool_result,
)


def test_mcp_result_parser_handles_structured_content() -> None:
    result = CallToolResult(
        content=[],
        structuredContent={"results": [{"_raw": "event one", "txn_id": "UPI1"}]},
    )

    assert extract_rows_from_tool_result(result) == [{"_raw": "event one", "txn_id": "UPI1"}]


def test_mcp_result_parser_handles_json_text_content() -> None:
    result = CallToolResult(
        content=[TextContent(type="text", text=json.dumps({"rows": [{"_raw": "event two"}]}))]
    )

    assert extract_rows_from_tool_result(result) == [{"_raw": "event two"}]


def test_mcp_result_parser_rejects_unsupported_payloads() -> None:
    result = CallToolResult(content=[TextContent(type="text", text=json.dumps({"message": "ok"}))])

    with pytest.raises(McpResultPayloadError):
        extract_rows_from_tool_result(result)


def test_mcp_preflight_fails_when_run_query_tool_absent() -> None:
    client = McpSplunkClient(
        McpConfig(
            endpoint="https://localhost:8089/services/mcp",
            encrypted_token="encrypted",
            tls_verify=False,
        )
    )
    client._session = lambda: _FakeSessionContext([_FakeTool("splunk_get_knowledge_objects")])

    with pytest.raises(McpToolUnavailableError):
        client.preflight()


class _FakeTool:
    def __init__(self, name: str) -> None:
        self.name = name
        self.inputSchema = {"type": "object", "properties": {"query": {"type": "string"}}}


class _FakeListToolsResult:
    def __init__(self, tools: list[_FakeTool]) -> None:
        self.tools = tools


class _FakeSession:
    def __init__(self, tools: list[_FakeTool]) -> None:
        self.tools = tools

    async def list_tools(self) -> _FakeListToolsResult:
        return _FakeListToolsResult(self.tools)


class _FakeSessionContext:
    def __init__(self, tools: list[_FakeTool]) -> None:
        self.tools = tools

    async def __aenter__(self) -> _FakeSession:
        return _FakeSession(self.tools)

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None
