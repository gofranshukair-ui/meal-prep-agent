const MEAL_TYPES = [
    { key: 'breakfast', label: 'Breakfast', color: 'var(--breakfast)' },
    { key: 'lunch', label: 'Lunch', color: 'var(--lunch)' },
    { key: 'dinner', label: 'Dinner', color: 'var(--dinner)' },
    { key: 'snack', label: 'Snack', color: 'var(--snack)' },
];

let currentShoppingList = '';
let currentTitle = 'Meal Prep Shopping List';
let mealDays = [];
let selectedDayIndex = 0;

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('mealPlanForm');
    const feedback = document.getElementById('formFeedback');
    const resultsSection = document.getElementById('resultsSection');
    const mealPlanDisplay = document.getElementById('mealPlanDisplay');
    const dayPills = document.getElementById('dayPills');
    const shoppingListDisplay = document.getElementById('shoppingListDisplay');
    const validationFeedback = document.getElementById('validationFeedback');
    const mealsCount = document.getElementById('mealsCount');
    const ingredientsCount = document.getElementById('ingredientsCount');
    const budgetInfo = document.getElementById('budgetInfo');
    const downloadPdfBtn = document.getElementById('downloadPdfBtn');
    const generateBtn = document.getElementById('generateBtn');
    const tabButtons = document.querySelectorAll('.tab-btn');

    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    dayPills.addEventListener('click', (event) => {
        const pill = event.target.closest('.day-pill');
        if (!pill) return;
        selectedDayIndex = Number(pill.dataset.index);
        renderDayPills();
        renderSelectedDay();
    });

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        setLoading(true);
        resultsSection.classList.add('visible');
        switchTab('plan');
        showSkeletons();

        const payload = buildPayload();

        try {
            const response = await fetch('/meal-plan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Unable to generate meal plan');
            }
            const data = await response.json();
            renderResult(data, payload);
            setFeedback('Meal plan generated successfully.', 'success');
            currentShoppingList = data.raw_shopping_list;
            currentTitle = `Shopping List - ${payload.meals_per_day} meals/day`;
            downloadPdfBtn.disabled = false;
            resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } catch (error) {
            console.error(error);
            setFeedback(`Error: ${error.message}`, 'error');
            mealPlanDisplay.innerHTML = '<p class="empty-state">Unable to display meal plan.</p>';
            dayPills.innerHTML = '';
            shoppingListDisplay.innerHTML = '<p class="empty-state">Unable to display shopping list.</p>';
            validationFeedback.innerHTML = '<p class="empty-state">Please try again.</p>';
            downloadPdfBtn.disabled = true;
        } finally {
            setLoading(false);
        }
    });

    downloadPdfBtn.addEventListener('click', async () => {
        if (!currentShoppingList) return;
        const pdfResponse = await fetch('/shopping-list/pdf', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: currentTitle, shopping_list: currentShoppingList }),
        });
        if (!pdfResponse.ok) {
            const error = await pdfResponse.json();
            alert(error.detail || 'Unable to generate PDF');
            return;
        }
        const blob = await pdfResponse.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'shopping_list.pdf';
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    });

    function setLoading(loading) {
        generateBtn.disabled = loading;
        downloadPdfBtn.disabled = loading || !currentShoppingList;
    }

    function setFeedback(text, type) {
        feedback.textContent = text;
        feedback.className = 'feedback' + (type ? ` ${type}` : '');
    }

    function switchTab(tabName) {
        tabButtons.forEach(btn => {
            const isActive = btn.dataset.tab === tabName;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-selected', String(isActive));
        });
        document.querySelectorAll('.tab-panel').forEach(panel => {
            panel.classList.toggle('active', panel.id === `tab-${tabName}`);
        });
    }

    function showSkeletons() {
        mealPlanDisplay.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>';
        dayPills.innerHTML = '';
        shoppingListDisplay.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>';
        validationFeedback.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div>';
    }

    function buildPayload() {
        return {
            meals_per_day: Number(document.getElementById('meals_per_day').value),
            calories_per_day: Number(document.getElementById('calories_per_day').value) || undefined,
            budget_per_day: Number(document.getElementById('budget_per_day').value) || undefined,
            dietary_restrictions: splitCsv('dietary_restrictions'),
            cuisines: splitCsv('cuisines'),
            avoid_ingredients: splitCsv('avoid_ingredients'),
        };
    }

    function splitCsv(id) {
        return document.getElementById(id).value
            .split(',')
            .map(item => item.trim())
            .filter(Boolean);
    }

    function renderResult(data, payload) {
        if (!data.structured_plan?.length) {
            mealDays = [];
            mealPlanDisplay.innerHTML = '<p class="empty-state">No structured meal plan was returned. Please try again.</p>';
            dayPills.innerHTML = '';
        } else {
            mealDays = mapStructuredPlan(data.structured_plan);
            selectedDayIndex = 0;
            renderDayPills();
            renderSelectedDay();
        }

        const shoppingLines = data.structured_shopping_list?.length
            ? flattenStructuredShoppingList(data.structured_shopping_list)
            : (data.shopping_items || []);

        if (!data.structured_shopping_list?.length && !shoppingLines.length) {
            shoppingListDisplay.innerHTML = '<p class="empty-state">No structured shopping list was returned. Please try again.</p>';
        } else if (data.structured_shopping_list?.length) {
            shoppingListDisplay.innerHTML = renderStructuredShoppingList(data.structured_shopping_list);
        } else {
            shoppingListDisplay.innerHTML = `<div class="shopping-list">${shoppingLines.map(item => `
                <label class="shopping-item">
                    <input type="checkbox" />
                    <span>${escapeHtml(item)}</span>
                </label>
            `).join('')}</div>`;
        }

        validationFeedback.innerHTML = renderStructuredNotes(
            data.structured_nutrition,
            data.structured_budget,
            data.nutrition_validation,
            data.budget_validation,
        );

        const totalMeals = mealDays.reduce((sum, day) => sum + day.meals.length, 0);
        mealsCount.textContent = String(totalMeals || data.daily_plan.length);
        ingredientsCount.textContent = String(shoppingLines.length);
        budgetInfo.textContent = payload.budget_per_day
            ? `$${payload.budget_per_day.toFixed(0)}/day`
            : '—';
    }

    function renderDayPills() {
        dayPills.innerHTML = mealDays.map((day, index) => `
            <button type="button" class="day-pill${index === selectedDayIndex ? ' active' : ''}" data-index="${index}">
                ${escapeHtml(day.dayLabel)}
            </button>
        `).join('');
    }

    function renderSelectedDay() {
        const day = mealDays[selectedDayIndex];
        if (!day || day.meals.length === 0) {
            mealPlanDisplay.innerHTML = '<p class="empty-state">No meals for this day.</p>';
            return;
        }
        mealPlanDisplay.innerHTML = `
            <div class="meal-timeline">
                ${day.meals.map(meal => `
                    <article class="meal-row" style="--meal-color: ${meal.color}">
                        <span class="meal-dot" aria-hidden="true"></span>
                        <span class="meal-type-label">${escapeHtml(meal.label)}</span>
                        <p class="meal-name">${escapeHtml(meal.name)}${meal.calories ? ` <span class="meal-calories">${meal.calories} cal</span>` : ''}</p>
                        ${meal.ingredients?.length ? `<p class="meal-details">${escapeHtml(meal.ingredients.join(', '))}</p>` : ''}
                        ${meal.notes ? `<p class="meal-details">${escapeHtml(meal.notes)}</p>` : ''}
                    </article>
                `).join('')}
            </div>
        `;
    }
});

function mapStructuredPlan(structuredPlan) {
    return structuredPlan.map(day => ({
        dayNum: String(day.day),
        dayLabel: `Day ${day.day}`,
        meals: day.meals.map(meal => {
            const typeInfo = MEAL_TYPES.find(item => item.key === meal.type?.toLowerCase()) || {
                key: meal.type || 'meal',
                label: capitalize(meal.type || 'Meal'),
                color: 'var(--sage)',
            };
            return {
                ...typeInfo,
                name: meal.name,
                calories: meal.calories ?? null,
                ingredients: meal.ingredients || [],
                notes: meal.notes || '',
            };
        }),
    }));
}

function capitalize(value) {
    if (!value) return '';
    return value.charAt(0).toUpperCase() + value.slice(1);
}

function flattenStructuredShoppingList(structuredShoppingList) {
    return structuredShoppingList.flatMap(category =>
        category.items.map(item => {
            let label = item.name;
            if (item.quantity) label += ` (${item.quantity})`;
            return label;
        })
    );
}

function renderStructuredShoppingList(structuredShoppingList) {
    return structuredShoppingList.map(category => `
        <section class="shopping-category">
            <h4 class="shopping-category-title">${escapeHtml(category.category)}</h4>
            <div class="shopping-list">
                ${category.items.map(item => `
                    <label class="shopping-item">
                        <input type="checkbox" />
                        <span>
                            <strong>${escapeHtml(item.name)}</strong>
                            ${item.quantity ? `<span class="shopping-quantity"> — ${escapeHtml(item.quantity)}</span>` : ''}
                            ${item.notes ? `<span class="shopping-notes"> (${escapeHtml(item.notes)})</span>` : ''}
                        </span>
                    </label>
                `).join('')}
            </div>
        </section>
    `).join('');
}

function renderStructuredNotes(structuredNutrition, structuredBudget, nutritionText, budgetText) {
    if (!structuredNutrition && !structuredBudget) {
        return '<p class="empty-state">No structured notes were returned. Please try again.</p>';
    }

    return `<div class="notes-grid">
        ${renderValidationCard('Nutrition', structuredNutrition, nutritionText, renderNutritionBody)}
        ${renderValidationCard('Budget', structuredBudget, budgetText, renderBudgetBody)}
    </div>`;
}

function renderValidationCard(title, structured, fallbackText, renderBody) {
    if (!structured) {
        return `<div class="note-card">
            <h4>${escapeHtml(title)}</h4>
            <p>${escapeHtml(fallbackText || 'No data available.')}</p>
        </div>`;
    }

    return `<div class="note-card">
        <div class="note-card-header">
            <h4>${escapeHtml(title)}</h4>
            <span class="note-status note-status-${escapeHtml(structured.status)}">${escapeHtml(formatStatus(structured.status))}</span>
        </div>
        ${renderBody(structured)}
    </div>`;
}

function renderNutritionBody(nutrition) {
    return `
        <p class="note-summary">${escapeHtml(nutrition.summary)}</p>
        ${nutrition.highlights?.length ? `
            <ul class="note-highlights">
                ${nutrition.highlights.map(h => `
                    <li>
                        <strong>${escapeHtml(h.label)}</strong>
                        <span>${escapeHtml(h.detail)}</span>
                        ${h.status ? `<span class="note-highlight-status">${escapeHtml(formatStatus(h.status))}</span>` : ''}
                    </li>
                `).join('')}
            </ul>
        ` : ''}
        ${nutrition.issues?.length ? `
            <div class="note-section">
                <h5>Issues</h5>
                <ul class="note-issues">
                    ${nutrition.issues.map(issue => `
                        <li>
                            <strong>${escapeHtml(issue.issue)}</strong>
                            ${issue.recommendation ? `<span>${escapeHtml(issue.recommendation)}</span>` : ''}
                        </li>
                    `).join('')}
                </ul>
            </div>
        ` : ''}
    `;
}

function renderBudgetBody(budget) {
    return `
        <p class="note-summary">${escapeHtml(budget.summary)}</p>
        ${budget.estimated_daily_cost != null ? `
            <p class="note-cost">Est. daily cost: <strong>$${budget.estimated_daily_cost.toFixed(2)}</strong></p>
        ` : ''}
        ${budget.highlights?.length ? `
            <ul class="note-highlights">
                ${budget.highlights.map(h => `
                    <li>
                        <strong>${escapeHtml(h.label)}</strong>
                        <span>${escapeHtml(h.detail)}</span>
                    </li>
                `).join('')}
            </ul>
        ` : ''}
        ${budget.savings_tips?.length ? `
            <div class="note-section">
                <h5>Savings tips</h5>
                <ul class="note-issues">
                    ${budget.savings_tips.map(tip => `
                        <li>
                            <strong>${escapeHtml(tip.item)}</strong>
                            ${tip.alternative ? `<span>→ ${escapeHtml(tip.alternative)}</span>` : ''}
                            ${tip.note ? `<span class="shopping-notes"> (${escapeHtml(tip.note)})</span>` : ''}
                        </li>
                    `).join('')}
                </ul>
            </div>
        ` : ''}
    `;
}

function formatStatus(status) {
    if (!status) return '';
    return status.replace(/_/g, ' ');
}

function escapeHtml(text) {
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
    return String(text).replace(/[&<>"']/g, m => map[m]);
}
