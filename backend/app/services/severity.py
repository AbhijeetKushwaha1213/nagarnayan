"""
Dedicated Severity Service — Deterministic, Explainable Municipal Severity Engine.

Evaluates and escalates Urban Event severity (LOW, MEDIUM, HIGH, CRITICAL)
based on multi-factor municipal risk, persistence, and multi-bus verification.
Confidence represents AI detection probability and does NOT directly equal severity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any

from app.models.event import Event, EventSeverity, EventType

logger = logging.getLogger("nagar_nayan.severity")

# Numerical severity ranking for monotonic comparison and escalation
SEVERITY_ORDER: dict[EventSeverity, int] = {
    EventSeverity.LOW: 1,
    EventSeverity.MEDIUM: 2,
    EventSeverity.HIGH: 3,
    EventSeverity.CRITICAL: 4,
}

# Inherent municipal infrastructure risk tier by event type
BASE_SEVERITY_BY_TYPE: dict[EventType, EventSeverity] = {
    # Structural life-safety hazards: potential catastrophic head-on vehicular collision
    EventType.MISSING_DIVIDER: EventSeverity.CRITICAL,

    # Direct vehicular road hazards: wheel rupture, loss of steering control, hydroplaning
    EventType.POTHOLE: EventSeverity.MEDIUM,
    EventType.WATERLOGGING: EventSeverity.MEDIUM,

    # Infrastructure degradation and municipal impediment
    EventType.DAMAGED_ROAD: EventSeverity.LOW,
    EventType.MISSING_ZEBRA_CROSSING: EventSeverity.LOW,
    EventType.TRAFFIC_CONGESTION: EventSeverity.LOW,

    # Informational or minor municipal defects
    EventType.MISSING_SIGNBOARD: EventSeverity.LOW,
    EventType.OTHER: EventSeverity.LOW,

    # Road object categories (transient observations, not structural defects)
    EventType.VEHICLE: EventSeverity.LOW,
    EventType.PEDESTRIAN: EventSeverity.LOW,
}


@dataclass
class SeverityEvaluationResult:
    """Detailed, explainable result of a severity evaluation."""

    severity: EventSeverity
    score: float
    reasons: list[str] = field(default_factory=list)
    factors: dict[str, Any] = field(default_factory=dict)
    bus_bonus: float = 0.0
    count_bonus: float = 0.0
    persistence_bonus: float = 0.0


class SeverityService:
    """
    Dedicated Severity Engine for Urban Events.

    Calculates deterministic, explainable municipal severity using:
      1. Baseline Event Type risk tier (physical hazard impact).
      2. Multi-vehicle confirmation (distinct buses verifying the issue).
      3. Supporting detection count (repeated observations).
      4. Persistence duration (first_detected_at to last_detected_at).

    Strict Invariants:
      - Confidence does NOT equal severity.
      - Monotonic escalation: active events do not automatically downgrade.
      - Full explainability: stores reasons and evaluated metrics in event metadata.
    """

    @staticmethod
    def severity_rank(severity: EventSeverity) -> int:
        """Return numerical rank for severity comparison."""
        return SEVERITY_ORDER.get(severity, 1)

    def calculate_severity(self, event: Event) -> SeverityEvaluationResult:
        """
        Evaluate severity deterministically for an Event.
        Returns a SeverityEvaluationResult with the evaluated tier, numerical score, and reasons.
        """
        reasons: list[str] = []
        base_severity = BASE_SEVERITY_BY_TYPE.get(event.event_type, EventSeverity.LOW)
        base_score = float(self.severity_rank(base_severity))
        reasons.append(f"Baseline risk for {event.event_type.value}: {base_severity.value}")

        metadata = dict(event.extra_metadata or {})
        detection_count = int(metadata.get("detection_count", 1))
        reporting_buses = list(metadata.get("reporting_buses", []))
        if "distinct_buses" in metadata:
            distinct_bus_count = int(metadata["distinct_buses"])
        elif reporting_buses:
            distinct_bus_count = len(set(reporting_buses))
        elif getattr(event, "bus_id", None):
            distinct_bus_count = 1
        else:
            distinct_bus_count = 0

        # Calculate duration in seconds
        duration_seconds = 0.0
        if event.first_detected_at and event.last_detected_at:
            duration_seconds = max(
                0.0,
                (event.last_detected_at - event.first_detected_at).total_seconds(),
            )

        score = base_score
        bus_bonus = 0.0
        count_bonus = 0.0
        persistence_bonus = 0.0

        # Factor 1: Multi-bus cross-verification (+1 tier weight if >= 2 distinct buses)
        # Eliminates single-vehicle camera lens artifacts or isolated false readings
        if distinct_bus_count >= 2:
            bus_bonus = 1.0
            score += bus_bonus
            reasons.append(
                f"Multi-bus confirmation: verified by {distinct_bus_count} distinct buses (+1.0 tier)"
            )

        # Factor 2: Repeated observations (detection count)
        if detection_count >= 5:
            count_bonus = 1.0
            score += count_bonus
            reasons.append(
                f"High observation frequency: {detection_count} supporting detections (+1.0 tier)"
            )
        elif detection_count >= 3:
            count_bonus = 0.5
            score += count_bonus
            reasons.append(
                f"Repeated observations: {detection_count} supporting detections (+0.5 tier)"
            )

        # Factor 3: Persistence over time
        if duration_seconds >= 300.0:
            persistence_bonus = 1.0
            score += persistence_bonus
            reasons.append(
                f"Long persistence: observed over {int(duration_seconds)}s (+1.0 tier)"
            )
        elif duration_seconds >= 120.0:
            persistence_bonus = 0.5
            score += persistence_bonus
            reasons.append(
                f"Sustained presence: observed over {int(duration_seconds)}s (+0.5 tier)"
            )

        # Factor 4: Special life-safety priority for missing divider
        # Missing divider with ANY multi-bus confirmation or >= 3 detections escalates immediately to CRITICAL
        if event.event_type == EventType.MISSING_DIVIDER:
            if distinct_bus_count >= 2 or detection_count >= 3 or duration_seconds >= 60.0:
                score = max(score, 4.0)
                reasons.append("Critical life-safety hazard: confirmed missing road divider escalated to CRITICAL")

        # Map score to EventSeverity
        # Score thresholds: < 2.0 -> LOW, [2.0, 3.0) -> MEDIUM, [3.0, 4.0) -> HIGH, >= 4.0 -> CRITICAL
        if score >= 4.0:
            calculated_severity = EventSeverity.CRITICAL
        elif score >= 3.0:
            calculated_severity = EventSeverity.HIGH
        elif score >= 2.0:
            calculated_severity = EventSeverity.MEDIUM
        else:
            calculated_severity = EventSeverity.LOW

        factors = {
            "event_type": event.event_type.value,
            "base_severity": base_severity.value,
            "detection_count": detection_count,
            "distinct_bus_count": distinct_bus_count,
            "duration_seconds": round(duration_seconds, 1),
            "confidence": round(float(event.confidence), 4),
            "raw_score": round(score, 2),
            "bus_bonus": bus_bonus,
            "count_bonus": count_bonus,
            "persistence_bonus": persistence_bonus,
        }

        return SeverityEvaluationResult(
            severity=calculated_severity,
            score=round(score, 2),
            reasons=reasons,
            factors=factors,
            bus_bonus=bus_bonus,
            count_bonus=count_bonus,
            persistence_bonus=persistence_bonus,
        )

    evaluate_event = calculate_severity

    def evaluate_and_update_event_severity(
        self, event: Event
    ) -> SeverityEvaluationResult:
        """
        Evaluate and escalate the event's severity monotonically.
        Updates event.severity and stores explainability in event.extra_metadata.
        """
        eval_result = self.calculate_severity(event)

        # Monotonic escalation: active events do not automatically downgrade
        current_rank = self.severity_rank(event.severity)
        calculated_rank = self.severity_rank(eval_result.severity)

        if calculated_rank > current_rank:
            logger.info(
                "Event %s severity escalated from %s -> %s (reasons: %s)",
                event.id,
                event.severity.value,
                eval_result.severity.value,
                "; ".join(eval_result.reasons),
            )
            event.severity = eval_result.severity
        else:
            logger.debug(
                "Event %s severity maintained at %s (calculated=%s)",
                event.id,
                event.severity.value,
                eval_result.severity.value,
            )
            eval_result.severity = event.severity

        # Record explainability audit trail in event extra_metadata
        metadata = dict(event.extra_metadata or {})
        metadata["severity_evaluation"] = {
            "current_severity": event.severity.value,
            "calculated_severity": eval_result.severity.value,
            "final_severity": event.severity.value,
            "score": eval_result.score,
            "bus_bonus": eval_result.bus_bonus,
            "count_bonus": eval_result.count_bonus,
            "persistence_bonus": eval_result.persistence_bonus,
            "reasons": eval_result.reasons,
            "factors": eval_result.factors,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }
        event.extra_metadata = metadata

        return eval_result
