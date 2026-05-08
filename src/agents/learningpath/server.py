"""
LearningPath MCP Server — pure synthesis engine.

This server is called by the LearningPathAgent Foundry agent after the agent has
already collected data from the other two MCP endpoints:
    • Search tools (MS Learn MCP)                            → learning resources
    • Skill Gap tools (SkillGap MCP)                         → user skill gaps

This server does NOT make any HTTP calls.  It receives pre-fetched data as tool
arguments, synthesizes the learning path, and returns structured JSON.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP


mcp = FastMCP(name="LearningPathMCP")

# Average hours to complete one MS Learn module (used as fallback when not supplied).
_HOURS_PER_MODULE = 1.5

# Pacing configuration: how many phases and resources-per-phase per pace setting.
_PACE_CONFIG: dict[str, dict[str, int]] = {
    "fast":     {"max_phases": 3, "modules_per_phase": 6},
    "moderate": {"max_phases": 4, "modules_per_phase": 4},
    "slow":     {"max_phases": 6, "modules_per_phase": 3},
}

_DEFAULT_PACE = "moderate"



@mcp.tool()
def generate_learning_path(
    skill_gaps: list[dict],
    resources: list[dict],
    learning_pace: str = "moderate",
    time_commitment: int = 5,
) -> dict[str, Any]:
    """
    Synthesize a personalized learning path from assessed skill gaps and MS Learn resources.

        This tool is called by the LearningPathAgent after it has already retrieved:
            - skill_gaps  from SkillGap MCP tools (assess_skill_gap output)
            - resources   from Search tools (MS Learn MCP)

    Args:
        skill_gaps:        List of gap objects from assess_skill_gap.
                           Each item: {"skill": str, "priority": "high|medium|low",
                                       "proficiency_gap": int}
        resources:         List of MS Learn items returned by Search tools.
                           Each item may include: title, url, summary, description,
                           duration_in_minutes, estimated_hours.
        learning_pace:     "fast" | "moderate" | "slow"  (default "moderate")
        time_commitment:   Hours per week the learner can dedicate (default 5).

    Returns:
        {"status": "ok|error", "error": str|null, "learning_path": {...}}
    """
    if not skill_gaps:
        return {
            "status": "error",
            "error": "skill_gaps is required and cannot be empty",
            "learning_path": None,
        }
    if not resources:
        return {
            "status": "error",
            "error": "resources is required and cannot be empty",
            "learning_path": None,
        }

    pace = (learning_pace or _DEFAULT_PACE).lower().strip()
    if pace not in _PACE_CONFIG:
        pace = _DEFAULT_PACE

    weekly_hours = max(1, int(time_commitment)) if time_commitment else 5

    normalized_gaps = _normalize_gaps(skill_gaps)
    normalized_resources = _normalize_resources(resources)

    gap_buckets = _bucket_resources_by_gap(normalized_gaps, normalized_resources)
    phases = _build_phases(gap_buckets, normalized_gaps, pace, weekly_hours)

    total_hours = round(sum(p["total_hours"] for p in phases), 1)
    weeks_needed = math.ceil(total_hours / weekly_hours) if weekly_hours > 0 else 0

    return {
        "status": "ok",
        "error": None,
        "learning_path": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "learning_pace": pace,
            "time_commitment_hours_per_week": weekly_hours,
            "total_hours": total_hours,
            "estimated_duration": f"{weeks_needed} weeks at {weekly_hours}h/week",
            "phases": phases,
            "milestones": [p["milestone"] for p in phases if p.get("milestone")],
        },
    }


@mcp.tool()
def refine_learning_path(
    current_path: dict[str, Any],
    feedback: str,
    learning_pace: str = "moderate",
) -> dict[str, Any]:
    """
    Adjust an existing learning path based on learner feedback.

    Args:
        current_path:   The full dict returned by generate_learning_path
                        (the entire response, or just the learning_path object).
        feedback:       Plain-language feedback, e.g. "I want to go faster"
                        or "give me more practice on networking".
        learning_pace:  Override the pace; inferred from feedback if omitted.

    Returns:
        {"status": "ok|error", "error": str|null, "learning_path": {...}}
    """
    if not isinstance(current_path, dict):
        return {"status": "error", "error": "current_path must be a dict", "learning_path": None}

    # Accept either the wrapper {"learning_path": {...}} or the inner object directly.
    lp = current_path.get("learning_path", current_path)
    if not isinstance(lp, dict) or "phases" not in lp:
        return {"status": "error", "error": "No valid phases found in current_path", "learning_path": None}

    # Infer pace from feedback keywords.
    normalized_feedback = (feedback or "").lower()
    pace = (learning_pace or _DEFAULT_PACE).lower().strip()
    if pace not in _PACE_CONFIG:
        pace = _DEFAULT_PACE

    if "faster" in normalized_feedback or "speed up" in normalized_feedback:
        pace = "fast"
    elif "slower" in normalized_feedback or "slow down" in normalized_feedback or "more time" in normalized_feedback:
        pace = "slow"

    cfg = _PACE_CONFIG[pace]
    weekly_hours = int(lp.get("time_commitment_hours_per_week", 5))

    # Flatten all resources from existing phases, preserve order, de-duplicate.
    all_resources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for phase in lp.get("phases", []):
        for r in phase.get("resources", []):
            key = str(r.get("url") or r.get("title") or "").lower()
            if key and key not in seen:
                seen.add(key)
                all_resources.append(r)

    # Re-chunk into the new pace's phase structure.
    chunk_size = cfg["modules_per_phase"]
    max_phases = cfg["max_phases"]
    chunks = [all_resources[i : i + chunk_size] for i in range(0, len(all_resources), chunk_size)]
    chunks = chunks[:max_phases]

    phases = []
    for idx, chunk in enumerate(chunks, start=1):
        phase_hours = round(sum(_resource_hours(r) for r in chunk), 1)
        weeks = math.ceil(phase_hours / weekly_hours) if weekly_hours else 1
        phases.append(
            {
                "phase_number": idx,
                "title": _phase_title(idx, pace),
                "duration": f"{weeks} week{'s' if weeks != 1 else ''}",
                "total_hours": phase_hours,
                "resources": chunk,
                "objectives": [f"Complete all modules in the {_phase_title(idx, pace)} phase"],
                "milestone": f"Phase {idx} complete — {_phase_title(idx, pace)}",
            }
        )

    total_hours = round(sum(p["total_hours"] for p in phases), 1)
    weeks_needed = math.ceil(total_hours / weekly_hours) if weekly_hours else 0

    return {
        "status": "ok",
        "error": None,
        "learning_path": {
            **lp,
            "learning_pace": pace,
            "total_hours": total_hours,
            "estimated_duration": f"{weeks_needed} weeks at {weekly_hours}h/week",
            "phases": phases,
            "milestones": [p["milestone"] for p in phases if p.get("milestone")],
            "refined_at": datetime.now(timezone.utc).isoformat(),
            "feedback_applied": feedback,
        },
    }


@mcp.tool()
def estimate_learning_duration(
    modules: list[dict],
    user_pace: str = "moderate",
    weekly_hours: int = 5,
) -> dict[str, Any]:
    """
    Estimate how long a set of learning modules will take.

    Args:
        modules:      List of resource/module objects (title, url, duration_in_minutes optional).
                  Accepts the same format returned by Search tools.
        user_pace:    "fast" | "moderate" | "slow"
        weekly_hours: Hours per week the learner can commit.

    Returns:
        Duration estimates with total hours and week projections.
    """
    if not modules:
        return {"status": "error", "error": "modules list cannot be empty", "estimated_duration": None}

    weekly = max(1, int(weekly_hours)) if weekly_hours else 5
    total_hours = round(sum(_resource_hours(m) for m in modules), 1)
    weeks = math.ceil(total_hours / weekly)

    return {
        "status": "ok",
        "error": None,
        "estimated_duration": {
            "modules_count": len(modules),
            "user_pace": user_pace or "moderate",
            "total_hours": total_hours,
            "weeks_needed": weeks,
            "at_5h_per_week": math.ceil(total_hours / 5),
            "at_8h_per_week": math.ceil(total_hours / 8),
            "at_10h_per_week": math.ceil(total_hours / 10),
        },
    }


@mcp.tool()
def prioritize_resources(
    resources: list[dict],
    skill_gaps: list[dict],
) -> dict[str, Any]:
    """
    Rank and filter learning resources by gap priority.

    Useful when the agent wants to present the most relevant content first before
    calling generate_learning_path.

    Args:
        resources:   Raw list of MS Learn resources from Search tools.
        skill_gaps:  Skill gaps from SkillGap MCP assess_skill_gap (with priority field).

    Returns:
        {"status": "ok", "prioritized_resources": [...], "count": int}
    """
    if not resources:
        return {"status": "error", "error": "resources cannot be empty", "prioritized_resources": []}

    if not skill_gaps:
        normalized = _normalize_resources(resources)
        return {"status": "ok", "error": None, "prioritized_resources": normalized, "count": len(normalized)}

    normalized_gaps = _normalize_gaps(skill_gaps)
    normalized_resources = _normalize_resources(resources)
    buckets = _bucket_resources_by_gap(normalized_gaps, normalized_resources)

    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()

    for priority in ("high", "medium", "low"):
        for gap in [g for g in normalized_gaps if g["priority"] == priority]:
            for resource in buckets.get(gap["skill"], []):
                key = str(resource.get("url") or resource.get("title") or "").lower()
                if key and key not in seen:
                    seen.add(key)
                    ordered.append({**resource, "_matched_skill": gap["skill"], "_gap_priority": priority})

    # Append unmatched resources at the end.
    for resource in buckets.get("__unmatched__", []):
        key = str(resource.get("url") or resource.get("title") or "").lower()
        if key and key not in seen:
            seen.add(key)
            ordered.append(resource)

    return {"status": "ok", "error": None, "prioritized_resources": ordered, "count": len(ordered)}


# ── Private helpers ───────────────────────────────────────────────────────────


def _normalize_gaps(raw: list[Any]) -> list[dict[str, Any]]:
    normalized = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        skill = str(item.get("skill") or "").strip()
        if not skill:
            continue
        raw_gap = item.get("proficiency_gap", item.get("gap", 0))
        try:
            gap_score = int(raw_gap)
        except (TypeError, ValueError):
            gap_score = 0
        priority = str(item.get("priority") or "").lower().strip()
        if priority not in {"high", "medium", "low"}:
            if gap_score >= 35:
                priority = "high"
            elif gap_score >= 15:
                priority = "medium"
            else:
                priority = "low"
        normalized.append({"skill": skill, "priority": priority, "proficiency_gap": max(0, gap_score)})
    normalized.sort(key=lambda x: x["proficiency_gap"], reverse=True)
    return normalized


def _normalize_resources(raw: list[Any]) -> list[dict[str, Any]]:
    normalized = []
    for item in raw:
        if isinstance(item, str):
            normalized.append({"title": item, "url": "", "summary": "", "estimated_hours": _HOURS_PER_MODULE})
            continue
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("name") or item.get("module") or "").strip()
        url = str(item.get("url") or item.get("link") or item.get("module_url") or "").strip()
        summary = str(item.get("summary") or item.get("description") or "").strip()
        if not title and not url:
            continue
        normalized.append(
            {
                "title": title or url,
                "url": url,
                "summary": summary,
                "estimated_hours": _resource_hours(item),
            }
        )
    return normalized


def _resource_hours(item: dict[str, Any]) -> float:
    """Convert item duration fields to hours; defaults to _HOURS_PER_MODULE."""
    mins_raw = item.get("duration_in_minutes") or item.get("durationInMinutes") or item.get("duration_minutes")
    if mins_raw:
        try:
            return max(0.25, round(int(mins_raw) / 60, 2))
        except (TypeError, ValueError):
            pass
    hours_raw = item.get("estimated_hours") or item.get("duration_hours")
    if hours_raw:
        try:
            return max(0.25, float(hours_raw))
        except (TypeError, ValueError):
            pass
    return _HOURS_PER_MODULE


def _bucket_resources_by_gap(
    gaps: list[dict[str, Any]],
    resources: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Map each resource to its best-matching skill gap using keyword overlap."""
    buckets: dict[str, list[dict[str, Any]]] = {g["skill"]: [] for g in gaps}
    buckets["__unmatched__"] = []

    for resource in resources:
        blob = f"{resource.get('title', '')} {resource.get('summary', '')}".lower()
        matched = False
        for gap in gaps:
            keywords = [w for w in gap["skill"].lower().replace("/", " ").split() if len(w) >= 3]
            if any(kw in blob for kw in keywords):
                buckets[gap["skill"]].append(resource)
                matched = True
                break
        if not matched:
            buckets["__unmatched__"].append(resource)

    return buckets


def _build_phases(
    gap_buckets: dict[str, list[dict[str, Any]]],
    gaps: list[dict[str, Any]],
    pace: str,
    weekly_hours: int,
) -> list[dict[str, Any]]:
    """Build ordered phases from gap buckets, respecting pace config."""
    cfg = _PACE_CONFIG[pace]
    max_phases = cfg["max_phases"]
    modules_per_phase = cfg["modules_per_phase"]

    # Flatten resources in priority order: high → medium → low → unmatched.
    ordered_resources: list[dict[str, Any]] = []
    seen: set[str] = set()

    for priority in ("high", "medium", "low"):
        for gap in [g for g in gaps if g["priority"] == priority]:
            for res in gap_buckets.get(gap["skill"], [])[:modules_per_phase]:
                key = str(res.get("url") or res.get("title") or "").lower()
                if key and key not in seen:
                    seen.add(key)
                    ordered_resources.append({**res, "_skill": gap["skill"], "_priority": priority})

    for res in gap_buckets.get("__unmatched__", []):
        key = str(res.get("url") or res.get("title") or "").lower()
        if key and key not in seen:
            seen.add(key)
            ordered_resources.append(res)

    # Chunk into phases.
    chunks = [
        ordered_resources[i : i + modules_per_phase]
        for i in range(0, len(ordered_resources), modules_per_phase)
    ]
    chunks = chunks[:max_phases]

    phases = []
    for idx, chunk in enumerate(chunks, start=1):
        phase_hours = round(sum(_resource_hours(r) for r in chunk), 1)
        weeks = math.ceil(phase_hours / weekly_hours) if weekly_hours else 1
        skills_covered = list(dict.fromkeys(r.get("_skill", "") for r in chunk if r.get("_skill")))
        objectives = (
            [f"Build proficiency in {s}" for s in skills_covered]
            or [f"Complete all modules in phase {idx}"]
        )
        # Strip internal metadata keys before returning.
        clean_chunk = [{k: v for k, v in r.items() if not k.startswith("_")} for r in chunk]
        phases.append(
            {
                "phase_number": idx,
                "title": _phase_title(idx, pace),
                "duration": f"{weeks} week{'s' if weeks != 1 else ''}",
                "total_hours": phase_hours,
                "resources": clean_chunk,
                "objectives": objectives,
                "milestone": f"Phase {idx} complete — {_phase_title(idx, pace)}",
            }
        )

    return phases


def _phase_title(phase_number: int, pace: str) -> str:
    titles: dict[str, list[str]] = {
        "fast":     ["Essentials", "Core Skills", "Certification Prep"],
        "moderate": ["Foundations", "Core Skills", "Applied Practice", "Certification Prep"],
        "slow":     [
            "Foundations",
            "Core Concepts",
            "Hands-On Practice",
            "Applied Skills",
            "Review & Consolidation",
            "Certification Prep",
        ],
    }
    options = titles.get(pace, titles["moderate"])
    idx = phase_number - 1
    return options[idx] if idx < len(options) else f"Phase {phase_number}"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LearningPath MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="Transport mode: stdio for local, sse/streamable-http for Foundry portal",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind in HTTP modes")
    parser.add_argument("--port", type=int, default=8002, help="Port to bind in HTTP modes")
    parser.add_argument(
        "--public",
        action="store_true",
        help="Disable DNS rebinding protection for ngrok/tunnel compatibility",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        if args.public:
            mcp.settings.transport_security.enable_dns_rebinding_protection = False

        print(f"Starting LearningPath MCP server ({args.transport}) on {args.host}:{args.port}")
        if args.transport == "sse":
            print(f"  Foundry MCPTool URL: http://{args.host}:{args.port}/sse")
            print(f"  (Use ngrok or Azure to get a public URL, then set LEARNING_PATH_MCP_SERVER_URL)")
        else:
            print(f"  Foundry MCPTool URL: http://{args.host}:{args.port}/mcp")
        if args.public:
            print("  Public mode enabled: DNS rebinding protection disabled for tunnel compatibility")
        mcp.run(transport=args.transport)