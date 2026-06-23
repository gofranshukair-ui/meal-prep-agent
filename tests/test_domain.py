import json

from app.domain.models import (
    BUDGET_VALIDATION_JSON_SCHEMA,
    DietaryPreferences,
    MealPlanResult,
    MEAL_PLAN_JSON_SCHEMA,
    NUTRITION_VALIDATION_JSON_SCHEMA,
    SHOPPING_LIST_JSON_SCHEMA,
    parse_structured_budget,
    parse_structured_meal_plan,
    parse_structured_nutrition,
    parse_structured_shopping_list,
    structured_budget_to_text,
    structured_nutrition_to_text,
    structured_plan_to_daily_lines,
    structured_shopping_list_to_items,
    structured_shopping_list_to_text,
)


def test_dietary_preferences_to_prompt_contains_preferences() -> None:
    preferences = DietaryPreferences(
        meals_per_day=3,
        calories_per_day=1800,
        budget_per_day=40.0,
        dietary_restrictions=("vegetarian",),
        cuisines=("Mediterranean",),
        avoid_ingredients=("shellfish", "peanuts"),
    )

    prompt = preferences.to_prompt()

    assert "five-day meal plan" in prompt
    assert "vegetarian" in prompt
    assert "Mediterranean" in prompt
    assert "shellfish" in prompt
    assert "peanuts" in prompt
    assert "$40.00" in prompt
    assert "JSON meal plan" in prompt


def test_meal_plan_result_parses_lines_and_summaries() -> None:
    result = MealPlanResult.from_raw(
        raw_meal_plan="Day 1: Salad\nDay 2: Stew",
        raw_shopping_list="- Lettuce\n- Tomatoes",
        nutrition_summary="Balanced protein and fiber.",
        budget_summary="Within budget.",
    )

    assert result.daily_plan == ("Day 1: Salad", "Day 2: Stew")
    assert result.shopping_items == ("Lettuce", "Tomatoes")
    assert result.nutrition_summary == "Balanced protein and fiber."
    assert result.budget_summary == "Within budget."
    assert len(result.structured_plan) == 2


def test_parse_structured_meal_plan_from_json() -> None:
    payload = {
        "days": [
            {
                "day": 1,
                "meals": [
                    {
                        "type": "breakfast",
                        "name": "Oatmeal with berries",
                        "calories": 320,
                        "ingredients": ["oats", "blueberries"],
                        "notes": "Prep overnight",
                    }
                ],
            }
        ]
    }

    days = parse_structured_meal_plan(json.dumps(payload))

    assert len(days) == 1
    assert days[0].day == 1
    assert days[0].meals[0].meal_type == "breakfast"
    assert days[0].meals[0].name == "Oatmeal with berries"
    assert days[0].meals[0].calories == 320
    assert days[0].meals[0].ingredients == ("oats", "blueberries")
    assert days[0].meals[0].notes == "Prep overnight"


def test_parse_structured_meal_plan_from_fenced_json() -> None:
    raw = """Here is the plan:
```json
{
  "days": [
    {
      "day": 2,
      "meals": [
        {
          "type": "lunch",
          "name": "Quinoa bowl",
          "calories": 450,
          "ingredients": ["quinoa", "chickpeas"],
          "notes": ""
        }
      ]
    }
  ]
}
```
"""
    days = parse_structured_meal_plan(raw)

    assert len(days) == 1
    assert days[0].day == 2
    assert days[0].meals[0].meal_type == "lunch"
    assert days[0].meals[0].name == "Quinoa bowl"


def test_structured_plan_to_daily_lines() -> None:
    payload = {
        "days": [
            {
                "day": 1,
                "meals": [
                    {
                        "type": "breakfast",
                        "name": "Oatmeal",
                        "calories": 320,
                        "ingredients": ["oats"],
                        "notes": "",
                    }
                ],
            }
        ]
    }
    structured = parse_structured_meal_plan(json.dumps(payload))
    lines = structured_plan_to_daily_lines(structured)

    assert lines == ("Day 1:", "Breakfast: Oatmeal (320 cal)")


def test_meal_plan_json_schema_has_required_fields() -> None:
    assert MEAL_PLAN_JSON_SCHEMA["required"] == ["days"]
    assert "days" in MEAL_PLAN_JSON_SCHEMA["properties"]


def test_parse_structured_shopping_list_from_json() -> None:
    payload = {
        "categories": [
            {
                "category": "Produce",
                "items": [
                    {"name": "Tomatoes", "quantity": "2 lbs", "notes": "Roma preferred"},
                    {"name": "Spinach", "quantity": "1 bag", "notes": ""},
                ],
            }
        ]
    }

    categories = parse_structured_shopping_list(json.dumps(payload))

    assert len(categories) == 1
    assert categories[0].category == "Produce"
    assert categories[0].items[0].name == "Tomatoes"
    assert categories[0].items[0].quantity == "2 lbs"
    assert categories[0].items[1].name == "Spinach"


def test_meal_plan_result_parses_structured_shopping_list() -> None:
    shopping_json = json.dumps(
        {
            "categories": [
                {
                    "category": "Pantry",
                    "items": [{"name": "Oats", "quantity": "1 lb", "notes": ""}],
                }
            ]
        }
    )
    result = MealPlanResult.from_raw(
        raw_meal_plan='{"days": []}',
        raw_shopping_list=shopping_json,
        nutrition_summary="ok",
        budget_summary="ok",
    )

    assert len(result.structured_shopping_list) == 1
    assert result.shopping_items == ("Oats (1 lb)",)
    assert "Pantry" in result.raw_shopping_list
    assert structured_shopping_list_to_text(result.structured_shopping_list) == result.raw_shopping_list


def test_shopping_list_json_schema_has_required_fields() -> None:
    assert SHOPPING_LIST_JSON_SCHEMA["required"] == ["categories"]
    assert structured_shopping_list_to_items(parse_structured_shopping_list(json.dumps({
        "categories": [{"category": "Dairy", "items": [{"name": "Milk", "quantity": "1 gal"}]}]
    }))) == ("Milk (1 gal)",)


def test_meal_plan_result_falls_back_to_text_lines() -> None:
    result = MealPlanResult.from_raw(
        raw_meal_plan=(
            "Day 1:\n"
            "Breakfast: Greek yogurt parfait (350 cal)\n"
            "Lunch: Lentil soup — with whole grain bread"
        ),
        raw_shopping_list="- Yogurt",
        nutrition_summary="Good balance.",
        budget_summary="On budget.",
    )

    assert len(result.structured_plan) == 1
    day = result.structured_plan[0]
    assert day.day == 1
    assert len(day.meals) == 2
    assert day.meals[0].meal_type == "breakfast"
    assert day.meals[0].name == "Greek yogurt parfait"
    assert day.meals[0].calories == 350
    assert day.meals[1].meal_type == "lunch"
    assert day.meals[1].name == "Lentil soup"
    assert day.meals[1].notes == "with whole grain bread"


def test_parse_structured_nutrition_from_json() -> None:
    payload = {
        "status": "good",
        "summary": "Balanced macros and fiber.",
        "highlights": [
            {"label": "Protein", "detail": "Adequate across all days", "status": "good"}
        ],
        "issues": [
            {"issue": "Low iron on Day 3", "recommendation": "Add spinach or lentils"}
        ],
    }

    nutrition = parse_structured_nutrition(json.dumps(payload))

    assert nutrition is not None
    assert nutrition.status == "good"
    assert nutrition.summary == "Balanced macros and fiber."
    assert nutrition.highlights[0].label == "Protein"
    assert nutrition.issues[0].recommendation == "Add spinach or lentils"


def test_parse_structured_budget_from_json() -> None:
    payload = {
        "status": "within",
        "summary": "Plan fits the daily budget.",
        "estimated_daily_cost": 38.5,
        "highlights": [{"label": "Protein", "detail": "Uses affordable chicken and beans"}],
        "savings_tips": [
            {"item": "Salmon", "alternative": "Canned tuna", "note": "Similar protein profile"}
        ],
    }

    budget = parse_structured_budget(json.dumps(payload))

    assert budget is not None
    assert budget.status == "within"
    assert budget.estimated_daily_cost == 38.5
    assert budget.savings_tips[0].alternative == "Canned tuna"


def test_meal_plan_result_parses_structured_notes() -> None:
    nutrition_json = json.dumps(
        {
            "status": "warning",
            "summary": "Mostly balanced.",
            "issues": [{"issue": "High sodium", "recommendation": "Reduce soy sauce"}],
        }
    )
    budget_json = json.dumps(
        {
            "status": "over",
            "summary": "Slightly above budget.",
            "estimated_daily_cost": 45.0,
        }
    )
    result = MealPlanResult.from_raw(
        raw_meal_plan='{"days": []}',
        raw_shopping_list='{"categories": []}',
        nutrition_summary=nutrition_json,
        budget_summary=budget_json,
    )

    assert result.structured_nutrition is not None
    assert result.structured_nutrition.status == "warning"
    assert result.structured_budget is not None
    assert result.structured_budget.estimated_daily_cost == 45.0
    assert "Mostly balanced." in result.nutrition_summary
    assert structured_nutrition_to_text(result.structured_nutrition) == result.nutrition_summary
    assert structured_budget_to_text(result.structured_budget) == result.budget_summary


def test_notes_json_schemas_have_required_fields() -> None:
    assert NUTRITION_VALIDATION_JSON_SCHEMA["required"] == ["status", "summary"]
    assert BUDGET_VALIDATION_JSON_SCHEMA["required"] == ["status", "summary"]
