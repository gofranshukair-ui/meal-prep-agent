from __future__ import annotations

import uuid

from app.domain.models import MealPlanResult
from app.schemas import MealPlanRequestSchema
from app.workflows.meal_plan_workflow import meal_plan_supervisor


class MealPlanUseCase:
    def create_plan(self, request: MealPlanRequestSchema) -> MealPlanResult:
        request_id = uuid.uuid4().hex
        result = meal_plan_supervisor.invoke(request.dict(), request_id=request_id)
        return MealPlanResult.from_raw(
            raw_meal_plan=result["meal_plan"],
            raw_shopping_list=result["shopping_list"],
            nutrition_summary=result["nutrition_report"],
            budget_summary=result["budget_report"],
        )
