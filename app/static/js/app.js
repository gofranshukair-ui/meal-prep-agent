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
        mealDays = groupMealsByDay(data.daily_plan);
        selectedDayIndex = 0;

        if (mealDays.length === 0) {
            mealPlanDisplay.innerHTML = '<p class="empty-state">No meal breakdown was returned.</p>';
            dayPills.innerHTML = '';
        } else {
            renderDayPills();
            renderSelectedDay();
        }

        const shoppingLines = data.shopping_items.length
            ? data.shopping_items
            : data.raw_shopping_list.split('\n').map(line => line.trim()).filter(Boolean);

        if (shoppingLines.length === 0) {
            shoppingListDisplay.innerHTML = '<p class="empty-state">No shopping items were returned.</p>';
        } else {
            shoppingListDisplay.innerHTML = `<div class="shopping-list">${shoppingLines.map(item => `
                <label class="shopping-item">
                    <input type="checkbox" />
                    <span>${escapeHtml(item)}</span>
                </label>
            `).join('')}</div>`;
        }

        validationFeedback.innerHTML = `
            <div class="notes-grid">
                <div class="note-card">
                    <h4>Nutrition</h4>
                    <p>${escapeHtml(data.nutrition_validation)}</p>
                </div>
                <div class="note-card">
                    <h4>Budget</h4>
                    <p>${escapeHtml(data.budget_validation)}</p>
                </div>
            </div>
        `;

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
                        <p class="meal-name">${escapeHtml(meal.name)}</p>
                        ${meal.details ? `<p class="meal-details">${escapeHtml(meal.details)}</p>` : ''}
                    </article>
                `).join('')}
            </div>
        `;
    }
});

function splitMealDescription(text) {
    const parenMatch = text.match(/^(.+?)\s*\((.+)\)\s*$/);
    if (parenMatch && parenMatch[1].length < 90) {
        return { name: parenMatch[1].trim(), details: parenMatch[2].trim() };
    }
    const dashMatch = text.match(/^(.+?)\s*[—–-]\s*(.+)$/);
    if (dashMatch && dashMatch[1].length < 90) {
        return { name: dashMatch[1].trim(), details: dashMatch[2].trim() };
    }
    return { name: text, details: '' };
}

function parseMealLine(line) {
    const trimmed = line.replace(/^[-*•]\s*/, '').trim();
    for (const mealType of MEAL_TYPES) {
        const pattern = new RegExp(`^(${mealType.key}|${mealType.label})\\s*[:\\-–—]\\s*(.+)$`, 'i');
        const match = trimmed.match(pattern);
        if (match) {
            return { ...mealType, ...splitMealDescription(match[2].trim()) };
        }
    }
    return {
        label: 'Meal',
        color: 'var(--sage)',
        ...splitMealDescription(trimmed),
    };
}

function groupMealsByDay(dailyPlan) {
    const days = [];
    let currentDay = null;
    dailyPlan.forEach(line => {
        const dayMatch = line.match(/^Day\s*(\d+)\s*[:\-–—]?\s*(.*)$/i);
        if (dayMatch) {
            if (currentDay) days.push(currentDay);
            const remainder = dayMatch[2].trim();
            currentDay = {
                dayNum: dayMatch[1],
                dayLabel: `Day ${dayMatch[1]}`,
                meals: remainder ? [parseMealLine(remainder)] : [],
            };
        } else if (currentDay) {
            currentDay.meals.push(parseMealLine(line));
        } else {
            currentDay = {
                dayNum: String(days.length + 1),
                dayLabel: `Day ${days.length + 1}`,
                meals: [parseMealLine(line)],
            };
        }
    });
    if (currentDay) days.push(currentDay);
    return days;
}

function escapeHtml(text) {
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
    return String(text).replace(/[&<>"']/g, m => map[m]);
}
