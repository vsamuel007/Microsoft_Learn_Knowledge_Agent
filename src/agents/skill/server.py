from mcp.server.fastmcp import FastMCP


mcp = FastMCP(name="SkillGapMock")


MOCK_USER_PROFILES = {
    "user-123": {
        "user_id": "user-123",
        "name": "Avery Kim",
        "current_skill_details": [
            {"skill": "Azure Fundamentals", "proficiency": 68},
            {"skill": "Identity and Access Management", "proficiency": 46},
            {"skill": "Azure Networking", "proficiency": 34},
            {"skill": "Monitoring", "proficiency": 40},
            {"skill": "PowerShell", "proficiency": 52},
        ],
        "learning_history": [
            {"course": "AZ-900 Introduction", "completed_date": "2025-11-04", "score": 84},
            {"course": "Azure Governance Basics", "completed_date": "2026-01-12", "score": 73},
        ],
        "target_role": "Azure Administrator",
        "target_certification": "AZ-104",
    },
    "user-456": {
        "user_id": "user-456",
        "name": "Jordan Lee",
        "current_skill_details": [
            {"skill": "Python", "proficiency": 80},
            {"skill": "Data Analysis", "proficiency": 72},
            {"skill": "Prompt Engineering", "proficiency": 61},
        ],
        "learning_history": [
            {"course": "AI-900", "completed_date": "2026-02-09", "score": 78},
        ],
        "target_role": "AI Engineer",
        "target_certification": "AI-102",
    },
}


ROLE_REQUIREMENTS = {
    "azure administrator": {
        "target_type": "role",
        "target_name": "Azure Administrator",
        "required_skill_details": [
            {"skill": "Azure Networking", "target_proficiency": 75},
            {"skill": "Identity and Access Management", "target_proficiency": 78},
            {"skill": "Monitoring", "target_proficiency": 70},
            {"skill": "Backup and Recovery", "target_proficiency": 68},
            {"skill": "Azure Compute", "target_proficiency": 72},
        ],
    },
    "ai engineer": {
        "target_type": "role",
        "target_name": "AI Engineer",
        "required_skill_details": [
            {"skill": "Prompt Engineering", "target_proficiency": 80},
            {"skill": "Model Evaluation", "target_proficiency": 74},
            {"skill": "Python", "target_proficiency": 82},
            {"skill": "Responsible AI", "target_proficiency": 75},
            {"skill": "Azure AI Services", "target_proficiency": 78},
        ],
    },
}


CERT_REQUIREMENTS = {
    "az-104": {
        "target_type": "certification",
        "target_name": "AZ-104",
        "required_skill_details": [
            {"skill": "Azure Networking", "target_proficiency": 78},
            {"skill": "Identity and Access Management", "target_proficiency": 80},
            {"skill": "Monitoring", "target_proficiency": 74},
            {"skill": "Storage Management", "target_proficiency": 72},
            {"skill": "Azure Governance", "target_proficiency": 70},
        ],
    },
    "ai-102": {
        "target_type": "certification",
        "target_name": "AI-102",
        "required_skill_details": [
            {"skill": "Prompt Engineering", "target_proficiency": 82},
            {"skill": "Azure AI Services", "target_proficiency": 80},
            {"skill": "Model Evaluation", "target_proficiency": 76},
            {"skill": "Responsible AI", "target_proficiency": 78},
            {"skill": "Vector Search", "target_proficiency": 68},
        ],
    },
}


def _priority_from_gap(gap: int) -> str:
    if gap >= 35:
        return "high"
    if gap >= 15:
        return "medium"
    return "low"


@mcp.tool()
def get_user_profile(user_id: str, include_history: bool = True) -> dict:
    """Return a mock user profile, current skills, and optional learning history."""
    profile = MOCK_USER_PROFILES.get(user_id)
    if not profile:
        return {"status": "not_found", "error": f"User '{user_id}' not found", "profile": None}

    result_profile = dict(profile)
    result_profile["current_skills"] = [s["skill"] for s in profile["current_skill_details"]]
    if not include_history:
        result_profile["learning_history"] = []

    return {"status": "ok", "error": None, "profile": result_profile}


@mcp.tool()
def get_role_requirements(target_role: str = "", target_certification: str = "") -> dict:
    """Return required skills for a mock target role or certification."""
    if not target_role and not target_certification:
        return {
            "status": "error",
            "error": "Provide either target_role or target_certification",
            "required_skill_details": [],
        }

    if target_role:
        req = ROLE_REQUIREMENTS.get(target_role.lower())
        if not req:
            return {
                "status": "error",
                "error": f"Unsupported target_role '{target_role}'",
                "required_skill_details": [],
            }
        return {"status": "ok", "error": None, **req}

    req = CERT_REQUIREMENTS.get(target_certification.lower())
    if not req:
        return {
            "status": "error",
            "error": f"Unsupported target_certification '{target_certification}'",
            "required_skill_details": [],
        }
    return {"status": "ok", "error": None, **req}


@mcp.tool()
def assess_skill_gap(
    current_skill_details: list[dict] | None = None,
    current_skills: list[str] | None = None,
    target_role: str = "",
    target_certification: str = "",
) -> dict:
    """Compute prioritized skill gaps from user skills and target requirements."""
    try:
        if current_skill_details is not None and not isinstance(current_skill_details, list):
            return {
                "status": "error",
                "error": "current_skill_details must be a list of objects",
                "current_skills": current_skills or [],
                "required_skills": [],
                "skill_gaps": [],
                "recommended_focus_areas": [],
            }

        if current_skills is not None and not isinstance(current_skills, list):
            return {
                "status": "error",
                "error": "current_skills must be a list of strings",
                "current_skills": [],
                "required_skills": [],
                "skill_gaps": [],
                "recommended_focus_areas": [],
            }

        normalized_current_skills = [str(skill) for skill in (current_skills or [])]

        if not target_role and not target_certification:
            return {
                "status": "error",
                "error": "Provide either target_role or target_certification",
                "current_skills": normalized_current_skills,
                "required_skills": [],
                "skill_gaps": [],
                "recommended_focus_areas": [],
            }

        req_result = get_role_requirements(target_role=target_role, target_certification=target_certification)
        if req_result.get("status") != "ok":
            return {
                "status": "error",
                "error": req_result.get("error"),
                "current_skills": normalized_current_skills,
                "required_skills": [],
                "skill_gaps": [],
                "recommended_focus_areas": [],
            }

        detail_map = {}
        if current_skill_details:
            for item in current_skill_details:
                if not isinstance(item, dict):
                    continue
                skill = item.get("skill")
                prof_raw = item.get("proficiency", 0)
                try:
                    prof = int(prof_raw)
                except (TypeError, ValueError):
                    prof = 0
                if skill:
                    detail_map[str(skill).lower()] = max(0, min(100, prof))
        elif normalized_current_skills:
            detail_map = {skill.lower(): 40 for skill in normalized_current_skills}

        required_skill_details = req_result.get("required_skill_details", [])
        required_skills = [item["skill"] for item in required_skill_details if isinstance(item, dict) and "skill" in item]
        gaps = []
        total_gap = 0

        for item in required_skill_details:
            if not isinstance(item, dict) or "skill" not in item:
                continue
            skill = str(item["skill"])
            target_raw = item.get("target_proficiency", 70)
            try:
                target = int(target_raw)
            except (TypeError, ValueError):
                target = 70

            current = detail_map.get(skill.lower(), 0)
            gap = max(0, target - current)
            total_gap += gap
            gaps.append(
                {
                    "skill": skill,
                    "priority": _priority_from_gap(gap),
                    "proficiency_gap": gap,
                }
            )

        gaps = sorted(gaps, key=lambda g: g["proficiency_gap"], reverse=True)[:10]
        focus_areas = [g["skill"] for g in gaps if g["proficiency_gap"] > 0][:3]
        avg_gap = int(total_gap / len(required_skill_details)) if required_skill_details else 0
        match_score = max(0, 100 - avg_gap)

        derived_skills = []
        if current_skill_details:
            for item in current_skill_details:
                if isinstance(item, dict) and item.get("skill"):
                    derived_skills.append(str(item["skill"]))

        return {
            "status": "ok",
            "error": None,
            "current_skills": list(dict.fromkeys(derived_skills or normalized_current_skills)),
            "required_skills": required_skills,
            "skill_gaps": gaps,
            "recommended_focus_areas": focus_areas,
            "match_score": match_score,
        }

    except Exception as ex:  # pylint: disable=broad-except
        return {
            "status": "error",
            "error": f"assess_skill_gap failed: {str(ex)}",
            "current_skills": current_skills or [],
            "required_skills": [],
            "skill_gaps": [],
            "recommended_focus_areas": [],
        }


@mcp.tool()
def generate_assessment_items(
    skill_gaps: list[dict],
    num_items_per_skill: int = 2,
    include_scenario_questions: bool = True,
) -> dict:
    """Generate mock adaptive assessment questions for prioritized skill gaps."""
    if not skill_gaps:
        return {"status": "error", "error": "skill_gaps is required", "items": []}

    item_count = max(1, min(5, num_items_per_skill))
    items = []

    for gap in skill_gaps[:5]:
        skill = gap.get("skill", "Unknown Skill")
        priority = gap.get("priority", "medium")
        for idx in range(1, item_count + 1):
            question_type = "scenario" if include_scenario_questions and idx % 2 == 0 else "concept"
            items.append(
                {
                    "id": f"{skill.lower().replace(' ', '-')}-{idx}",
                    "skill": skill,
                    "priority": priority,
                    "type": question_type,
                    "question": f"[{question_type}] What is the best practice for {skill} in this context?",
                    "choices": ["A", "B", "C", "D"],
                    "correct_answer": "B",
                    "difficulty": "hard" if priority == "high" else "medium",
                }
            )

    return {"status": "ok", "error": None, "count": len(items), "items": items}


@mcp.tool()
def evaluate_assessment_response(responses: list[dict], pass_score: int = 70) -> dict:
    """Evaluate mock learner responses and suggest follow-up focus areas."""
    if not responses:
        return {
            "status": "error",
            "error": "responses is required",
            "overall_score": 0,
            "skill_results": [],
            "recommended_next_steps": [],
        }

    skill_results = []
    scored = 0

    for item in responses:
        skill = item.get("skill", "Unknown Skill")
        correct = int(item.get("correct", 0))
        total = max(1, int(item.get("total", 1)))
        score = int((correct / total) * 100)
        scored += score
        skill_results.append(
            {
                "skill": skill,
                "score": score,
                "status": "pass" if score >= pass_score else "needs_improvement",
            }
        )

    overall_score = int(scored / len(skill_results))
    next_steps = [
        f"Review fundamentals for {r['skill']}" for r in skill_results if r["status"] == "needs_improvement"
    ]

    return {
        "status": "ok",
        "error": None,
        "overall_score": overall_score,
        "skill_results": skill_results,
        "recommended_next_steps": next_steps,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SkillGap MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="Transport mode: 'stdio' for local client.py, 'sse' or 'streamable-http' for Foundry portal",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (HTTP modes only)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind (HTTP modes only)")
    parser.add_argument(
        "--public",
        action="store_true",
        help="Allow public tunnel host headers (use for ngrok/Azure demo endpoints)",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        if args.public:
            mcp.settings.transport_security.enable_dns_rebinding_protection = False

        print(f"Starting SkillGap MCP server ({args.transport}) on {args.host}:{args.port}")
        if args.transport == "sse":
            print(f"  Foundry MCPTool URL: http://{args.host}:{args.port}/sse")
            print(f"  (Use ngrok or Azure to get a public URL, then set SKILL_GAP_MCP_SERVER_URL)")
        else:
            print(f"  Foundry MCPTool URL: http://{args.host}:{args.port}/mcp")
        if args.public:
            print("  Public mode enabled: DNS rebinding protection disabled for tunnel compatibility")
        mcp.run(transport=args.transport)
