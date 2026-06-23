from __future__ import annotations

from io import BytesIO
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas

from app.metrics import metrics
from app.domain.models import BudgetValidation, NutritionValidation
from app.schemas import (
    BudgetValidationSchema,
    DayPlanSchema,
    MealPlanRequestSchema,
    MealPlanResponseSchema,
    MealSchema,
    MetricsDashboardSchema,
    NutritionValidationSchema,
    RecipeMemorySchema,
    ShoppingCategorySchema,
    ShoppingItemSchema,
    ShoppingListPdfRequestSchema,
    ValidationHighlightSchema,
    ValidationIssueSchema,
    SavingsTipSchema,
    WorkflowStateSchema,
)
from app.state import state_store
from app.use_cases.meal_plan_use_case import MealPlanUseCase

app = FastAPI(
    title="Meal Prep Agent",
    description="Generate a five-day meal plan and shopping list from dietary preferences.",
    version="0.1.0",
)

planner = MealPlanUseCase()

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _nutrition_to_schema(
    nutrition: NutritionValidation | None,
) -> NutritionValidationSchema | None:
    if nutrition is None:
        return None
    return NutritionValidationSchema(
        status=nutrition.status,
        summary=nutrition.summary,
        highlights=[
            ValidationHighlightSchema(
                label=highlight.label,
                detail=highlight.detail,
                status=highlight.status,
            )
            for highlight in nutrition.highlights
        ],
        issues=[
            ValidationIssueSchema(
                issue=issue.issue,
                recommendation=issue.recommendation,
            )
            for issue in nutrition.issues
        ],
    )


def _budget_to_schema(budget: BudgetValidation | None) -> BudgetValidationSchema | None:
    if budget is None:
        return None
    return BudgetValidationSchema(
        status=budget.status,
        summary=budget.summary,
        estimated_daily_cost=budget.estimated_daily_cost,
        highlights=[
            ValidationHighlightSchema(
                label=highlight.label,
                detail=highlight.detail,
                status=highlight.status,
            )
            for highlight in budget.highlights
        ],
        savings_tips=[
            SavingsTipSchema(
                item=tip.item,
                alternative=tip.alternative,
                note=tip.note,
            )
            for tip in budget.savings_tips
        ],
    )


@app.post("/meal-plan", response_model=MealPlanResponseSchema)
def create_meal_plan(request: MealPlanRequestSchema) -> MealPlanResponseSchema:
    try:
        result = planner.create_plan(request)
        return MealPlanResponseSchema(
            raw_meal_plan=result.raw_meal_plan,
            raw_shopping_list=result.raw_shopping_list,
            nutrition_validation=result.nutrition_summary,
            budget_validation=result.budget_summary,
            daily_plan=list(result.daily_plan),
            shopping_items=list(result.shopping_items),
            structured_plan=[
                DayPlanSchema(
                    day=day.day,
                    meals=[
                        MealSchema(
                            type=meal.meal_type,
                            name=meal.name,
                            calories=meal.calories,
                            ingredients=list(meal.ingredients),
                            notes=meal.notes,
                        )
                        for meal in day.meals
                    ],
                )
                for day in result.structured_plan
            ],
            structured_shopping_list=[
                ShoppingCategorySchema(
                    category=category.category,
                    items=[
                        ShoppingItemSchema(
                            name=item.name,
                            quantity=item.quantity,
                            notes=item.notes,
                        )
                        for item in category.items
                    ],
                )
                for category in result.structured_shopping_list
            ],
            structured_nutrition=_nutrition_to_schema(result.structured_nutrition),
            structured_budget=_budget_to_schema(result.structured_budget),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/")
def get_ui() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/shopping-list/pdf")
def generate_shopping_list_pdf(request: ShoppingListPdfRequestSchema):
    buffer = BytesIO()
    canvas = Canvas(buffer, pagesize=letter)
    width, height = letter
    margin = 50
    y = height - margin

    canvas.setFont('Helvetica-Bold', 18)
    canvas.drawString(margin, y, request.title)
    y -= 28
    canvas.setFont('Helvetica', 10)
    canvas.drawString(
        margin,
        y,
        f'Generated by Meal Prep Agent on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
    )
    y -= 28
    canvas.setFont('Helvetica', 12)

    for line in request.shopping_list.splitlines():
        line = line.strip()
        if not line:
            continue
        if y < margin + 30:
            canvas.showPage()
            y = height - margin
            canvas.setFont('Helvetica', 12)
        canvas.drawString(margin, y, line)
        y -= 18

    canvas.showPage()
    canvas.save()
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type='application/pdf',
        headers={'Content-Disposition': 'attachment; filename="shopping_list.pdf"'},
    )


@app.get("/metrics", response_model=MetricsDashboardSchema)
def get_metrics() -> MetricsDashboardSchema:
    dashboard_data = metrics.dashboard()
    return MetricsDashboardSchema(**dashboard_data)


@app.get("/recipe-memory", response_model=list[RecipeMemorySchema])
def get_recipe_memory() -> list[RecipeMemorySchema]:
    memories = state_store.get_recent_recipe_memories()
    return [RecipeMemorySchema(**memory.__dict__) for memory in memories]


@app.get("/workflow-state/{request_id}", response_model=WorkflowStateSchema)
def get_workflow_state(request_id: str) -> WorkflowStateSchema:
    state = state_store.get_state(request_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Workflow state not found for request_id {request_id}")
    return WorkflowStateSchema(**state.to_dict())


@app.get("/metrics/html")
def get_metrics_html() -> FileResponse:
    return FileResponse(STATIC_DIR / "metrics.html")
