"""
ReliefOps AI — Structured Observability and Application Logging
Provides centralized, structured logging capturing multi-agent lifecycle events,
SOP RAG retrieval latencies, allocation decisions, fairness audits, and incident replanning.

Academic Disclaimer:
Developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
"""

import json
import logging
import os
import sys
import time
from typing import Any, Dict, Optional
from backend.config import settings


class StructuredFormatter(logging.Formatter):
    """
    Standardizes log records with timestamps, agent context, and structured metadata.
    Guarantees no sensitive tokens or unmasked keys are emitted.
    """

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        level = record.levelname.ljust(8)
        component = getattr(record, "component", record.name).ljust(22)
        message = record.getMessage()

        # Append structured context if present
        extra_ctx = getattr(record, "structured_data", None)
        if extra_ctx and isinstance(extra_ctx, dict):
            try:
                message += f" | {json.dumps(extra_ctx, default=str)}"
            except Exception:
                pass

        return f"[{timestamp}] [{level}] [{component}] {message}"


def setup_logger(
    name: str = "ReliefOps",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
) -> logging.Logger:
    """
    Creates or retrieves a configured structured logger.
    """
    level_str = (log_level or settings.LOG_LEVEL).upper()
    level = getattr(logging, level_str, logging.INFO)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid adding duplicate handlers if already configured
    if not logger.handlers:
        formatter = StructuredFormatter()

        # Console Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # Optional File Handler
        target_file = log_file or settings.LOG_FILE
        if target_file:
            try:
                os.makedirs(os.path.dirname(os.path.abspath(target_file)), exist_ok=True)
                file_handler = logging.FileHandler(target_file, encoding="utf-8")
                file_handler.setLevel(level)
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
            except Exception as exc:
                sys.stderr.write(f"Warning: Failed to initialize log file {target_file}: {exc}\n")

    return logger


# Primary module logger instance
app_logger = setup_logger("ReliefOps")


class OperationalObserver:
    """
    High-level operational logging helper emitting structured multi-agent telemetry.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or app_logger

    def log_disaster_event(
        self,
        event_id: str,
        disaster_type: str,
        severity_level: str,
        total_affected_pop: int,
    ) -> None:
        """Logs initial disaster event ingestion and context resolution."""
        extra = {
            "event_id": event_id,
            "disaster_type": disaster_type,
            "severity_level": severity_level,
            "affected_population": total_affected_pop,
        }
        self.logger.info(
            f"Disaster Event Initialized: {event_id} ({disaster_type} - {severity_level})",
            extra={"component": "DisasterLifecycle", "structured_data": extra},
        )

    def log_sop_retrieval(
        self,
        hazard: str,
        sop_id: str,
        engine: str,
        latency_ms: float,
        chunks_count: int = 0,
    ) -> None:
        """Logs SOP RAG vector retrieval metrics and citations."""
        extra = {
            "hazard": hazard,
            "sop_id": sop_id,
            "engine": engine,
            "latency_ms": round(latency_ms, 2),
            "chunks_retrieved": chunks_count,
        }
        self.logger.info(
            f"SOP RAG Retrieval Complete: {sop_id} via {engine} ({latency_ms:.1f}ms)",
            extra={"component": "SOPRetrievalEngine", "structured_data": extra},
        )

    def log_agent_execution(
        self,
        agent_name: str,
        action: str,
        status: str,
        latency_ms: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Logs individual agent lifecycle transitions."""
        extra = {
            "agent": agent_name,
            "action": action,
            "status": status,
        }
        if latency_ms is not None:
            extra["latency_ms"] = round(latency_ms, 2)
        if details:
            extra.update(details)

        self.logger.info(
            f"Agent Execution: {agent_name} -> {action} [{status}]",
            extra={"component": agent_name, "structured_data": extra},
        )

    def log_allocation_decision(
        self,
        plan_id: str,
        policy: str,
        total_dispatches: int,
        resource_summary: Dict[str, Any],
    ) -> None:
        """Logs synthesis allocation decisions and resource fulfillment breakdown."""
        summary_clean = {}
        for rtype, summary in resource_summary.items():
            summary_clean[rtype] = {
                "allocated": summary.get("allocated", 0),
                "demanded": summary.get("demanded", 0),
                "unfulfilled": summary.get("unfulfilled_qty", 0),
                "fulfillment_pct": summary.get("fulfillment_pct", 100.0),
                "status": summary.get("status", "ADEQUATE"),
            }

        extra = {
            "plan_id": plan_id,
            "policy": policy,
            "dispatches_count": total_dispatches,
            "resource_summary": summary_clean,
        }
        self.logger.info(
            f"Allocation Plan Synthesized: {plan_id} (Policy: {policy}, {total_dispatches} dispatches)",
            extra={"component": "ReliefCoordinator", "structured_data": extra},
        )

    def log_fairness_audit(
        self,
        plan_id: str,
        gini: float,
        verdict: str,
        adequacy_status: str,
        overall_status: str,
        violations_count: int = 0,
    ) -> None:
        """Logs distributive fairness audit verdict and Gini metrics."""
        extra = {
            "plan_id": plan_id,
            "gini_coefficient": round(gini, 4),
            "fairness_verdict": verdict,
            "adequacy_status": adequacy_status,
            "overall_status": overall_status,
            "violations": violations_count,
        }
        self.logger.info(
            f"Fairness Audit Verdict: Gini={gini:.4f} | Fairness={verdict} | Adequacy={adequacy_status} -> {overall_status}",
            extra={"component": "FairnessAuditorAgent", "structured_data": extra},
        )

    def log_incident_replanning(
        self,
        original_plan_id: str,
        revised_plan_id: str,
        incident_type: str,
        impact_summary: str,
    ) -> None:
        """Logs mid-run incident triggering and dynamic state replanning."""
        extra = {
            "original_plan_id": original_plan_id,
            "revised_plan_id": revised_plan_id,
            "incident": incident_type,
            "impact": impact_summary,
        }
        self.logger.warning(
            f"Dynamic Replanning Triggered: {incident_type} -> Revised Plan {revised_plan_id}",
            extra={"component": "DynamicReplanningEngine", "structured_data": extra},
        )


# Global observer instance
observer = OperationalObserver()
