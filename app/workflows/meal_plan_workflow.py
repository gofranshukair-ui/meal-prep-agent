from __future__ import annotations

import uuid
from typing import Any

from langgraph.func import entrypoint, task

from app.adapters.gemini_adapter import GeminiAI
from app.config import settings
from app.context import build_compressed_context, compress_text
from app.domain.models import (
    BUDGET_VALIDATION_JSON_SCHEMA,
    DietaryPreferences,
    MEAL_PLAN_JSON_SCHEMA,
    NUTRITION_VALIDATION_JSON_SCHEMA,
    SHOPPING_LIST_JSON_SCHEMA,
)
from app.metrics import metrics
from app.state import state_store


_ai_client = GeminiAI()


def _build_meal_plan_prompt(preferences: DietaryPreferences, recipe_memory_context: str = "") -> str:
    prompt_lines = []
    if recipe_memory_context:
        prompt_lines.extend([
            "Use the following previous recipe knowledge to improve variety, reuse pantry-friendly ingredients, and avoid repeating meals:",
            recipe_memory_context,
            "",
        ])
    prompt_lines.append(preferences.to_prompt())
    return "\n".join(prompt_lines)


def _build_recipe_memory_prompt(previous_recipes: str, preferences: DietaryPreferences) -> str:
    prompt_lines = [
        "You are a meal planning assistant with access to previously generated recipes.",
        "Review the previous recipe memory summaries and provide concise planning guidance",
        "that preserves dietary restrictions, balances calories, and encourages ingredient variety.",
        "",
        "Previous recipes:",
        previous_recipes,
        "",
        "Current preferences:",
        preferences.to_prompt(),
        "",
        "Provide a short planning context that the meal planning agent should use when creating a new five-day meal plan.",
    ]
    return "\n".join(prompt_lines)


def _build_recipe_summary(meal_plan: str, preferences: DietaryPreferences) -> str:
    summary_lines = [
        "A five-day meal plan based on the given dietary preferences.",
        preferences.to_prompt(),
        "Meal Plan Summary:",
        meal_plan[:1000].strip(),
    ]
    return "\n".join(summary_lines)


def _build_nutrition_validation_prompt(meal_plan: str, preferences: DietaryPreferences) -> str:
    prompt_lines = [
        "Review the following five-day meal plan and provide a nutrition validation report.",
        "Confirm whether the plan meets dietary restrictions, calorie targets, and balanced macronutrients.",
        "Return JSON matching the required schema.",
        "Use status values: good, warning, or concern.",
        "Include highlights for key nutrition areas and issues with recommendations when needed.",
        "",
        "Meal Plan:\n",
        meal_plan,
    ]
    if preferences.calories_per_day:
        prompt_lines.append(f"Target calories per day: {preferences.calories_per_day}")
    if preferences.dietary_restrictions:
        prompt_lines.append("Dietary restrictions: " + ", ".join(preferences.dietary_restrictions))
    if preferences.cuisines:
        prompt_lines.append("Preferred cuisines: " + ", ".join(preferences.cuisines))
    if preferences.avoid_ingredients:
        prompt_lines.append("Avoid: " + ", ".join(preferences.avoid_ingredients))

    return "\n".join(prompt_lines)


def _build_budget_validation_prompt(meal_plan: str, preferences: DietaryPreferences) -> str:
    prompt_lines = [
        "Review the following five-day meal plan and estimate its budget compatibility.",
        "If a budget target is provided, state whether the plan is likely within that budget.",
        "Return JSON matching the required schema.",
        "Use status values: within, over, or unknown.",
        "Include highlights, estimated daily cost when possible, and savings tips for expensive items.",
        "",
        "Meal Plan:\n",
        meal_plan,
    ]
    if preferences.budget_per_day is not None:
        prompt_lines.append(f"Budget target: ${preferences.budget_per_day:.2f} per day")
    if preferences.avoid_ingredients:
        prompt_lines.append("Avoid: " + ", ".join(preferences.avoid_ingredients))

    return "\n".join(prompt_lines)


def _build_shopping_optimization_prompt(meal_plan: str, preferences: DietaryPreferences) -> str:
    prompt_lines = [
        "Generate an optimized shopping list for the five-day meal plan below.",
        "Group items by category (Produce, Protein, Dairy, Pantry, etc.) and avoid duplicates.",
        "Prefer budget-friendly substitutions and pantry-friendly ingredients when possible.",
        "Return a JSON shopping list matching the required schema.",
        "",
        "Meal Plan:\n",
        meal_plan,
    ]
    if preferences.budget_per_day is not None:
        prompt_lines.append(f"Budget target: ${preferences.budget_per_day:.2f} per day")
    if preferences.dietary_restrictions:
        prompt_lines.append("Dietary restrictions: " + ", ".join(preferences.dietary_restrictions))
    if preferences.cuisines:
        prompt_lines.append("Preferred cuisines: " + ", ".join(preferences.cuisines))
    if preferences.avoid_ingredients:
        prompt_lines.append("Avoid: " + ", ".join(preferences.avoid_ingredients))

    return "\n".join(prompt_lines)


@task
def meal_planning_agent(prompt: str, request_id: str | None = None) -> str:
    return _ai_client.generate_json(
        prompt,
        schema=MEAL_PLAN_JSON_SCHEMA,
        max_output_tokens=max(settings.gemini_max_output_tokens, 2500),
        temperature=settings.gemini_temperature,
        request_id=request_id,
        operation_name="meal_planning",
    )


@task
def recipe_memory_agent(previous_recipes: str, preferences: DietaryPreferences, request_id: str | None = None) -> str:
    return _ai_client.generate_text(
        _build_recipe_memory_prompt(previous_recipes, preferences),
        max_output_tokens=400,
        temperature=0.2,
        request_id=request_id,
        operation_name="recipe_memory",
    )


@task
def nutrition_validation_agent(meal_plan: str, preferences: DietaryPreferences, request_id: str | None = None) -> str:
    return _ai_client.generate_json(
        _build_nutrition_validation_prompt(meal_plan, preferences),
        schema=NUTRITION_VALIDATION_JSON_SCHEMA,
        max_output_tokens=600,
        temperature=0.2,
        request_id=request_id,
        operation_name="nutrition_validation",
    )


@task
def budget_validation_agent(meal_plan: str, preferences: DietaryPreferences, request_id: str | None = None) -> str:
    return _ai_client.generate_json(
        _build_budget_validation_prompt(meal_plan, preferences),
        schema=BUDGET_VALIDATION_JSON_SCHEMA,
        max_output_tokens=600,
        temperature=0.2,
        request_id=request_id,
        operation_name="budget_validation",
    )


@task
def shopping_optimization_agent(meal_plan: str, preferences: DietaryPreferences, request_id: str | None = None) -> str:
    return _ai_client.generate_json(
        _build_shopping_optimization_prompt(meal_plan, preferences),
        schema=SHOPPING_LIST_JSON_SCHEMA,
        max_output_tokens=max(settings.gemini_max_output_tokens, 1500),
        temperature=settings.gemini_temperature,
        request_id=request_id,
        operation_name="shopping_optimization",
    )


@entrypoint()
def meal_plan_supervisor(preferences: dict[str, Any], request_id: str | None = None) -> dict[str, str]:
    if request_id is None:
        request_id = uuid.uuid4().hex

    existing_state = state_store.get_state(request_id)
    if existing_state and existing_state.meal_plan and existing_state.shopping_list:
        return {
            "meal_plan": existing_state.meal_plan,
            "nutrition_report": existing_state.nutrition_report,
            "budget_report": existing_state.budget_report,
            "shopping_list": existing_state.shopping_list,
        }

    dietary_preferences = DietaryPreferences.from_mapping(preferences)
    metrics.start_request(request_id=request_id, model_name=settings.gemini_model_name, inputs=preferences)

    state_store.update_state(
        request_id=request_id,
        preferences=preferences,
        meal_plan="",
        nutrition_report="",
        budget_report="",
        shopping_list="",
        compressed_context="",
    )

    previous_recipe_context = state_store.get_previous_recipe_context()
    recipe_memory_context = ""
    if previous_recipe_context:
        recipe_memory_context = recipe_memory_agent(previous_recipe_context, dietary_preferences, request_id=request_id).result()

    meal_plan_prompt = _build_meal_plan_prompt(dietary_preferences, recipe_memory_context)
    meal_plan = meal_planning_agent(meal_plan_prompt, request_id=request_id).result()
    state_store.update_state(
        request_id=request_id,
        preferences=preferences,
        meal_plan=meal_plan,
        compressed_context=build_compressed_context(preferences, meal_plan),
    )

    compressed_meal_plan = compress_text(meal_plan, settings.context_compression_threshold)
    nutrition_report_future = nutrition_validation_agent(compressed_meal_plan, dietary_preferences, request_id=request_id)
    budget_report_future = budget_validation_agent(compressed_meal_plan, dietary_preferences, request_id=request_id)
    shopping_list_future = shopping_optimization_agent(compressed_meal_plan, dietary_preferences, request_id=request_id)

    nutrition_report = nutrition_report_future.result()
    budget_report = budget_report_future.result()
    shopping_list = shopping_list_future.result()

    outputs = {
        "meal_plan": meal_plan,
        "nutrition_report": nutrition_report,
        "budget_report": budget_report,
        "shopping_list": shopping_list,
    }
    state_store.update_state(
        request_id=request_id,
        preferences=preferences,
        meal_plan=meal_plan,
        nutrition_report=nutrition_report,
        budget_report=budget_report,
        shopping_list=shopping_list,
        compressed_context=build_compressed_context(preferences, meal_plan, shopping_list),
    )

    state_store.save_recipe_memory(
        request_id=request_id,
        title="Five-day meal plan",
        summary=_build_recipe_summary(meal_plan, dietary_preferences),
    )

    metrics.finish_request(request_id=request_id, outputs=outputs)

    return outputs
