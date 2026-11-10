"""Tests for bounded and isolated short-term conversation context."""

from __future__ import annotations

from src.conversation import ConversationStore


def _append(
    store: ConversationStore,
    session_id: str,
    question: str,
    answer: str,
) -> None:
    store.append(
        session_id,
        question=question,
        answer=answer,
        refused=False,
    )


def test_sessions_are_isolated() -> None:
    store = ConversationStore()
    _append(store, "session-a", "Question A", "Answer A")

    context_a = store.get_context("session-a")
    context_b = store.get_context("session-b")

    assert context_a["recent_turns"][0]["question"] == "Question A"
    assert context_b == {"summary": "", "recent_turns": []}


def test_older_turns_are_summarized() -> None:
    store = ConversationStore(max_recent_turns=2)
    _append(store, "session-a", "First question", "First answer")
    _append(store, "session-a", "Second question", "Second answer")
    _append(store, "session-a", "Third question", "Third answer")

    context = store.get_context("session-a")

    assert "First question" in context["summary"]
    assert [turn["question"] for turn in context["recent_turns"]] == [
        "Second question",
        "Third question",
    ]


def test_session_count_is_bounded() -> None:
    store = ConversationStore(max_sessions=1)
    _append(store, "old-session", "Old question", "Old answer")
    _append(store, "new-session", "New question", "New answer")

    assert store.get_context("old-session")["recent_turns"] == []
    assert store.get_context("new-session")["recent_turns"][0]["question"] == (
        "New question"
    )
