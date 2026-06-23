from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from langsmith.client import Client as LangSmithClient

from app.config import settings


@dataclass
class AgentMetrics:
    calls: int = 0
    total_latency_ms: float = 0.0
    total_prompt_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0

    @property
    def average_latency_ms(self) -> float:
        return self.total_latency_ms / self.calls if self.calls else 0.0

    @property
    def average_cost_usd(self) -> float:
        return self.total_cost_usd / self.calls if self.calls else 0.0


@dataclass
class RequestMetrics:
    request_id: str
    model_name: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    prompt_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    agent_calls: int = 0
    operation_names: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def finalize(self) -> None:
        if self.end_time is None:
            self.end_time = time.time()
        self.cost_usd = round(self.cost_usd, 6)

    @property
    def latency_ms(self) -> float:
        if self.end_time is None:
            return round((time.time() - self.start_time) * 1000, 2)
        return round((self.end_time - self.start_time) * 1000, 2)


class MetricsStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.total_requests: int = 0
        self.total_agent_calls: int = 0
        self.total_latency_ms: float = 0.0
        self.total_prompt_tokens: int = 0
        self.total_output_tokens: int = 0
        self.total_cost_usd: float = 0.0
        self.agent_metrics: dict[str, AgentMetrics] = {}
        self.requests: dict[str, RequestMetrics] = {}
        self.recent_requests: list[RequestMetrics] = []
        self.recent_request_limit = settings.metrics_recent_requests
        self.langsmith_client: Optional[LangSmithClient] = self._build_langsmith_client()

    def _build_langsmith_client(self) -> Optional[LangSmithClient]:
        try:
            return LangSmithClient(
                api_key=settings.langsmith_api_key,
                api_url=settings.langsmith_api_url,
            )
        except Exception:
            return None

    def start_request(self, request_id: str, model_name: str, inputs: dict[str, Any]) -> None:
        request_metrics = RequestMetrics(request_id=request_id, model_name=model_name)
        with self._lock:
            self.requests[request_id] = request_metrics
        self._create_langsmith_root_run(request_id, inputs)

    def record_agent_call(
        self,
        request_id: str,
        operation_name: str,
        model_name: str,
        prompt_tokens: int,
        output_tokens: int,
        latency_ms: float,
        cost_usd: float,
        prompt_summary: str,
    ) -> None:
        with self._lock:
            self.total_agent_calls += 1
            self.total_prompt_tokens += prompt_tokens
            self.total_output_tokens += output_tokens
            self.total_cost_usd += cost_usd

            agent_stats = self.agent_metrics.setdefault(operation_name, AgentMetrics())
            agent_stats.calls += 1
            agent_stats.total_latency_ms += latency_ms
            agent_stats.total_prompt_tokens += prompt_tokens
            agent_stats.total_output_tokens += output_tokens
            agent_stats.total_cost_usd += cost_usd

            request_metrics = self.requests.get(request_id)
            if request_metrics is not None:
                request_metrics.prompt_tokens += prompt_tokens
                request_metrics.output_tokens += output_tokens
                request_metrics.cost_usd += cost_usd
                request_metrics.agent_calls += 1
                request_metrics.operation_names.append(operation_name)

        self._create_langsmith_agent_run(
            request_id=request_id,
            operation_name=operation_name,
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            prompt_summary=prompt_summary,
        )

    def finish_request(self, request_id: str, outputs: dict[str, Any]) -> None:
        with self._lock:
            request_metrics = self.requests.get(request_id)
            if request_metrics is None:
                return
            request_metrics.end_time = time.time()
            self.total_requests += 1
            self.total_latency_ms += request_metrics.latency_ms
            self.recent_requests.insert(0, request_metrics)
            self.recent_requests = self.recent_requests[: self.recent_request_limit]
        self._update_langsmith_root_run(request_id, outputs)

    def dashboard(self) -> dict[str, Any]:
        with self._lock:
            average_latency = self.total_latency_ms / self.total_requests if self.total_requests else 0.0
            average_cost = self.total_cost_usd / self.total_requests if self.total_requests else 0.0
            return {
                "total_requests": self.total_requests,
                "total_agent_calls": self.total_agent_calls,
                "total_prompt_tokens": self.total_prompt_tokens,
                "total_output_tokens": self.total_output_tokens,
                "total_cost_usd": round(self.total_cost_usd, 6),
                "average_latency_ms": round(average_latency, 2),
                "average_cost_per_request_usd": round(average_cost, 6),
                "agent_breakdown": {
                    name: {
                        "calls": agent_stats.calls,
                        "average_latency_ms": round(agent_stats.average_latency_ms, 2),
                        "average_cost_usd": round(agent_stats.average_cost_usd, 6),
                        "total_prompt_tokens": agent_stats.total_prompt_tokens,
                        "total_output_tokens": agent_stats.total_output_tokens,
                        "total_cost_usd": round(agent_stats.total_cost_usd, 6),
                    }
                    for name, agent_stats in self.agent_metrics.items()
                },
                "recent_requests": [
                    {
                        "request_id": request.request_id,
                        "model_name": request.model_name,
                        "created_at": request.created_at,
                        "latency_ms": request.latency_ms,
                        "prompt_tokens": request.prompt_tokens,
                        "output_tokens": request.output_tokens,
                        "cost_usd": round(request.cost_usd, 6),
                        "agent_calls": request.agent_calls,
                        "operation_names": request.operation_names,
                    }
                    for request in self.recent_requests
                ],
            }

    def _create_langsmith_root_run(self, request_id: str, inputs: dict[str, Any]) -> None:
        if self.langsmith_client is None:
            return
        try:
            self.langsmith_client.create_run(
                id=request_id,
                project_name=settings.langsmith_project_name,
                name=f"meal_plan_request_{request_id}",
                run_type="chain",
                inputs={"preferences": inputs},
                outputs={"status": "started"},
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
            )
        except Exception:
            return

    def _update_langsmith_root_run(self, request_id: str, outputs: dict[str, Any]) -> None:
        if self.langsmith_client is None:
            return
        try:
            self.langsmith_client.update_run(
                request_id,
                outputs={"result": outputs},
                end_time=datetime.now(timezone.utc),
            )
        except Exception:
            return

    def _create_langsmith_agent_run(
        self,
        request_id: str,
        operation_name: str,
        model_name: str,
        prompt_tokens: int,
        output_tokens: int,
        latency_ms: float,
        cost_usd: float,
        prompt_summary: str,
    ) -> None:
        if self.langsmith_client is None:
            return
        run_id = str(uuid.uuid4())
        try:
            self.langsmith_client.create_run(
                id=run_id,
                project_name=settings.langsmith_project_name,
                name=f"{operation_name}:{model_name}",
                run_type="llm",
                inputs={
                    "operation": operation_name,
                    "model": model_name,
                    "prompt_summary": prompt_summary,
                    "prompt_tokens": prompt_tokens,
                },
                outputs={
                    "latency_ms": round(latency_ms, 2),
                    "output_tokens": output_tokens,
                    "cost_usd": round(cost_usd, 6),
                },
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
            )
        except Exception:
            return


metrics = MetricsStore()
