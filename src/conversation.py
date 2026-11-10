"""Bounded in-memory short-term conversation context."""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _SessionRecord:
    summary: str = ""
    turns: list[dict[str, Any]] = field(default_factory=list)


class ConversationStore:
    """Keep only bounded, process-local session context."""

    def __init__(
        self,
        *,
        max_sessions: int = 128,
        max_recent_turns: int = 4,
        max_summary_chars: int = 1200,
    ) -> None:
        if max_sessions < 1:
            raise ValueError("max_sessions must be positive")
        if max_recent_turns < 1:
            raise ValueError("max_recent_turns must be positive")
        if max_summary_chars < 1:
            raise ValueError("max_summary_chars must be positive")
        self.max_sessions = max_sessions
        self.max_recent_turns = max_recent_turns
        self.max_summary_chars = max_summary_chars
        self._sessions: OrderedDict[str, _SessionRecord] = OrderedDict()
        self._lock = threading.Lock()

    def get_context(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return {"summary": "", "recent_turns": []}
            self._sessions.move_to_end(session_id)
            return {
                "summary": record.summary,
                "recent_turns": [dict(turn) for turn in record.turns],
            }

    def append(
        self,
        session_id: str,
        *,
        question: str,
        answer: str,
        refused: bool,
    ) -> None:
        if not session_id:
            raise ValueError("session_id must not be blank")
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                if len(self._sessions) >= self.max_sessions:
                    self._sessions.popitem(last=False)
                record = _SessionRecord()
                self._sessions[session_id] = record
            else:
                self._sessions.move_to_end(session_id)

            record.turns.append(
                {
                    "question": question,
                    "answer": answer,
                    "refused": refused,
                }
            )
            while len(record.turns) > self.max_recent_turns:
                older = record.turns.pop(0)
                record.summary = self._merge_summary(record.summary, older)

    def _merge_summary(
        self,
        summary: str,
        turn: dict[str, Any],
    ) -> str:
        answer = str(turn.get("answer", ""))[:240]
        outcome = "refused" if turn.get("refused") else "answered"
        entry = (
            f"Q: {str(turn.get('question', ''))[:160]} "
            f"A({outcome}): {answer}"
        )
        combined = f"{summary}\n{entry}".strip()
        return combined[-self.max_summary_chars :]

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()
