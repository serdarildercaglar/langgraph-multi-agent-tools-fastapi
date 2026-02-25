"""Checkpointer factory for LangGraph agents."""

from langgraph.checkpoint.sqlite import SqliteSaver

_checkpointer: SqliteSaver | None = None


def get_checkpointer() -> SqliteSaver:
    """Return a shared SqliteSaver instance.

    Konuşma geçmişi checkpoints.db dosyasında saklanır.
    """
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = SqliteSaver.from_conn_string("checkpoints.db")
    return _checkpointer
