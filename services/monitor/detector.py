"""Contradiction detection logic."""
import uuid
from collections import defaultdict
import structlog

from .models import Claim, Conflict

logger = structlog.get_logger()

# Scope hierarchy (lower number = broader scope)
SCOPE_LEVELS = {
    "global": 0,
    "conversation": 1,
    "task": 2,
    "step": 3,
    "file": 4,
}


def detect_conflicts(claims: list[Claim]) -> list[Conflict]:
    """Detect contradictions between claims."""
    conflicts = []

    # Group by (action, target)
    groups = defaultdict(list)
    for claim in claims:
        key = (claim.action, claim.target)
        groups[key].append(claim)

    logger.debug("claims_grouped", group_count=len(groups))

    # Check for contradictions within each group
    for (action, target), group_claims in groups.items():
        if len(group_claims) < 2:
            continue

        for i, claim1 in enumerate(group_claims):
            for claim2 in group_claims[i+1:]:
                # Check if modalities contradict
                if not is_contradictory(claim1.modality, claim2.modality):
                    continue

                # For now, skip scope overlap check (assume same session = overlap)
                # In future: check claim scope fields

                # Determine severity based on conditions
                severity = assess_conflict_severity(claim1, claim2)

                if severity != "none":
                    conflict = create_conflict(claim1, claim2, severity)
                    conflicts.append(conflict)

                    logger.info(
                        "conflict_detected",
                        conflict_id=conflict.conflict_id,
                        severity=severity,
                        action=action,
                        target=target
                    )

    logger.info("conflict_detection_complete", conflict_count=len(conflicts))
    return conflicts


def is_contradictory(mod1: str, mod2: str) -> bool:
    """Check if two modalities contradict each other."""
    opposites = {
        ('must', 'must_not'),
        ('must', 'avoid'),
        ('should', 'must_not'),
        ('prefer', 'avoid'),
    }
    return (mod1, mod2) in opposites or (mod2, mod1) in opposites


def assess_conflict_severity(claim1: Claim, claim2: Claim) -> str:
    """
    Assess conflict severity: "hard" | "soft" | "none"

    - hard: No conditions, always applies
    - soft: Conditional or exceptional cases
    - none: Conditions don't overlap
    """
    # No conditions = always applies = hard conflict
    if not claim1.conditions and not claim2.conditions:
        return "hard"

    # One has conditions, one doesn't = soft conflict
    if bool(claim1.conditions) != bool(claim2.conditions):
        return "soft"

    # Both have conditions - check for overlap
    words1 = set(" ".join(claim1.conditions).lower().split())
    words2 = set(" ".join(claim2.conditions).lower().split())

    if words1 & words2:  # Intersection
        return "soft"  # Conditionally conflicting
    else:
        return "none"  # Different conditions, no conflict


def create_conflict(claim1: Claim, claim2: Claim, severity: str) -> Conflict:
    """Create a conflict object from two contradictory claims."""
    explanation = (
        f"Contradictory instructions: {claim1.modality} {claim1.action} "
        f"vs {claim2.modality} {claim2.action} on '{claim1.target}'"
    )

    # Average confidence
    confidence = (claim1.confidence + claim2.confidence) / 2

    return Conflict(
        conflict_id=f"cfl_{uuid.uuid4().hex[:12]}",
        session_id=claim1.session_id,
        claims=[claim1.claim_id, claim2.claim_id],
        severity=severity,
        explanation=explanation,
        confidence=confidence
    )
