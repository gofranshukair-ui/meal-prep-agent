from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Optional, Tuple

MEAL_TYPE_KEYS = ("breakfast", "lunch", "dinner", "snack")
MEAL_TYPE_LABELS = {
    "breakfast": "Breakfast",
    "lunch": "Lunch",
    "dinner": "Dinner",
    "snack": "Snack",
}

MEAL_PLAN_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "days": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "day": {"type": "integer"},
                    "meals": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "name": {"type": "string"},
                                "calories": {"type": "integer"},
                                "ingredients": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "notes": {"type": "string"},
                            },
                            "required": ["type", "name"],
                        },
                    },
                },
                "required": ["day", "meals"],
            },
        },
    },
    "required": ["days"],
}

SHOPPING_LIST_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "categories": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "quantity": {"type": "string"},
                                "notes": {"type": "string"},
                            },
                            "required": ["name"],
                        },
                    },
                },
                "required": ["category", "items"],
            },
        },
    },
    "required": ["categories"],
}

NUTRITION_VALIDATION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {"type": "string"},
        "summary": {"type": "string"},
        "highlights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "detail": {"type": "string"},
                    "status": {"type": "string"},
                },
                "required": ["label", "detail"],
            },
        },
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "issue": {"type": "string"},
                    "recommendation": {"type": "string"},
                },
                "required": ["issue"],
            },
        },
    },
    "required": ["status", "summary"],
}

BUDGET_VALIDATION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {"type": "string"},
        "summary": {"type": "string"},
        "estimated_daily_cost": {"type": "number"},
        "highlights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "detail": {"type": "string"},
                },
                "required": ["label", "detail"],
            },
        },
        "savings_tips": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item": {"type": "string"},
                    "alternative": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["item"],
            },
        },
    },
    "required": ["status", "summary"],
}


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

        parts.extend([
            "",
            "Return a JSON meal plan matching the required schema.",
            f"Include exactly 5 days and {self.meals_per_day} meals per day.",
            "Use type values: breakfast, lunch, dinner, or snack.",
            "Include calories and ingredients for each meal when possible.",
        ])
        return "\n".join(parts)


@dataclass(frozen=True)
class Meal:
    meal_type: str
    name: str
    calories: Optional[int] = None
    ingredients: Tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class DayPlan:
    day: int
    meals: Tuple[Meal, ...]


@dataclass(frozen=True)
class ShoppingItem:
    name: str
    quantity: str = ""
    notes: str = ""


@dataclass(frozen=True)
class ShoppingCategory:
    category: str
    items: Tuple[ShoppingItem, ...]


@dataclass(frozen=True)
class ValidationHighlight:
    label: str
    detail: str
    status: str = ""


@dataclass(frozen=True)
class ValidationIssue:
    issue: str
    recommendation: str = ""


@dataclass(frozen=True)
class SavingsTip:
    item: str
    alternative: str = ""
    note: str = ""


@dataclass(frozen=True)
class NutritionValidation:
    status: str
    summary: str
    highlights: Tuple[ValidationHighlight, ...] = ()
    issues: Tuple[ValidationIssue, ...] = ()


@dataclass(frozen=True)
class BudgetValidation:
    status: str
    summary: str
    estimated_daily_cost: Optional[float] = None
    highlights: Tuple[ValidationHighlight, ...] = ()
    savings_tips: Tuple[SavingsTip, ...] = ()


@dataclass(frozen=True)
class MealPlanResult:
    raw_meal_plan: str
    raw_shopping_list: str
    nutrition_summary: str
    budget_summary: str
    daily_plan: Tuple[str, ...]
    shopping_items: Tuple[str, ...]
    structured_plan: Tuple[DayPlan, ...] = ()
    structured_shopping_list: Tuple[ShoppingCategory, ...] = ()
    structured_nutrition: Optional[NutritionValidation] = None
    structured_budget: Optional[BudgetValidation] = None

    @classmethod
    def from_raw(
        cls,
        raw_meal_plan: str,
        raw_shopping_list: str,
        nutrition_summary: str,
        budget_summary: str,
    ) -> "MealPlanResult":
        stripped_plan = raw_meal_plan.strip()
        structured_plan = parse_structured_meal_plan(stripped_plan)
        if structured_plan:
            daily_plan = structured_plan_to_daily_lines(structured_plan)
        else:
            daily_plan = tuple(_extract_lines(stripped_plan))
            if daily_plan:
                structured_plan = _structured_plan_from_lines(daily_plan)

        stripped_shopping = raw_shopping_list.strip()
        structured_shopping_list = parse_structured_shopping_list(stripped_shopping)
        if structured_shopping_list:
            shopping_items = structured_shopping_list_to_items(structured_shopping_list)
            raw_shopping_text = structured_shopping_list_to_text(structured_shopping_list)
        else:
            shopping_items = tuple(_extract_lines(stripped_shopping))
            raw_shopping_text = stripped_shopping
            if shopping_items:
                structured_shopping_list = _structured_shopping_from_items(shopping_items)

        stripped_nutrition = nutrition_summary.strip()
        structured_nutrition = parse_structured_nutrition(stripped_nutrition)
        if structured_nutrition:
            nutrition_text = structured_nutrition_to_text(structured_nutrition)
        else:
            nutrition_text = stripped_nutrition
            if nutrition_text:
                structured_nutrition = _structured_nutrition_from_text(nutrition_text)

        stripped_budget = budget_summary.strip()
        structured_budget = parse_structured_budget(stripped_budget)
        if structured_budget:
            budget_text = structured_budget_to_text(structured_budget)
        else:
            budget_text = stripped_budget
            if budget_text:
                structured_budget = _structured_budget_from_text(budget_text)

        return cls(
            raw_meal_plan=stripped_plan,
            raw_shopping_list=raw_shopping_text,
            nutrition_summary=nutrition_text,
            budget_summary=budget_text,
            daily_plan=daily_plan,
            shopping_items=shopping_items,
            structured_plan=structured_plan,
            structured_shopping_list=structured_shopping_list,
            structured_nutrition=structured_nutrition,
            structured_budget=structured_budget,
        )


def parse_structured_meal_plan(raw: str) -> Tuple[DayPlan, ...]:
    payload = _load_json_payload(raw)
    if payload is None:
        return ()

    days_raw = payload.get("days") if isinstance(payload, dict) else None
    if not isinstance(days_raw, list):
        return ()

    days: list[DayPlan] = []
    for day_entry in days_raw:
        if not isinstance(day_entry, dict):
            continue
        day_num = day_entry.get("day")
        meals_raw = day_entry.get("meals")
        if not isinstance(day_num, int) or not isinstance(meals_raw, list):
            continue

        meals: list[Meal] = []
        for meal_entry in meals_raw:
            meal = _meal_from_dict(meal_entry)
            if meal is not None:
                meals.append(meal)

        if meals:
            days.append(DayPlan(day=day_num, meals=tuple(meals)))

    days.sort(key=lambda item: item.day)
    return tuple(days)


def structured_plan_to_daily_lines(structured_plan: Tuple[DayPlan, ...]) -> Tuple[str, ...]:
    lines: list[str] = []
    for day in structured_plan:
        lines.append(f"Day {day.day}:")
        for meal in day.meals:
            label = MEAL_TYPE_LABELS.get(meal.meal_type, meal.meal_type.title())
            detail = meal.name
            if meal.calories is not None:
                detail += f" ({meal.calories} cal)"
            lines.append(f"{label}: {detail}")
    return tuple(lines)


def _load_json_payload(raw: str) -> dict[str, Any] | None:
    stripped = raw.strip()
    if not stripped:
        return None

    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", stripped, re.IGNORECASE)
    if fence_match:
        try:
            parsed = json.loads(fence_match.group(1).strip())
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return None

    return None


def _meal_from_dict(entry: object) -> Meal | None:
    if not isinstance(entry, dict):
        return None

    name = entry.get("name")
    if not isinstance(name, str) or not name.strip():
        return None

    meal_type = _normalize_meal_type(entry.get("type"))
    calories = entry.get("calories")
    parsed_calories: int | None = None
    if isinstance(calories, int):
        parsed_calories = calories
    elif isinstance(calories, float):
        parsed_calories = int(calories)

    ingredients_raw = entry.get("ingredients") or []
    ingredients: list[str] = []
    if isinstance(ingredients_raw, list):
        ingredients = [str(item).strip() for item in ingredients_raw if str(item).strip()]

    notes = entry.get("notes")
    parsed_notes = notes.strip() if isinstance(notes, str) else ""

    return Meal(
        meal_type=meal_type,
        name=name.strip(),
        calories=parsed_calories,
        ingredients=tuple(ingredients),
        notes=parsed_notes,
    )


def _normalize_meal_type(value: object) -> str:
    if not isinstance(value, str):
        return "meal"
    normalized = value.strip().lower()
    if normalized in MEAL_TYPE_KEYS:
        return normalized
    for key, label in MEAL_TYPE_LABELS.items():
        if normalized == label.lower():
            return key
    return normalized or "meal"


def _structured_plan_from_lines(lines: Tuple[str, ...]) -> Tuple[DayPlan, ...]:
    days: list[DayPlan] = []
    current_day: DayPlan | None = None

    for line in lines:
        day_match = re.match(r"^Day\s*(\d+)\s*[:\-–—]?\s*(.*)$", line, re.IGNORECASE)
        if day_match:
            if current_day is not None and current_day.meals:
                days.append(current_day)
            day_num = int(day_match.group(1))
            remainder = day_match.group(2).strip()
            meals: tuple[Meal, ...] = ()
            if remainder:
                meals = (_parse_meal_line(remainder),)
            current_day = DayPlan(day=day_num, meals=meals)
            continue

        if current_day is None:
            current_day = DayPlan(day=len(days) + 1, meals=(_parse_meal_line(line),))
        else:
            current_day = DayPlan(
                day=current_day.day,
                meals=current_day.meals + (_parse_meal_line(line),),
            )

    if current_day is not None and current_day.meals:
        days.append(current_day)

    return tuple(days)


def _parse_meal_line(line: str) -> Meal:
    trimmed = re.sub(r"^[-*•]\s*", "", line).strip()
    for key, label in MEAL_TYPE_LABELS.items():
        pattern = rf"^({key}|{label})\s*[:\-–—]\s*(.+)$"
        match = re.match(pattern, trimmed, re.IGNORECASE)
        if match:
            name, notes = _split_meal_description(match.group(2).strip())
            calories = _extract_calories(name, notes)
            return Meal(
                meal_type=key,
                name=name,
                calories=calories,
                notes=notes,
            )

    name, notes = _split_meal_description(trimmed)
    calories = _extract_calories(name, notes)
    return Meal(meal_type="meal", name=name, calories=calories, notes=notes)


def _split_meal_description(text: str) -> tuple[str, str]:
    paren_match = re.match(r"^(.+?)\s*\((.+)\)\s*$", text)
    if paren_match and len(paren_match.group(1)) < 90:
        return paren_match.group(1).strip(), paren_match.group(2).strip()

    dash_match = re.match(r"^(.+?)\s*[—–-]\s*(.+)$", text)
    if dash_match and len(dash_match.group(1)) < 90:
        return dash_match.group(1).strip(), dash_match.group(2).strip()

    return text, ""


def _extract_calories(name: str, notes: str) -> int | None:
    for text in (notes, name):
        match = re.search(r"(\d+)\s*cal(?:ories)?\b", text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


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


def parse_structured_shopping_list(raw: str) -> Tuple[ShoppingCategory, ...]:
    payload = _load_json_payload(raw)
    if payload is None:
        return ()

    categories_raw = payload.get("categories") if isinstance(payload, dict) else None
    if not isinstance(categories_raw, list):
        return ()

    categories: list[ShoppingCategory] = []
    for category_entry in categories_raw:
        if not isinstance(category_entry, dict):
            continue
        category_name = category_entry.get("category")
        items_raw = category_entry.get("items")
        if not isinstance(category_name, str) or not category_name.strip():
            continue
        if not isinstance(items_raw, list):
            continue

        items: list[ShoppingItem] = []
        for item_entry in items_raw:
            item = _shopping_item_from_dict(item_entry)
            if item is not None:
                items.append(item)

        if items:
            categories.append(
                ShoppingCategory(category=category_name.strip(), items=tuple(items))
            )

    return tuple(categories)


def structured_shopping_list_to_items(
    structured_shopping_list: Tuple[ShoppingCategory, ...],
) -> Tuple[str, ...]:
    items: list[str] = []
    for category in structured_shopping_list:
        for item in category.items:
            label = item.name
            if item.quantity:
                label = f"{label} ({item.quantity})"
            items.append(label)
    return tuple(items)


def structured_shopping_list_to_text(
    structured_shopping_list: Tuple[ShoppingCategory, ...],
) -> str:
    lines: list[str] = []
    for category in structured_shopping_list:
        lines.append(category.category)
        for item in category.items:
            detail = item.name
            if item.quantity:
                detail += f" — {item.quantity}"
            if item.notes:
                detail += f" ({item.notes})"
            lines.append(f"- {detail}")
        lines.append("")
    return "\n".join(lines).strip()


def _shopping_item_from_dict(entry: object) -> ShoppingItem | None:
    if not isinstance(entry, dict):
        return None

    name = entry.get("name")
    if not isinstance(name, str) or not name.strip():
        return None

    quantity = entry.get("quantity")
    notes = entry.get("notes")
    return ShoppingItem(
        name=name.strip(),
        quantity=quantity.strip() if isinstance(quantity, str) else "",
        notes=notes.strip() if isinstance(notes, str) else "",
    )


def _structured_shopping_from_items(items: Tuple[str, ...]) -> Tuple[ShoppingCategory, ...]:
    shopping_items = tuple(
        ShoppingItem(name=item) for item in items if item.strip()
    )
    if not shopping_items:
        return ()
    return (ShoppingCategory(category="Shopping list", items=shopping_items),)


def parse_structured_nutrition(raw: str) -> NutritionValidation | None:
    payload = _load_json_payload(raw)
    if payload is None:
        return None
    return _nutrition_from_dict(payload)


def parse_structured_budget(raw: str) -> BudgetValidation | None:
    payload = _load_json_payload(raw)
    if payload is None:
        return None
    return _budget_from_dict(payload)


def structured_nutrition_to_text(nutrition: NutritionValidation) -> str:
    lines = [nutrition.summary]
    if nutrition.highlights:
        lines.append("")
        for highlight in nutrition.highlights:
            lines.append(f"- {highlight.label}: {highlight.detail}")
    if nutrition.issues:
        lines.append("")
        for issue in nutrition.issues:
            line = f"- {issue.issue}"
            if issue.recommendation:
                line += f" — {issue.recommendation}"
            lines.append(line)
    return "\n".join(lines).strip()


def structured_budget_to_text(budget: BudgetValidation) -> str:
    lines = [budget.summary]
    if budget.estimated_daily_cost is not None:
        lines.append(f"Estimated daily cost: ${budget.estimated_daily_cost:.2f}")
    if budget.highlights:
        lines.append("")
        for highlight in budget.highlights:
            lines.append(f"- {highlight.label}: {highlight.detail}")
    if budget.savings_tips:
        lines.append("")
        for tip in budget.savings_tips:
            line = f"- {tip.item}"
            if tip.alternative:
                line += f" → {tip.alternative}"
            if tip.note:
                line += f" ({tip.note})"
            lines.append(line)
    return "\n".join(lines).strip()


def _nutrition_from_dict(entry: object) -> NutritionValidation | None:
    if not isinstance(entry, dict):
        return None

    status = entry.get("status")
    summary = entry.get("summary")
    if not isinstance(status, str) or not status.strip():
        return None
    if not isinstance(summary, str) or not summary.strip():
        return None

    highlights: list[ValidationHighlight] = []
    highlights_raw = entry.get("highlights") or []
    if isinstance(highlights_raw, list):
        for item in highlights_raw:
            if not isinstance(item, dict):
                continue
            label = item.get("label")
            detail = item.get("detail")
            if not isinstance(label, str) or not isinstance(detail, str):
                continue
            if not label.strip() or not detail.strip():
                continue
            item_status = item.get("status")
            highlights.append(
                ValidationHighlight(
                    label=label.strip(),
                    detail=detail.strip(),
                    status=item_status.strip() if isinstance(item_status, str) else "",
                )
            )

    issues: list[ValidationIssue] = []
    issues_raw = entry.get("issues") or []
    if isinstance(issues_raw, list):
        for item in issues_raw:
            if not isinstance(item, dict):
                continue
            issue = item.get("issue")
            if not isinstance(issue, str) or not issue.strip():
                continue
            recommendation = item.get("recommendation")
            issues.append(
                ValidationIssue(
                    issue=issue.strip(),
                    recommendation=recommendation.strip()
                    if isinstance(recommendation, str)
                    else "",
                )
            )

    return NutritionValidation(
        status=status.strip().lower(),
        summary=summary.strip(),
        highlights=tuple(highlights),
        issues=tuple(issues),
    )


def _budget_from_dict(entry: object) -> BudgetValidation | None:
    if not isinstance(entry, dict):
        return None

    status = entry.get("status")
    summary = entry.get("summary")
    if not isinstance(status, str) or not status.strip():
        return None
    if not isinstance(summary, str) or not summary.strip():
        return None

    estimated_daily_cost = entry.get("estimated_daily_cost")
    parsed_cost: float | None = None
    if isinstance(estimated_daily_cost, (int, float)):
        parsed_cost = float(estimated_daily_cost)

    highlights: list[ValidationHighlight] = []
    highlights_raw = entry.get("highlights") or []
    if isinstance(highlights_raw, list):
        for item in highlights_raw:
            if not isinstance(item, dict):
                continue
            label = item.get("label")
            detail = item.get("detail")
            if not isinstance(label, str) or not isinstance(detail, str):
                continue
            if not label.strip() or not detail.strip():
                continue
            highlights.append(
                ValidationHighlight(label=label.strip(), detail=detail.strip())
            )

    savings_tips: list[SavingsTip] = []
    tips_raw = entry.get("savings_tips") or []
    if isinstance(tips_raw, list):
        for item in tips_raw:
            if not isinstance(item, dict):
                continue
            tip_item = item.get("item")
            if not isinstance(tip_item, str) or not tip_item.strip():
                continue
            alternative = item.get("alternative")
            note = item.get("note")
            savings_tips.append(
                SavingsTip(
                    item=tip_item.strip(),
                    alternative=alternative.strip()
                    if isinstance(alternative, str)
                    else "",
                    note=note.strip() if isinstance(note, str) else "",
                )
            )

    return BudgetValidation(
        status=status.strip().lower(),
        summary=summary.strip(),
        estimated_daily_cost=parsed_cost,
        highlights=tuple(highlights),
        savings_tips=tuple(savings_tips),
    )


def _structured_nutrition_from_text(text: str) -> NutritionValidation | None:
    if not text.strip():
        return None
    return NutritionValidation(status="unknown", summary=text.strip())


def _structured_budget_from_text(text: str) -> BudgetValidation | None:
    if not text.strip():
        return None
    return BudgetValidation(status="unknown", summary=text.strip())
