#!/usr/bin/env python3
"""Normalize common coding-agent traces into a compact, redacted event stream."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SECRET_PATTERNS = [
    (re.compile(r"(?i)\b(Bearer)\s+[A-Za-z0-9._~+/=-]+"), r"\1 [REDACTED]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"), "[REDACTED]"),
    (
        re.compile(
            r"(?i)(\b[A-Z0-9_]*(?:API[_-]?KEY|TOKEN|PASSWORD|SECRET)\b\s*[=:]\s*)"
            r"([^\s,;\"']+)"
        ),
        r"\1[REDACTED]",
    ),
    (
        re.compile(r'(?i)("(?:authorization|api[_-]?key|token|password|secret)"\s*:\s*")[^"]+'),
        r"\1[REDACTED]",
    ),
]

VALIDATION_RE = re.compile(
    r"(?i)(?:^|[\s/_-])(test|tests|testing|check|lint|validate|verify|pytest|vitest|jest|playwright|"
    r"tsc|build|compile|syntax)(?:$|[\s/_-])"
)
QUESTION_TOOLS = {"askuserquestion", "request_user_input", "ask_user", "askuser"}
PERMISSION_RE = re.compile(r"(?i)(permission|approval|authorize|allow|confirm)")


def redact(text: str) -> str:
    for pattern, replacement in SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def compact(text: Any, limit: int) -> str:
    if text is None:
        return ""
    if not isinstance(text, str):
        text = json.dumps(text, ensure_ascii=False, separators=(",", ":"))
    text = redact(text.replace("\x00", "")).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + f" … [truncated; {len(text)} chars total]"


def parse_time(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10_000_000_000 else value
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str):
        return None
    candidate = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def iso_time(value: Any) -> str | None:
    parsed = parse_time(value)
    return parsed.isoformat().replace("+00:00", "Z") if parsed else None


def find_timestamp(record: dict[str, Any]) -> Any:
    for key in ("timestamp", "created_at", "createdAt", "time", "ts", "start_time"):
        if record.get(key) is not None:
            return record[key]
    message = record.get("message")
    if isinstance(message, dict):
        return find_timestamp(message)
    info = record.get("info")
    if isinstance(info, dict):
        return find_timestamp(info)
    return None


def load_trace(path: Path) -> tuple[list[Any], str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    stripped = text.strip()
    if not stripped:
        return [], "empty"
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, list):
            return parsed, "json"
        if isinstance(parsed, dict):
            for key in ("events", "messages", "turns", "items", "records"):
                if isinstance(parsed.get(key), list):
                    return parsed[key], "json"
            return [parsed], "json"
    except json.JSONDecodeError:
        pass

    records: list[Any] = []
    jsonl = True
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            if isinstance(record, dict):
                record.setdefault("_source_line", line_number)
            records.append(record)
        except json.JSONDecodeError:
            jsonl = False
            break
    if jsonl and records:
        return records, "jsonl"

    return [
        {"type": "text", "content": line, "_source_line": number}
        for number, line in enumerate(text.splitlines(), 1)
        if line.strip()
    ], "text"


def detect_platform(records: Iterable[Any]) -> str:
    sample = [record for record in records if isinstance(record, dict)][:100]
    if any(
        "parentUuid" in r
        or ("sessionId" in r and r.get("type") in {"assistant", "user", "progress", "system"})
        for r in sample
    ):
        return "claude-code"
    if any(
        "sessionID" in r
        or "messageID" in r
        or (isinstance(r.get("info"), dict) and "sessionID" in r["info"])
        for r in sample
    ):
        return "opencode"
    codex_types = {"event_msg", "response_item", "turn_context", "agent_message", "function_call"}
    if any(r.get("type") in codex_types or "thread_id" in r or "turn_id" in r for r in sample):
        return "codex"
    return "generic"


def summarize_tool_input(name: str, payload: Any, limit: int) -> str:
    if not isinstance(payload, dict):
        return compact(payload, limit)
    lowered = name.lower()
    parts: list[str] = []
    for key in ("description", "file_path", "path", "pattern", "query", "url", "command", "cmd"):
        if key in payload and payload[key] not in (None, ""):
            parts.append(f"{key}={compact(payload[key], min(limit, 600))}")
    if lowered in {"write", "edit", "multiedit", "apply_patch"}:
        for key in ("content", "old_string", "new_string", "patch"):
            value = payload.get(key)
            if isinstance(value, str):
                parts.append(f"{key}_chars={len(value)}")
    if lowered in QUESTION_TOOLS:
        questions = payload.get("questions", payload.get("question", payload))
        parts.append(f"questions={compact(questions, min(limit, 1000))}")
    if not parts:
        keys = ",".join(sorted(str(key) for key in payload.keys())[:20])
        parts.append(f"input_keys={keys}")
    return compact("; ".join(parts), limit)


def make_event(
    *,
    timestamp: Any,
    actor: str,
    event_type: str,
    visibility: str,
    surface: str,
    content: Any,
    source_line: int | None,
    limit: int,
    tool_name: str | None = None,
    tool_use_id: str | None = None,
    is_error: bool = False,
) -> dict[str, Any]:
    return {
        "index": 0,
        "timestamp": iso_time(timestamp),
        "actor": actor,
        "event_type": event_type,
        "visibility": visibility,
        "surface": surface,
        "content": compact(content, limit),
        "tool_name": tool_name,
        "tool_use_id": tool_use_id,
        "is_error": bool(is_error),
        "source_line": source_line,
    }


def content_blocks(content: Any) -> list[Any]:
    if isinstance(content, list):
        return content
    if content is None:
        return []
    return [content]


def looks_error(text: str, explicit: Any = False) -> bool:
    if bool(explicit):
        return True
    return bool(
        re.search(
            r"(?im)(^|\n)(?:error:|syntaxerror|traceback|tool_use_error|exit code [1-9]|"
            r"command failed|failed with|permission denied)",
            text,
        )
    )


def normalize_claude(record: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    timestamp = find_timestamp(record)
    line = record.get("_source_line")
    record_type = str(record.get("type", "unknown"))
    message = record.get("message")
    if not isinstance(message, dict):
        message = {}
    content = message.get("content", record.get("content"))
    events: list[dict[str, Any]] = []

    if record_type in {"assistant", "user"}:
        for block in content_blocks(content):
            if isinstance(block, str):
                events.append(
                    make_event(
                        timestamp=timestamp,
                        actor=record_type,
                        event_type="message",
                        visibility="user-visible",
                        surface="assistant-message" if record_type == "assistant" else "user-message",
                        content=block,
                        source_line=line,
                        limit=limit,
                    )
                )
                continue
            if not isinstance(block, dict):
                continue
            block_type = str(block.get("type", "content"))
            if block_type == "thinking":
                events.append(
                    make_event(
                        timestamp=timestamp,
                        actor="assistant",
                        event_type="thinking",
                        visibility="internal-only",
                        surface="internal",
                        content=block.get("thinking", block.get("text", "")),
                        source_line=line,
                        limit=limit,
                    )
                )
            elif block_type in {"text", "output_text"}:
                events.append(
                    make_event(
                        timestamp=timestamp,
                        actor=record_type,
                        event_type="message",
                        visibility="user-visible",
                        surface="assistant-message" if record_type == "assistant" else "user-message",
                        content=block.get("text", ""),
                        source_line=line,
                        limit=limit,
                    )
                )
            elif block_type in {"tool_use", "tool_call"}:
                name = str(block.get("name", "unknown"))
                lowered = name.lower()
                surface = "ask-user" if lowered in QUESTION_TOOLS else "tool-output"
                visibility = "user-visible" if lowered in QUESTION_TOOLS else "potentially-visible"
                events.append(
                    make_event(
                        timestamp=timestamp,
                        actor="assistant",
                        event_type="tool-call",
                        visibility=visibility,
                        surface=surface,
                        content=summarize_tool_input(name, block.get("input", {}), limit),
                        source_line=line,
                        limit=limit,
                        tool_name=name,
                        tool_use_id=block.get("id"),
                    )
                )
            elif block_type in {"tool_result", "tool-result"}:
                raw = compact(block.get("content", block.get("output", "")), limit)
                events.append(
                    make_event(
                        timestamp=timestamp,
                        actor="tool",
                        event_type="tool-result",
                        visibility="potentially-visible",
                        surface="tool-output",
                        content=raw,
                        source_line=line,
                        limit=limit,
                        tool_use_id=block.get("tool_use_id", block.get("id")),
                        is_error=looks_error(raw, block.get("is_error")),
                    )
                )
            else:
                events.append(
                    make_event(
                        timestamp=timestamp,
                        actor=record_type,
                        event_type=block_type,
                        visibility="unknown",
                        surface="unknown",
                        content=block.get("text", block),
                        source_line=line,
                        limit=limit,
                    )
                )
        return events

    if record_type == "progress":
        data = record.get("data", record.get("content", record))
        return [
            make_event(
                timestamp=timestamp,
                actor="harness",
                event_type="progress",
                visibility="potentially-visible",
                surface="progress-update",
                content=data,
                source_line=line,
                limit=limit,
            )
        ]
    return [
        make_event(
            timestamp=timestamp,
            actor="harness" if record_type == "system" else "unknown",
            event_type=record_type,
            visibility="potentially-visible" if record_type == "system" else "unknown",
            surface="tool-output" if record_type == "system" else "unknown",
            content=record.get("content", record.get("message", record.get("data", ""))),
            source_line=line,
            limit=limit,
            is_error=bool(record.get("is_error", False)),
        )
    ]


def normalize_generic(record: Any, limit: int, platform: str) -> list[dict[str, Any]]:
    if not isinstance(record, dict):
        return [
            make_event(
                timestamp=None,
                actor="unknown",
                event_type="text",
                visibility="unknown",
                surface="unknown",
                content=record,
                source_line=None,
                limit=limit,
            )
        ]
    timestamp = find_timestamp(record)
    line = record.get("_source_line")
    info = record.get("info") if isinstance(record.get("info"), dict) else {}
    role = str(record.get("role", info.get("role", record.get("actor", "unknown"))))
    event_type = str(record.get("type", record.get("event_type", "event")))
    tool_name = record.get("tool_name", record.get("name"))
    content = record.get("content", record.get("text", record.get("message", record.get("data", ""))))

    if event_type in {"tool_use", "tool_call", "function_call"} or tool_name:
        name = str(tool_name or "unknown")
        lowered = name.lower()
        return [
            make_event(
                timestamp=timestamp,
                actor="assistant",
                event_type="tool-call",
                visibility="user-visible" if lowered in QUESTION_TOOLS else "potentially-visible",
                surface="ask-user" if lowered in QUESTION_TOOLS else "tool-output",
                content=summarize_tool_input(name, record.get("input", record.get("arguments", content)), limit),
                source_line=line,
                limit=limit,
                tool_name=name,
                tool_use_id=record.get("id", record.get("call_id")),
            )
        ]

    if isinstance(content, list):
        synthetic = {
            "type": role if role in {"assistant", "user"} else "assistant",
            "message": {"content": content},
            "timestamp": timestamp,
            "_source_line": line,
        }
        return normalize_claude(synthetic, limit)

    if event_type in {"tool_result", "function_call_output"}:
        raw = compact(content, limit)
        return [
            make_event(
                timestamp=timestamp,
                actor="tool",
                event_type="tool-result",
                visibility="potentially-visible",
                surface="tool-output",
                content=raw,
                source_line=line,
                limit=limit,
                tool_use_id=record.get("tool_use_id", record.get("call_id")),
                is_error=looks_error(raw, record.get("is_error")),
            )
        ]

    visibility = "user-visible" if role in {"assistant", "user"} else "unknown"
    surface = "assistant-message" if role == "assistant" else "user-message" if role == "user" else "unknown"
    return [
        make_event(
            timestamp=timestamp,
            actor=role,
            event_type=event_type,
            visibility=visibility,
            surface=surface,
            content=content,
            source_line=line,
            limit=limit,
            is_error=looks_error(compact(content, limit), record.get("is_error")),
        )
    ]


def classify_metrics(events: list[dict[str, Any]]) -> dict[str, Any]:
    times = [parse_time(event.get("timestamp")) for event in events]
    valid_times = [value for value in times if value is not None]
    start = min(valid_times) if valid_times else None
    end = max(valid_times) if valid_times else None

    tool_calls = [event for event in events if event["event_type"] == "tool-call"]
    tool_errors = [event for event in events if event["event_type"] == "tool-result" and event["is_error"]]
    names = [str(event.get("tool_name") or "").lower() for event in tool_calls]

    def elapsed(event: dict[str, Any] | None) -> float | None:
        if not event or not start:
            return None
        value = parse_time(event.get("timestamp"))
        return round((value - start).total_seconds(), 3) if value else None

    first_action = tool_calls[0] if tool_calls else None
    write_indices = [
        i
        for i, name in enumerate(names)
        if name in {"write", "edit", "multiedit", "apply_patch", "create_file"}
    ]
    first_artifact = tool_calls[write_indices[0]] if write_indices else None
    assistant_messages = [
        event
        for event in events
        if event["actor"] == "assistant"
        and event["event_type"] == "message"
        and event.get("content", "").strip()
    ]
    final_response = assistant_messages[-1] if assistant_messages else None
    question_calls = [event for event in tool_calls if str(event.get("tool_name") or "").lower() in QUESTION_TOOLS]
    permission_events = [
        event
        for event in events
        if event["surface"] == "permission-request"
        or (
            event["event_type"] == "tool-call"
            and PERMISSION_RE.search(str(event.get("tool_name") or ""))
        )
    ]
    permission_denials = [
        event
        for event in events
        if event["event_type"] == "tool-result"
        and re.search(r"(?i)permission (?:for this action )?was denied", event.get("content", ""))
    ]
    validation_calls = [
        event
        for event in tool_calls
        if VALIDATION_RE.search(f" {event.get('tool_name', '')} {event.get('content', '')} ")
    ]
    error_ids = {event.get("tool_use_id") for event in tool_errors if event.get("tool_use_id")}
    validation_successes = sum(
        1 for event in validation_calls if not event.get("tool_use_id") or event.get("tool_use_id") not in error_ids
    )

    return {
        "started_at": start.isoformat().replace("+00:00", "Z") if start else None,
        "ended_at": end.isoformat().replace("+00:00", "Z") if end else None,
        "duration_seconds": round((end - start).total_seconds(), 3) if start and end else None,
        "time_to_first_action_seconds": elapsed(first_action),
        "time_to_first_artifact_seconds": elapsed(first_artifact),
        "time_to_final_response_seconds": elapsed(final_response),
        "event_count": len(events),
        "assistant_messages": len(assistant_messages),
        "thinking_blocks": sum(event["event_type"] == "thinking" for event in events),
        "tool_calls": len(tool_calls),
        "tool_errors": len(tool_errors),
        "reads": sum(name in {"read", "glob", "grep", "ls", "find"} for name in names),
        "writes": sum(name in {"write", "create_file"} for name in names),
        "edits": sum(name in {"edit", "multiedit", "apply_patch"} for name in names),
        "user_questions": len(question_calls),
        "permission_requests": len(permission_events),
        "permission_denials": len(permission_denials),
        "validation_attempts": len(validation_calls),
        "validation_successes_inferred": validation_successes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace_path", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--platform",
        choices=("auto", "claude-code", "opencode", "codex", "generic"),
        default="auto",
    )
    parser.add_argument("--max-content-chars", type=int, default=1200)
    args = parser.parse_args()

    if args.max_content_chars < 100:
        parser.error("--max-content-chars must be at least 100")
    if not args.trace_path.is_file():
        print(f"error: trace does not exist or is not a file: {args.trace_path}", file=sys.stderr)
        return 2

    try:
        records, source_format = load_trace(args.trace_path)
        platform = detect_platform(records) if args.platform == "auto" else args.platform
        events: list[dict[str, Any]] = []
        for record in records:
            if platform == "claude-code" and isinstance(record, dict):
                events.extend(normalize_claude(record, args.max_content_chars))
            else:
                events.extend(normalize_generic(record, args.max_content_chars, platform))
        for index, event in enumerate(events, 1):
            event["index"] = index

        tool_names_by_id = {
            event["tool_use_id"]: event["tool_name"]
            for event in events
            if event["event_type"] == "tool-call" and event.get("tool_use_id")
        }
        for event in events:
            if event["event_type"] == "tool-result" and event.get("tool_use_id"):
                event["tool_name"] = tool_names_by_id.get(event["tool_use_id"])
        assistant_messages = [
            event
            for event in events
            if event["actor"] == "assistant" and event["event_type"] == "message" and event["content"]
        ]
        if assistant_messages:
            assistant_messages[-1]["surface"] = "final-response"

        result = {
            "schema_version": "1.0",
            "source": {
                "path": str(args.trace_path.resolve()),
                "format": source_format,
                "record_count": len(records),
            },
            "platform": platform,
            "metrics": classify_metrics(events),
            "events": events,
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(
        f"[OK] normalized {len(records)} records into {len(events)} events "
        f"({platform}, {source_format}) -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
