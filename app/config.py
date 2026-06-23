from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gemini_api_key: str = Field(..., env="GEMINI_API_KEY")
    gemini_model_name: str = Field("models/gemini-2.5-flash", env="GEMINI_MODEL_NAME")
    gemini_fallback_model_names: list[str] = Field(
        default_factory=lambda: [
            "models/gemini-flash-lite-latest",
            "models/gemini-2.5-flash-lite",
            "models/gemini-2.5-pro",
        ],
        env="GEMINI_FALLBACK_MODEL_NAMES",
    )

    @field_validator("gemini_model_name", mode="before")
    def normalize_gemini_model_name(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        legacy_map = {
            "gemini-2.5-flash-lite": "models/gemini-1.5-flash",
            "gemini-1.5-flash": "models/gemini-1.5-flash",
            "gemini-1.5-pro": "models/gemini-1.5-pro",
            "gemini-2.0": "models/gemini-1.5-flash",
        }
        normalized = legacy_map.get(value, value)
        if not normalized.startswith("models/") and normalized.startswith("gemini-"):
            normalized = f"models/{normalized}"
        return normalized
    gemini_max_output_tokens: int = Field(900, env="GEMINI_MAX_OUTPUT_TOKENS")
    gemini_temperature: float = Field(0.3, env="GEMINI_TEMPERATURE")
    gemini_cost_per_prompt_token: float = Field(0.000001, env="GEMINI_COST_PER_PROMPT_TOKEN")
    gemini_cost_per_output_token: float = Field(0.0000015, env="GEMINI_COST_PER_OUTPUT_TOKEN")

    sqlite_db_path: str = Field("workflow_state.db", env="SQLITE_DB_PATH")
    context_compression_enabled: bool = Field(True, env="CONTEXT_COMPRESSION_ENABLED")
    context_compression_threshold: int = Field(1200, env="CONTEXT_COMPRESSION_THRESHOLD")
    recipe_memory_limit: int = Field(5, env="RECIPE_MEMORY_LIMIT")

    langsmith_api_key: str | None = Field(None, env="LANGSMITH_API_KEY")
    langsmith_api_url: str | None = Field(None, env="LANGSMITH_API_URL")
    langsmith_project_name: str = Field("meal-prep-agent", env="LANGSMITH_PROJECT_NAME")
    metrics_recent_requests: int = Field(20, env="METRICS_RECENT_REQUESTS")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
