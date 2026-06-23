from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, List, Optional


class MealPlanRequestSchema(BaseModel):
    meals_per_day: int = Field(..., ge=1, le=6, description="Number of meals per day")
    calories_per_day: Optional[int] = Field(None, ge=100, le=5000, description="Optional target calories per day")
    budget_per_day: Optional[float] = Field(None, ge=0, description="Optional budget target per day")
    dietary_restrictions: List[str] = Field(default_factory=list, description="Dietary restrictions for the meal plan")
    cuisines: List[str] = Field(default_factory=list, description="Preferred cuisine styles")
    avoid_ingredients: List[str] = Field(default_factory=list, description="Ingredients to avoid")


class MealPlanResponseSchema(BaseModel):
    raw_meal_plan: str
    raw_shopping_list: str
    nutrition_validation: str
    budget_validation: str
    daily_plan: List[str]
    shopping_items: List[str]

    model_config = {
        "json_schema_extra": {
            "example": {
                "raw_meal_plan": "Day 1: ...\nDay 2: ...",
                "raw_shopping_list": "- Chicken\n- Tomatoes",
                "nutrition_validation": "Balanced macros and appropriate fiber levels.",
                "budget_validation": "The meal plan is within the target budget.",
                "daily_plan": ["Day 1: ...", "Day 2: ..."],
                "shopping_items": ["Chicken", "Tomatoes"],
            }
        }
    }


class RecipeMemorySchema(BaseModel):
    request_id: str
    title: str
    summary: str
    created_at: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "request_id": "abc123",
                "title": "Five-day meal plan",
                "summary": "A balanced five-day meal plan featuring Mediterranean vegetables and lean proteins.",
                "created_at": "2026-06-08T12:00:00Z",
            }
        }
    }


class MetricsAgentSummary(BaseModel):
    calls: int
    average_latency_ms: float
    average_cost_usd: float
    total_prompt_tokens: int
    total_output_tokens: int
    total_cost_usd: float


class MetricsRequestSummary(BaseModel):
    request_id: str
    model_name: str
    created_at: str
    latency_ms: float
    prompt_tokens: int
    output_tokens: int
    cost_usd: float
    agent_calls: int
    operation_names: List[str]


class MetricsDashboardSchema(BaseModel):
    total_requests: int
    total_agent_calls: int
    total_prompt_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    average_latency_ms: float
    average_cost_per_request_usd: float
    agent_breakdown: dict[str, MetricsAgentSummary]
    recent_requests: List[MetricsRequestSummary]


class ShoppingListPdfRequestSchema(BaseModel):
    title: str = Field("Meal Prep Shopping List", description="Title for the generated PDF")
    shopping_list: str = Field(..., description="Raw shopping list text to include in the PDF")


class WorkflowStateSchema(BaseModel):
    request_id: str
    preferences: dict[str, Any]
    meal_plan: str
    nutrition_report: str
    budget_report: str
    shopping_list: str
    compressed_context: str
    created_at: str
    updated_at: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "request_id": "abc123",
                "preferences": {
                    "meals_per_day": 3,
                    "calories_per_day": 1800,
                    "budget_per_day": 40.0,
                    "dietary_restrictions": ["vegetarian"],
                    "cuisines": ["Mediterranean"],
                    "avoid_ingredients": ["peanuts"],
                },
                "meal_plan": "Day 1: ...",
                "nutrition_report": "Balanced nutrition.",
                "budget_report": "Within budget.",
                "shopping_list": "- Lettuce\n- Tomatoes",
                "compressed_context": "...",
                "created_at": "2026-06-08T12:00:00Z",
                "updated_at": "2026-06-08T12:00:05Z",
            }
        }
    }
