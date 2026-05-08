"""Adaptive card builders for Microsoft Teams bot responses."""
from typing import Any, Dict, List

from botbuilder.schema import Attachment


class AdaptiveCardBuilder:
    """Builder for creating rich Adaptive Cards for Microsoft Teams."""

    @staticmethod
    def create_welcome_card(user_name: str) -> Attachment:
        """Create welcome card with bot introduction and quick actions."""
        card = {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": f"👋 Welcome, {user_name}!",
                    "size": "Large",
                    "weight": "Bolder",
                    "color": "Accent",
                },
                {
                    "type": "TextBlock",
                    "text": "I'm your AI Learning Path Assistant. I can help you:",
                    "wrap": True,
                    "spacing": "Medium",
                },
                {
                    "type": "FactSet",
                    "facts": [
                        {"title": "🎯", "value": "Create personalized learning paths"},
                        {"title": "📊", "value": "Analyze your skill gaps"},
                        {"title": "🔍", "value": "Find relevant Microsoft Learn resources"},
                        {"title": "📈", "value": "Track your learning progress"},
                    ],
                },
                {"type": "TextBlock", "text": "**Get Started:**", "weight": "Bolder", "spacing": "Medium"},
            ],
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": "🎓 Create Learning Path",
                    "data": {"action": "create_learning_path"},
                },
                {
                    "type": "Action.Submit",
                    "title": "📋 View My Skills",
                    "data": {"action": "view_skills"},
                },
                {
                    "type": "Action.Submit",
                    "title": "🔍 Search Resources",
                    "data": {"action": "search_resources"},
                },
            ],
        }
        return Attachment(content_type="application/vnd.microsoft.card.adaptive", content=card)

    @staticmethod
    def create_learning_path_card(learning_path: Dict[str, Any], skill_analysis: Dict[str, Any]) -> Attachment:
        """Create card showing a personalized learning path plus learner context."""
        learning_path_data = learning_path.get("learning_path", learning_path)
        phases = learning_path_data.get("phases", []) if isinstance(learning_path_data, dict) else []

        phase_items = []
        for i, phase in enumerate(phases[:3], 1):
            phase_items.extend(
                [
                    {
                        "type": "TextBlock",
                        "text": f"**Phase {i}: {phase.get('title')}**",
                        "weight": "Bolder",
                        "spacing": "Medium",
                    },
                    {"type": "TextBlock", "text": f"⏱️ Duration: {phase.get('duration', 'N/A')}", "spacing": "Small"},
                    {"type": "TextBlock", "text": f"🎯 Milestone: {phase.get('milestone', 'N/A')}", "spacing": "Small", "wrap": True},
                ]
            )

        learner_profile = skill_analysis.get("profile", skill_analysis)
        skill_gaps = skill_analysis.get("skill_gaps", [])[:5]
        current_skill_details = learner_profile.get("current_skill_details", [])[:5] if isinstance(learner_profile, dict) else []

        learner_facts = []
        if skill_gaps:
            learner_facts = [
                {
                    "title": f"{'🔴' if gap.get('priority') == 'high' else '🟡'} {gap.get('skill', 'Unknown Skill')}",
                    "value": f"{gap.get('proficiency_gap', 0)}% gap",
                }
                for gap in skill_gaps
            ]
        elif current_skill_details:
            learner_facts = [
                {
                    "title": item.get("skill", "Unknown Skill"),
                    "value": f"{item.get('proficiency', 0)}% current proficiency",
                }
                for item in current_skill_details
            ]

        card = {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "🎓 Your Personalized Learning Path",
                    "size": "Large",
                    "weight": "Bolder",
                    "color": "Accent",
                },
                {
                    "type": "ColumnSet",
                    "columns": [
                        {
                            "type": "Column",
                            "width": "stretch",
                            "items": [{"type": "TextBlock", "text": f"📚 {len(phases)} Phases", "weight": "Bolder"}],
                        },
                        {
                            "type": "Column",
                            "width": "stretch",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": f"⏱️ {learning_path_data.get('estimated_duration', 'N/A') if isinstance(learning_path_data, dict) else 'N/A'}",
                                    "weight": "Bolder",
                                }
                            ],
                        },
                    ],
                },
                {"type": "TextBlock", "text": "**📊 Learner Snapshot**", "weight": "Bolder", "spacing": "Large"},
                {"type": "FactSet", "facts": learner_facts or [{"title": "Info", "value": "No learner context returned"}]},
                {"type": "TextBlock", "text": "**📖 Learning Phases**", "weight": "Bolder", "spacing": "Large"},
            ]
            + phase_items
            + [
                {
                    "type": "TextBlock",
                    "text": f"_Showing {min(3, len(phases))} of {len(phases)} phases_",
                    "isSubtle": True,
                    "spacing": "Medium",
                }
            ],
            "actions": [
                {"type": "Action.Submit", "title": "🚀 Start Learning", "data": {"action": "start_learning"}},
            ],
        }
        return Attachment(content_type="application/vnd.microsoft.card.adaptive", content=card)

    @staticmethod
    def create_resources_card(query: str, resources: List[Dict[str, Any]]) -> Attachment:
        """Create card showing search results for learning resources."""
        resource_items = []
        for i, resource in enumerate(resources[:5], 1):
            description = resource.get("description") or resource.get("summary") or "No description available"
            duration = resource.get("duration") or resource.get("estimated_hours") or "N/A"
            level = resource.get("level") or resource.get("audience") or "N/A"
            resource_items.extend(
                [
                    {
                        "type": "Container",
                        "spacing": "Medium",
                        "separator": i > 1,
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": f"**{i}. {resource.get('title', 'Untitled')}**",
                                "weight": "Bolder",
                                "wrap": True,
                            },
                            {
                                "type": "TextBlock",
                                "text": description,
                                "wrap": True,
                                "spacing": "Small",
                                "isSubtle": True,
                            },
                            {
                                "type": "ColumnSet",
                                "columns": [
                                    {
                                        "type": "Column",
                                        "width": "auto",
                                        "items": [
                                            {
                                                "type": "TextBlock",
                                                "text": f"📊 {str(level).title()}",
                                                "spacing": "Small",
                                            }
                                        ],
                                    },
                                    {
                                        "type": "Column",
                                        "width": "auto",
                                        "items": [
                                            {
                                                "type": "TextBlock",
                                                "text": f"⏱️ {duration}",
                                                "spacing": "Small",
                                            }
                                        ],
                                    },
                                ],
                            },
                        ],
                    },
                    {
                        "type": "ActionSet",
                        "actions": [
                            {
                                "type": "Action.OpenUrl",
                                "title": "🔗 Open Resource",
                                "url": resource.get("url", "#"),
                            }
                        ],
                    },
                ]
            )

        card = {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": f"🔍 Search Results for '{query}'",
                    "size": "Large",
                    "weight": "Bolder",
                    "color": "Accent",
                },
                {"type": "TextBlock", "text": f"Found {len(resources)} resources", "spacing": "Small", "isSubtle": True},
            ]
            + resource_items,
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": "🎓 Create Learning Path from These",
                    "data": {"action": "create_from_resources", "query": query},
                }
            ],
        }
        return Attachment(content_type="application/vnd.microsoft.card.adaptive", content=card)

    @staticmethod
    def create_skills_card(profile_payload: Dict[str, Any]) -> Attachment:
        """Create card showing the learner's skill profile from SkillGapAgent."""
        profile = profile_payload.get("profile", profile_payload)
        current_skill_details = profile.get("current_skill_details", []) if isinstance(profile, dict) else []
        skills = [
            {
                "name": item.get("skill", "Unknown Skill"),
                "proficiency": item.get("proficiency", 0),
                "category": "Skill",
            }
            for item in current_skill_details
        ]

        skill_items = []
        for skill in skills:
            skill_items.extend(
                [
                    {"type": "TextBlock", "text": f"**{skill['name']}** ({skill['category']})", "spacing": "Medium"},
                    {
                        "type": "TextBlock",
                        "text": f"{'█' * (skill['proficiency'] // 10)}{' ' * (10 - skill['proficiency'] // 10)} {skill['proficiency']}%",
                        "spacing": "Small",
                        "fontType": "Monospace",
                    },
                ]
            )

        card = {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": f"📊 Skills Profile for {profile.get('name', profile.get('user_id', 'learner'))}",
                    "size": "Large",
                    "weight": "Bolder",
                    "color": "Accent",
                },
                {
                    "type": "TextBlock",
                    "text": f"Target role: {profile.get('target_role', 'N/A')} | Target certification: {profile.get('target_certification', 'N/A')}",
                    "spacing": "Small",
                    "isSubtle": True,
                    "wrap": True,
                },
            ]
            + skill_items
            + [
                {
                    "type": "TextBlock",
                    "text": "\nLegend: stronger bars indicate higher current proficiency.",
                    "spacing": "Large",
                    "isSubtle": True,
                    "size": "Small",
                    "wrap": True,
                }
            ],
            "actions": [
                {"type": "Action.Submit", "title": "🎯 Update Skills", "data": {"action": "update_skills"}},
                {"type": "Action.Submit", "title": "📈 View Progress", "data": {"action": "view_progress"}},
            ],
        }
        return Attachment(content_type="application/vnd.microsoft.card.adaptive", content=card)

    @staticmethod
    def create_help_card() -> Attachment:
        """Create help card with command examples."""
        card = {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "❓ Help & Commands",
                    "size": "Large",
                    "weight": "Bolder",
                    "color": "Accent",
                },
                {"type": "TextBlock", "text": "Here's what I can help you with:", "spacing": "Medium", "wrap": True},
                {
                    "type": "FactSet",
                    "facts": [
                        {"title": "🎓 Create learning path", "value": "Type: 'Create learning path for [role name]'"},
                        {"title": "📊 View skills", "value": "Type: 'My skills'"},
                        {"title": "🔍 Search resources", "value": "Type: 'I want to learn [topic]' or ask a learning question"},
                        {"title": "👋 Greeting", "value": "Type: 'Hello' or 'Hi'"},
                        {"title": "❓ Help", "value": "Type: 'Help'"},
                    ],
                },
                {"type": "TextBlock", "text": "**Examples:**", "weight": "Bolder", "spacing": "Large"},
                {
                    "type": "TextBlock",
                    "text": "• Create learning path for Azure Administrator\n• I want to learn Azure AI services\n• My skills",
                    "spacing": "Small",
                    "wrap": True,
                },
            ],
            "actions": [
                {
                    "type": "Action.OpenUrl",
                    "title": "📖 Full Documentation",
                    "url": "https://learn.microsoft.com",
                }
            ],
        }
        return Attachment(content_type="application/vnd.microsoft.card.adaptive", content=card)
