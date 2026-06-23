from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from app.config import settings


@dataclass
class RecipeMemory:
    request_id: str
    title: str
    summary: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "RecipeMemory":
        return cls(
            request_id=row["request_id"],
            title=row["title"],
            summary=row["summary"],
            created_at=row["created_at"],
        )


@dataclass
class WorkflowState:
    request_id: str
    preferences: dict[str, Any]
    meal_plan: str = ""
    nutrition_report: str = ""
    budget_report: str = ""
    shopping_list: str = ""
    compressed_context: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "WorkflowState":
        return cls(
            request_id=row["request_id"],
            preferences=json.loads(row["preferences"]),
            meal_plan=row["meal_plan"] or "",
            nutrition_report=row["nutrition_report"] or "",
            budget_report=row["budget_report"] or "",
            shopping_list=row["shopping_list"] or "",
            compressed_context=row["compressed_context"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "preferences": self.preferences,
            "meal_plan": self.meal_plan,
            "nutrition_report": self.nutrition_report,
            "budget_report": self.budget_report,
            "shopping_list": self.shopping_list,
            "compressed_context": self.compressed_context,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class WorkflowStateStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(settings.sqlite_db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._ensure_table()

    def _ensure_table(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_state (
                    request_id TEXT PRIMARY KEY,
                    preferences TEXT NOT NULL,
                    meal_plan TEXT,
                    nutrition_report TEXT,
                    budget_report TEXT,
                    shopping_list TEXT,
                    compressed_context TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS recipe_memory (
                    request_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def save_state(self, state: WorkflowState) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO workflow_state (
                    request_id,
                    preferences,
                    meal_plan,
                    nutrition_report,
                    budget_report,
                    shopping_list,
                    compressed_context,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(request_id) DO UPDATE SET
                    preferences=excluded.preferences,
                    meal_plan=excluded.meal_plan,
                    nutrition_report=excluded.nutrition_report,
                    budget_report=excluded.budget_report,
                    shopping_list=excluded.shopping_list,
                    compressed_context=excluded.compressed_context,
                    updated_at=excluded.updated_at
                """,
                (
                    state.request_id,
                    json.dumps(state.preferences),
                    state.meal_plan,
                    state.nutrition_report,
                    state.budget_report,
                    state.shopping_list,
                    state.compressed_context,
                    state.created_at,
                    state.updated_at,
                ),
            )

    def get_state(self, request_id: str) -> Optional[WorkflowState]:
        with self._lock:
            cursor = self._conn.execute(
                "SELECT * FROM workflow_state WHERE request_id = ?",
                (request_id,),
            )
            row = cursor.fetchone()
        return WorkflowState.from_row(row) if row else None

    def update_state(
        self,
        request_id: str,
        preferences: dict[str, Any],
        meal_plan: str | None = None,
        nutrition_report: str | None = None,
        budget_report: str | None = None,
        shopping_list: str | None = None,
        compressed_context: str | None = None,
    ) -> WorkflowState:
        existing = self.get_state(request_id)
        now = datetime.now(timezone.utc).isoformat()
        if existing is None:
            existing = WorkflowState(
                request_id=request_id,
                preferences=preferences,
                meal_plan=meal_plan or "",
                nutrition_report=nutrition_report or "",
                budget_report=budget_report or "",
                shopping_list=shopping_list or "",
                compressed_context=compressed_context or "",
                created_at=now,
                updated_at=now,
            )
        else:
            existing.preferences = preferences
            existing.meal_plan = meal_plan if meal_plan is not None else existing.meal_plan
            existing.nutrition_report = nutrition_report if nutrition_report is not None else existing.nutrition_report
            existing.budget_report = budget_report if budget_report is not None else existing.budget_report
            existing.shopping_list = shopping_list if shopping_list is not None else existing.shopping_list
            existing.compressed_context = compressed_context if compressed_context is not None else existing.compressed_context
            existing.updated_at = now
        self.save_state(existing)
        return existing

    def save_recipe_memory(self, request_id: str, title: str, summary: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO recipe_memory (request_id, title, summary, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(request_id) DO UPDATE SET
                    title=excluded.title,
                    summary=excluded.summary,
                    created_at=excluded.created_at
                """,
                (request_id, title, summary, datetime.now(timezone.utc).isoformat()),
            )

    def get_recent_recipe_memories(self, limit: int | None = None) -> list[RecipeMemory]:
        if limit is None:
            limit = settings.recipe_memory_limit
        with self._lock:
            cursor = self._conn.execute(
                "SELECT * FROM recipe_memory ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            rows = cursor.fetchall()
        return [RecipeMemory.from_row(row) for row in rows]

    def get_previous_recipe_context(self, limit: int | None = None) -> str:
        memories = self.get_recent_recipe_memories(limit)
        if not memories:
            return ""
        lines = ["Previous recipe memory summaries:"]
        for idx, memory in enumerate(memories, start=1):
            lines.append(f"{idx}. {memory.title}: {memory.summary}")
        return "\n".join(lines)


state_store = WorkflowStateStore()
