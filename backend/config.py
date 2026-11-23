"""
ReliefOps AI — Centralized Application Configuration
Provides strongly-typed, environment-driven configuration management with safe defaults,
secret masking, and path validation for academic and production deployments.

Academic Disclaimer:
Developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv

# Determine root repository directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env if present
ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    load_dotenv(dotenv_path=ENV_FILE)


class Settings:
    """
    Centralized configuration manager reading from environment variables with safe defaults.
    Ensures that secrets and keys are never logged in plain text.
    """

    def __init__(self) -> None:
        self.BASE_DIR: Path = BASE_DIR
        self.ENV_FILE: Path = ENV_FILE

        # Execution Mode: "deterministic" (default, zero-API dependency) or "llm"
        self.EXECUTION_MODE: str = os.getenv("RELIEFOPS_EXECUTION_MODE", "deterministic").strip().lower()

        # Database and Storage Configuration
        db_env = os.getenv("DATABASE_PATH", "data/reliefops.db").strip()
        self.DATABASE_PATH: Path = (self.BASE_DIR / db_env) if not os.path.isabs(db_env) else Path(db_env)

        chroma_env = os.getenv("CHROMADB_PATH", "data/chromadb").strip()
        self.CHROMADB_PATH: Path = (self.BASE_DIR / chroma_env) if not os.path.isabs(chroma_env) else Path(chroma_env)

        sop_env = os.getenv("SOP_DIR", "data/sops").strip()
        self.SOP_DIR: Path = (self.BASE_DIR / sop_env) if not os.path.isabs(sop_env) else Path(sop_env)

        # Logging & Observability
        self.LOG_LEVEL: str = os.getenv("RELIEFOPS_LOG_LEVEL", os.getenv("LOG_LEVEL", "INFO")).strip().upper()
        self.LOG_FILE: Optional[str] = os.getenv("RELIEFOPS_LOG_FILE", None)

        # Optimization & Fairness Policy Defaults
        try:
            self.GINI_THRESHOLD: float = float(os.getenv("GINI_THRESHOLD", "0.35"))
        except ValueError:
            self.GINI_THRESHOLD = 0.35

        try:
            self.SURVIVAL_FLOOR_RATIO: float = float(os.getenv("SURVIVAL_FLOOR_RATIO", "0.30"))
        except ValueError:
            self.SURVIVAL_FLOOR_RATIO = 0.30

        # Geospatial Routing Configuration (Phase 12)
        raw_routing_mode = os.getenv("ROUTING_MODE", "HAVERSINE_FALLBACK").strip().upper()
        self.ROUTING_MODE: str = (
            raw_routing_mode if raw_routing_mode in ("ROAD_NETWORK", "HAVERSINE_FALLBACK") else "HAVERSINE_FALLBACK"
        )
        self.OSRM_BASE_URL: str = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org").strip().rstrip("/")
        try:
            self.ROUTING_TIMEOUT_SECONDS: float = max(0.5, float(os.getenv("ROUTING_TIMEOUT_SECONDS", "5.0")))
        except ValueError:
            self.ROUTING_TIMEOUT_SECONDS = 5.0

        # Server / Host Configurations
        self.APP_HOST: str = os.getenv("STREAMLIT_SERVER_ADDRESS", "0.0.0.0")
        try:
            self.APP_PORT: int = int(os.getenv("STREAMLIT_SERVER_PORT", "8501"))
        except ValueError:
            self.APP_PORT = 8501

        # Optional LLM API Keys (Strictly masked in string representation)
        self.OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
        self.OPENAI_MODEL_ID: str = os.getenv("OPENAI_MODEL_ID", "gpt-4o")
        self.GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
        self.AZURE_OPENAI_API_KEY: Optional[str] = os.getenv("AZURE_OPENAI_API_KEY")
        self.AZURE_OPENAI_ENDPOINT: Optional[str] = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.AZURE_OPENAI_DEPLOYMENT: Optional[str] = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

    @staticmethod
    def mask_secret(secret: Optional[str]) -> str:
        """Masks sensitive strings so they can never be logged in full."""
        if not secret:
            return "<UNSET>"
        clean = secret.strip()
        if len(clean) <= 8:
            return "********"
        return f"{clean[:3]}...{clean[-4:]}"

    def to_dict(self, mask_secrets: bool = True) -> Dict[str, Any]:
        """Returns safe configuration summary dictionary."""
        return {
            "EXECUTION_MODE": self.EXECUTION_MODE,
            "DATABASE_PATH": str(self.DATABASE_PATH),
            "CHROMADB_PATH": str(self.CHROMADB_PATH),
            "SOP_DIR": str(self.SOP_DIR),
            "LOG_LEVEL": self.LOG_LEVEL,
            "GINI_THRESHOLD": self.GINI_THRESHOLD,
            "SURVIVAL_FLOOR_RATIO": self.SURVIVAL_FLOOR_RATIO,
            "ROUTING_MODE": self.ROUTING_MODE,
            "OSRM_BASE_URL": self.OSRM_BASE_URL,
            "ROUTING_TIMEOUT_SECONDS": self.ROUTING_TIMEOUT_SECONDS,
            "APP_HOST": self.APP_HOST,
            "APP_PORT": self.APP_PORT,
            "OPENAI_CONFIGURED": bool(self.OPENAI_API_KEY),
            "GEMINI_CONFIGURED": bool(self.GEMINI_API_KEY),
            "AZURE_CONFIGURED": bool(self.AZURE_OPENAI_API_KEY),
            "OPENAI_API_KEY": self.mask_secret(self.OPENAI_API_KEY) if mask_secrets else self.OPENAI_API_KEY,
            "GEMINI_API_KEY": self.mask_secret(self.GEMINI_API_KEY) if mask_secrets else self.GEMINI_API_KEY,
        }

    def __repr__(self) -> str:
        items = [f"{k}={v}" for k, v in self.to_dict(mask_secrets=True).items()]
        return f"Settings({', '.join(items)})"


# Singleton configuration instance
settings = Settings()
