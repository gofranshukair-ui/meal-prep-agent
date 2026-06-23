(() => {
    const CHART_COLORS = ['#3d6b4f', '#c45c3e', '#d97706', '#4f46e5', '#db2777', '#059669'];
    const REFRESH_INTERVAL_MS = 5000;

    const charts = {
        token: null,
        agentCalls: null,
        agentCosts: null,
        latency: null,
    };

    const refreshBtn = document.getElementById('refreshBtn');
    const lastUpdated = document.getElementById('lastUpdated');

    refreshBtn.addEventListener('click', refreshMetrics);
    setInterval(refreshMetrics, REFRESH_INTERVAL_MS);
    refreshMetrics();

    async function refreshMetrics() {
        try {
            document.body.classList.add('is-loading');
            const response = await fetch('/metrics');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            updateDashboard(await response.json());
            lastUpdated.textContent = `Updated ${new Date().toLocaleTimeString()}`;
        } catch (error) {
            console.error('Failed to fetch metrics:', error);
            lastUpdated.textContent = 'Failed to load metrics';
        } finally {
            document.body.classList.remove('is-loading');
        }
    }

    function updateDashboard(data) {
        document.getElementById('totalRequests').textContent = formatNumber(data.total_requests);
        document.getElementById('totalCalls').textContent = formatNumber(data.total_agent_calls);
        document.getElementById('totalTokens').textContent = formatNumber(
            data.total_prompt_tokens + data.total_output_tokens
        );
        document.getElementById('totalCost').textContent = formatCost(data.total_cost_usd, 4);
        document.getElementById('avgLatency').textContent = `${data.average_latency_ms.toFixed(0)} ms`;
        document.getElementById('avgCost').textContent = formatCost(data.average_cost_per_request_usd, 6);

        updateTokenChart(data);
        updateAgentCallsChart(data);
        updateAgentCostsChart(data);
        updateLatencyChart(data);
        updateAgentBreakdown(data);
        updateRecentRequests(data);
    }

    function updateTokenChart(data) {
        const ctx = document.getElementById('tokenChart').getContext('2d');
        destroyChart('token');
        charts.token = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Prompt tokens', 'Output tokens'],
                datasets: [{
                    data: [data.total_prompt_tokens, data.total_output_tokens],
                    backgroundColor: [CHART_COLORS[0], CHART_COLORS[1]],
                    borderColor: '#ffffff',
                    borderWidth: 2,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'bottom' } },
            },
        });
    }

    function updateAgentCallsChart(data) {
        const agents = Object.keys(data.agent_breakdown);
        const ctx = document.getElementById('agentCallsChart').getContext('2d');
        destroyChart('agentCalls');
        charts.agentCalls = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: agents.map(formatAgentName),
                datasets: [{
                    label: 'Calls',
                    data: agents.map(name => data.agent_breakdown[name].calls),
                    backgroundColor: CHART_COLORS[0],
                    borderRadius: 4,
                }],
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: { x: { beginAtZero: true, ticks: { precision: 0 } } },
            },
        });
    }

    function updateAgentCostsChart(data) {
        const agents = Object.keys(data.agent_breakdown);
        const ctx = document.getElementById('agentCostsChart').getContext('2d');
        destroyChart('agentCosts');
        charts.agentCosts = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: agents.map(formatAgentName),
                datasets: [{
                    label: 'Cost ($)',
                    data: agents.map(name => data.agent_breakdown[name].total_cost_usd),
                    backgroundColor: CHART_COLORS[1],
                    borderRadius: 4,
                }],
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: { x: { beginAtZero: true } },
            },
        });
    }

    function updateLatencyChart(data) {
        const requests = [...data.recent_requests].reverse();
        const ctx = document.getElementById('latencyChart').getContext('2d');
        destroyChart('latency');

        if (!requests.length) {
            charts.latency = new Chart(ctx, {
                type: 'line',
                data: { labels: [], datasets: [] },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        title: {
                            display: true,
                            text: 'No requests yet',
                            color: '#6b5f52',
                            font: { size: 14, weight: 'normal' },
                        },
                    },
                },
            });
            return;
        }

        charts.latency = new Chart(ctx, {
            type: 'line',
            data: {
                labels: requests.map((_, index) => `#${index + 1}`),
                datasets: [{
                    label: 'Latency (ms)',
                    data: requests.map(req => req.latency_ms),
                    borderColor: CHART_COLORS[0],
                    backgroundColor: 'rgba(61, 107, 79, 0.12)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 4,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true } },
            },
        });
    }

    function updateAgentBreakdown(data) {
        const container = document.getElementById('agentBreakdown');
        const agents = Object.keys(data.agent_breakdown);

        if (!agents.length) {
            container.innerHTML = '<li class="empty-state">No agents have run yet.</li>';
            return;
        }

        container.innerHTML = agents.map(agent => {
            const stats = data.agent_breakdown[agent];
            return `
                <li class="agent-item">
                    <div class="agent-name">${escapeHtml(formatAgentName(agent))}</div>
                    <div class="agent-stats">
                        <div>Calls: <span class="agent-stat-value">${stats.calls}</span></div>
                        <div>Avg latency: <span class="agent-stat-value">${stats.average_latency_ms.toFixed(0)} ms</span></div>
                        <div>Tokens: <span class="agent-stat-value">${formatNumber(stats.total_prompt_tokens + stats.total_output_tokens)}</span></div>
                        <div>Cost: <span class="agent-stat-value">${formatCost(stats.total_cost_usd, 6)}</span></div>
                    </div>
                </li>
            `;
        }).join('');
    }

    function updateRecentRequests(data) {
        const tbody = document.getElementById('recentRequestsBody');

        if (!data.recent_requests.length) {
            tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No requests yet.</td></tr>';
            return;
        }

        tbody.innerHTML = data.recent_requests.map(req => `
            <tr>
                <td class="request-id" title="${escapeHtml(req.request_id)}">${escapeHtml(req.request_id.slice(0, 8))}</td>
                <td>${escapeHtml(formatModelName(req.model_name))}</td>
                <td>${escapeHtml(formatTimestamp(req.created_at))}</td>
                <td>${req.latency_ms.toFixed(0)} ms</td>
                <td>${formatNumber(req.prompt_tokens + req.output_tokens)}</td>
                <td>${formatCost(req.cost_usd, 6)}</td>
                <td>${req.agent_calls}</td>
                <td class="operations-cell">${escapeHtml(req.operation_names.join(', '))}</td>
            </tr>
        `).join('');
    }

    function destroyChart(key) {
        if (charts[key]) {
            charts[key].destroy();
            charts[key] = null;
        }
    }

    function formatAgentName(name) {
        return name.replace(/_/g, ' ');
    }

    function formatModelName(name) {
        return name.replace(/^models\//, '');
    }

    function formatTimestamp(value) {
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
            return value;
        }
        return date.toLocaleString(undefined, {
            month: 'short',
            day: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
        });
    }

    function formatNumber(value) {
        return Number(value || 0).toLocaleString();
    }

    function formatCost(value, decimals) {
        return `$${Number(value || 0).toFixed(decimals)}`;
    }

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }
})();
