from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable

import requests
from dotenv import load_dotenv


class HecIngestError(RuntimeError):
    pass


@dataclass(frozen=True)
class HecConfig:
    host: str
    port: int
    token: str
    index: str
    sourcetype: str
    source: str
    scheme: str = "https"
    tls_verify: bool = False

    @property
    def endpoint(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}/services/collector/event"


class HecIngestor:
    def __init__(self, config: HecConfig) -> None:
        self.config = config

    @classmethod
    def from_env(cls, *, source: str) -> "HecIngestor":
        load_dotenv()
        token = os.getenv("SPLUNK_HEC_TOKEN", "")
        if not token or token == "00000000-0000-0000-0000-000000000000":
            raise HecIngestError("SPLUNK_HEC_TOKEN must be set to a real HEC token.")
        config = HecConfig(
            host=os.getenv("SPLUNK_HOST", "localhost"),
            port=int(os.getenv("SPLUNK_HEC_PORT", "8088")),
            token=token,
            index=os.getenv("SPLUNK_ONBOARDING_INDEX", "main"),
            sourcetype=os.getenv("SPLUNK_ONBOARDING_SOURCETYPE", "upi_gateway_raw"),
            source=source,
            scheme=os.getenv("SPLUNK_HEC_SCHEME", "https"),
            tls_verify=_env_bool("SPLUNK_HEC_TLS_VERIFY", default=False),
        )
        return cls(config)

    def ingest_lines(self, lines: Iterable[str]) -> int:
        count = 0
        headers = {"Authorization": f"Splunk {self.config.token}"}
        with requests.Session() as session:
            for line in lines:
                event = line.rstrip("\n")
                if not event:
                    continue
                response = session.post(
                    self.config.endpoint,
                    headers=headers,
                    json={
                        "event": event,
                        "index": self.config.index,
                        "sourcetype": self.config.sourcetype,
                        "source": self.config.source,
                    },
                    timeout=10,
                    verify=self.config.tls_verify,
                )
                if response.status_code >= 400:
                    raise HecIngestError(
                        f"HEC ingest failed with HTTP {response.status_code}: {response.text}"
                    )
                body = response.json()
                if int(body.get("code", 0)) != 0:
                    raise HecIngestError(f"HEC ingest failed: {body}")
                count += 1
        return count


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
