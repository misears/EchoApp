"""
Echo Pro Undo Manager
Provides a thin undo/redo layer for recording takes and transport actions.
"""

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Protocol, Any


class UndoableAction(Protocol):
    def undo(self) -> None:
        ...

    def redo(self) -> None:
        ...


@dataclass
class ActionHistory:
    """Stores a reversible recording-related action."""

    description: str
    action: UndoableAction
    metadata: dict[str, Any] = field(default_factory=dict)


class UndoManager:
    """Simple bounded undo/redo stack for recording workflows."""

    def __init__(self, max_levels: int = 10):
        self.max_levels = max(1, max_levels)
        self._undo_stack: List[ActionHistory] = []
        self._redo_stack: List[ActionHistory] = []

    def push(self, action: UndoableAction, description: str = "", metadata: Optional[dict[str, Any]] = None) -> None:
        history = ActionHistory(description=description, action=action, metadata=metadata or {})
        self._undo_stack.append(history)
        if len(self._undo_stack) > self.max_levels:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def undo(self) -> Optional[ActionHistory]:
        if not self._undo_stack:
            return None
        history = self._undo_stack.pop()
        history.action.undo()
        self._redo_stack.append(history)
        return history

    def redo(self) -> Optional[ActionHistory]:
        if not self._redo_stack:
            return None
        history = self._redo_stack.pop()
        history.action.redo()
        self._undo_stack.append(history)
        return history

    def clear(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()
