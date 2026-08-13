"""Wire format — the subset of the LCO WebSocket protocol this server uses.

Mirrors `src/adc_winered/ws/envelope.py`, trimmed to what a mechanisms-only
server needs. Copied rather than imported: this package has to install on a Pi
that has no ADC server, no pyads, and no PLC to talk to. If the envelope
changes in the spec, both files move together.

Spec: /Users/william/workspace/lco-ansible/docs/ws-protocol.md
"""

from __future__ import annotations

import enum
import json
from dataclasses import dataclass
from typing import Any

PROTOCOL_VERSION = 1
# Same app tag as the PLC-backed server: to a client this *is* the WINERED ADC's
# mechanisms surface, just without the ADC. The advertised topic list is what
# tells the client which panels it can offer — here, only the mechanisms one.
APP_NAME = "ADC"
KNOWN_TOPICS = ("mechanisms",)


class ErrorCode(str, enum.Enum):
    BUSY = "busy"
    MISSING_ARGUMENT = "missing_argument"
    INVALID_ARGUMENT = "invalid_argument"
    HARDWARE = "hardware"
    PLC_UNREACHABLE = "plc_unreachable"


@dataclass(frozen=True, slots=True)
class CmdFrame:
    id: str
    name: str
    args: dict[str, Any]


@dataclass(frozen=True, slots=True)
class SubscribeFrame:
    topics: list[str]


@dataclass(frozen=True, slots=True)
class UnsubscribeFrame:
    topics: list[str]


@dataclass(frozen=True, slots=True)
class ParseError(Exception):
    code: ErrorCode
    message: str

    def __str__(self) -> str:
        return f"{self.code.value}: {self.message}"


# --- server -> client builders --------------------------------------------------

def hello() -> str:
    return json.dumps({
        "type": "hello",
        "protocol_version": PROTOCOL_VERSION,
        "app": APP_NAME,
        "topics": list(KNOWN_TOPICS),
    })


def state(topic: str, data: dict[str, Any]) -> str:
    return json.dumps({"type": "state", "topic": topic, "data": data})


def ack_ok(cmd_id: str, result: dict[str, Any] | None = None) -> str:
    payload: dict[str, Any] = {"type": "ack", "id": cmd_id, "ok": True}
    if result is not None:
        payload["result"] = result
    return json.dumps(payload)


def ack_err(cmd_id: str, code: ErrorCode, message: str) -> str:
    return json.dumps({
        "type": "ack",
        "id": cmd_id,
        "ok": False,
        "error": {"code": code.value, "message": message},
    })


# --- client -> server parser ----------------------------------------------------

def parse_client_frame(
    raw: str | bytes,
) -> CmdFrame | SubscribeFrame | UnsubscribeFrame:
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ParseError(ErrorCode.INVALID_ARGUMENT, f"not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ParseError(ErrorCode.INVALID_ARGUMENT, "frame must be a JSON object")

    frame_type = payload.get("type")
    if frame_type == "cmd":
        cmd_id = payload.get("id")
        name = payload.get("name")
        if not isinstance(cmd_id, str) or not cmd_id:
            raise ParseError(ErrorCode.MISSING_ARGUMENT, "cmd.id (non-empty string) required")
        if not isinstance(name, str) or not name:
            raise ParseError(ErrorCode.MISSING_ARGUMENT, "cmd.name (non-empty string) required")
        args = payload.get("args", {})
        if not isinstance(args, dict):
            raise ParseError(ErrorCode.INVALID_ARGUMENT, "cmd.args must be an object if present")
        return CmdFrame(id=cmd_id, name=name, args=args)

    if frame_type in ("subscribe", "unsubscribe"):
        topics = payload.get("topics")
        if not isinstance(topics, list) or not all(isinstance(t, str) for t in topics):
            raise ParseError(
                ErrorCode.INVALID_ARGUMENT,
                f"{frame_type}.topics must be a list of strings",
            )
        if frame_type == "subscribe":
            return SubscribeFrame(topics=list(topics))
        return UnsubscribeFrame(topics=list(topics))

    raise ParseError(ErrorCode.INVALID_ARGUMENT, f"unknown frame type: {frame_type!r}")
