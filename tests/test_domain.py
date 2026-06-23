from app.domain.models import DietaryPreferences, MealPlanResult


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
