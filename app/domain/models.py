from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class DietaryPreferences:
    meals_per_day: int
    calories_per_day: Optional[int] = None
    budget_per_day: Optional[float] = None
    dietary_restrictions: Tuple[str, ...] = ()
    cuisines: Tuple[str, ...] = ()
    avoid_ingredients: Tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, payload: dict[str, object]) -> "DietaryPreferences":
        return cls(
            meals_per_day=int(payload.get("meals_per_day", 3)),
            calories_per_day=payload.get("calories_per_day"),
            budget_per_day=payload.get("budget_per_day"),
            dietary_restrictions=tuple(payload.get("dietary_restrictions") or []),
            cuisines=tuple(payload.get("cuisines") or []),
            avoid_ingredients=tuple(payload.get("avoid_ingredients") or []),
        )

    def to_prompt(self) -> str:
        parts: list[str] = [
            f"Create a five-day meal plan with {self.meals_per_day} meals per day.",
        ]

        if self.calories_per_day:
            parts.append(f"Target approximately {self.calories_per_day} calories per day.")

        if self.budget_per_day:
            parts.append(f"Keep the shopping budget near ${self.budget_per_day:.2f} per day.")

        if self.dietary_restrictions:
            parts.append(
                "Dietary restrictions: " + ", ".join(self.dietary_restrictions) + "."
            )

        if self.cuisines:
            parts.append("Preferred cuisines: " + ", ".join(self.cuisines) + ".")

        if self.avoid_ingredients:
            parts.append(
                "Avoid these ingredients: " + ", ".join(self.avoid_ingredients) + "."
            )

        parts.append(
            "Return the plan as a daily list of meals with breakfast, lunch, dinner, and optional snacks."
        )
        return "\n".join(parts)


@dataclass(frozen=True)
class MealPlanResult:
    raw_meal_plan: str
    raw_shopping_list: str
    nutrition_summary: str
    budget_summary: str
    daily_plan: Tuple[str, ...]
    shopping_items: Tuple[str, ...]

    @classmethod
    def from_raw(
        cls,
        raw_meal_plan: str,
        raw_shopping_list: str,
        nutrition_summary: str,
        budget_summary: str,
    ) -> "MealPlanResult":
        return cls(
            raw_meal_plan=raw_meal_plan.strip(),
            raw_shopping_list=raw_shopping_list.strip(),
            nutrition_summary=nutrition_summary.strip(),
            budget_summary=budget_summary.strip(),
            daily_plan=tuple(_extract_lines(raw_meal_plan)),
            shopping_items=tuple(_extract_lines(raw_shopping_list)),
        )


def _extract_lines(text: str) -> Tuple[str, ...]:
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        bullet_match = re.match(r"^[\-\*]\s*(.+)$", line)
        numbered_match = re.match(r"^\d+[\.)]\s*(.+)$", line)
        if bullet_match:
            lines.append(bullet_match.group(1).strip())
        elif numbered_match:
            lines.append(numbered_match.group(1).strip())
        else:
            lines.append(line)

    return tuple(lines)
