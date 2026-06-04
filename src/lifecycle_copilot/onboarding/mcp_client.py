from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


RUN_QUERY_TOOL = "splunk_run_query"
QUERY_ARGUMENT_CANDIDATES = ("query", "search", "spl")


class McpClientError(RuntimeError):
    pass


class McpToolUnavailableError(McpClientError):
    def __init__(self, tool_names: tuple[str, ...]) -> None:
        self.tool_names = tool_names
        super().__init__(
            f"{RUN_QUERY_TOOL} is not exposed by the configured MCP server. "
            f"Observed tools: {', '.join(tool_names) or '(none)'}"
        )


class McpToolSchemaError(McpClientError):
    def __init__(self, schema: dict[str, Any], tool_names: tuple[str, ...]) -> None:
        self.schema = schema
        self.tool_names = tool_names
        super().__init__(
            f"{RUN_QUERY_TOOL} input schema does not expose any supported SPL argument "
            f"({', '.join(QUERY_ARGUMENT_CANDIDATES)})."
        )


class McpResultPayloadError(McpClientError):
    pass


@dataclass(frozen=True)
class McpConfig:
    endpoint: str
    encrypted_token: str
    tls_verify: bool


@dataclass(frozen=True)
class McpPreflight:
    tool_names: tuple[str, ...]
    run_query_schema: dict[str, Any]
    query_argument: str


@dataclass(frozen=True)
class McpQueryResponse:
    rows: list[dict[str, Any]]
    raw_payload: dict[str, Any]


class McpSplunkClient:
    def __init__(self, config: McpConfig) -> None:
        self.config = config
        self._preflight: McpPreflight | None = None

    @classmethod
    def from_env(cls) -> "McpSplunkClient":
        load_dotenv()
        endpoint = os.getenv("SPLUNK_MCP_ENDPOINT", "")
        token = os.getenv("SPLUNK_MCP_ENCRYPTED_TOKEN", "")
        if not endpoint:
            raise McpClientError("SPLUNK_MCP_ENDPOINT must be set.")
        if not token or token == "replace-with-mcp-app-generated-encrypted-token":
            raise McpClientError("SPLUNK_MCP_ENCRYPTED_TOKEN must be set to an encrypted MCP token.")
        return cls(
            McpConfig(
                endpoint=endpoint,
                encrypted_token=token,
                tls_verify=_env_bool("SPLUNK_MCP_TLS_VERIFY", default=True),
            )
        )

    def preflight(self) -> McpPreflight:
        self._preflight = asyncio.run(self._preflight_async())
        return self._preflight

    def run_query(self, spl: str) -> McpQueryResponse:
        if self._preflight is None:
            self.preflight()
        assert self._preflight is not None
        return asyncio.run(self._run_query_async(spl, self._preflight.query_argument))

    async def _preflight_async(self) -> McpPreflight:
        async with self._session() as session:
            tools_result = await session.list_tools()
            tools = tuple(tools_result.tools)
            tool_names = tuple(sorted(tool.name for tool in tools))
            run_query_tool = next((tool for tool in tools if tool.name == RUN_QUERY_TOOL), None)
            if run_query_tool is None:
                raise McpToolUnavailableError(tool_names)

            schema = dict(run_query_tool.inputSchema or {})
            properties = schema.get("properties", {})
            query_argument = next(
                (name for name in QUERY_ARGUMENT_CANDIDATES if name in properties),
                None,
            )
            if query_argument is None:
                raise McpToolSchemaError(schema, tool_names)

            return McpPreflight(
                tool_names=tool_names,
                run_query_schema=schema,
                query_argument=query_argument,
            )

    async def _run_query_async(self, spl: str, query_argument: str) -> McpQueryResponse:
        async with self._session() as session:
            result = await session.call_tool(RUN_QUERY_TOOL, arguments={query_argument: spl})
        rows = extract_rows_from_tool_result(result)
        return McpQueryResponse(
            rows=rows,
            raw_payload=_tool_result_payload(result),
        )

    def _client_factory(
        self,
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        auth: httpx.Auth | None = None,
    ) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            headers=headers,
            timeout=timeout,
            auth=auth,
            verify=self.config.tls_verify,
        )

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.config.encrypted_token}"}

    def _session(self):
        return _McpSessionContext(self.config.endpoint, self._headers(), self._client_factory)


class _McpSessionContext:
    def __init__(self, endpoint: str, headers: dict[str, str], client_factory: Any) -> None:
        self.endpoint = endpoint
        self.headers = headers
        self.client_factory = client_factory
        self._http_context: Any = None
        self._session_context: Any = None

    async def __aenter__(self) -> ClientSession:
        self._http_context = streamablehttp_client(
            self.endpoint,
            headers=self.headers,
            timeout=30,
            sse_read_timeout=300,
            httpx_client_factory=self.client_factory,
        )
        read_stream, write_stream, _ = await self._http_context.__aenter__()
        self._session_context = ClientSession(read_stream, write_stream)
        session = await self._session_context.__aenter__()
        await session.initialize()
        return session

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self._session_context is not None:
            await self._session_context.__aexit__(exc_type, exc, traceback)
        if self._http_context is not None:
            await self._http_context.__aexit__(exc_type, exc, traceback)


def extract_rows_from_tool_result(result: Any) -> list[dict[str, Any]]:
    if bool(getattr(result, "isError", False)):
        raise McpResultPayloadError(f"{RUN_QUERY_TOOL} returned an error result.")

    payloads: list[Any] = []
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        payloads.append(structured)

    for content in getattr(result, "content", []) or []:
        text = _content_text(content)
        if text is None:
            continue
        try:
            payloads.append(json.loads(text))
        except json.JSONDecodeError:
            payloads.append(text)

    for payload in payloads:
        rows = _rows_from_payload(payload)
        if rows is not None:
            return rows

    raise McpResultPayloadError("Unsupported MCP result payload; no row list found.")


def _rows_from_payload(payload: Any) -> list[dict[str, Any]] | None:
    if isinstance(payload, list):
        return [dict(row) for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return None

    for key in ("results", "rows", "events", "data", "result"):
        if key not in payload:
            continue
        value = payload[key]
        rows = _rows_from_payload(value)
        if rows is not None:
            return rows
    return None


def _content_text(content: Any) -> str | None:
    if isinstance(content, dict):
        value = content.get("text")
        return value if isinstance(value, str) else None
    value = getattr(content, "text", None)
    return value if isinstance(value, str) else None


def _tool_result_payload(result: Any) -> dict[str, Any]:
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    if isinstance(result, dict):
        return result
    return {"repr": repr(result)}


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
