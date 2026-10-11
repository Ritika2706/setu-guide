
"""Pipeline: route -> input safety -> context -> retrieve -> generate -> output safety.

The handle() function is the current orchestration entry point.
The API's handle_chat integration remains pending team confirmation.
"""

import json
from typing import List, Tuple

from app.schemas.guide import (
    GuideRequest,
    GuideResponse,
    Intent,
    Safety,
    SafetyStatus,
)
from app.safety import guard
from app.core.router import route_intent
from app.core.pipeline import run_pipeline


KEYWORDS = {
    Intent.privacy_safety: [
        "privacy", "safe", "safety", "private", "report", "block"
    ],
    Intent.conversation_ideas: [
        "question", "ask", "conversation", "talk about", "idea"
    ],
    Intent.help_me_understand: [
        "understand", "profile", "common", "match", "compatib"
    ],
    Intent.next_steps: [
        "next", "what now", "tip", "step"
    ],
}


TEMPLATES = {
    Intent.conversation_ideas: (
        "Here are some questions you can explore. Choose the ones that feel right.",
        [
            "What does a typical day look like for you?",
            "How do you like to spend your weekends?",
        ],
    ),
    Intent.help_me_understand: (
        "I can compare what you've both chosen to share. Ask about the things you haven't discussed yet.",
        [],
    ),
    Intent.next_steps: (
        "Take it at your own pace. Pick one topic for this stage and talk it through.",
        [],
    ),
    Intent.privacy_safety: (
        "I only use details people choose to share, and I can't reveal private answers. You can pause or leave a journey at any time.",
        [],
    ),
}


def route(req: GuideRequest) -> Intent:
    """Prioritize quick actions, then classify free-text messages."""
    quick_action = req.intent.value if req.intent else None

    intent_name = route_intent(
        user_message=req.message or "",
        quick_action=quick_action,
    )

    if intent_name is None:
        return Intent.conversation_ideas

    return Intent(intent_name)


# Confirm the allowed fields against the team's final privacy contract.
ALLOWED_FIELDS = {
    "interests",
    "lifestyle",
    "relationship_priorities",
    "partner_type",
    "relocation",
    "career_importance",
    "languages",
    "location",
}


def _allowed(data):
    """Return only explicitly allowed profile fields."""
    if not isinstance(data, dict):
        return {}

    return {
        key: value
        for key, value in data.items()
        if key in ALLOWED_FIELDS
    }


def build_context(req: GuideRequest) -> dict:
    """Build a restricted context from the request."""
    context = req.context or {}

    return {
        "stage": req.stage.value,
        "topic": req.topic,
        "profiles": {
            "viewer": _allowed(context.get("viewer")),
            "match": _allowed(context.get("match")),
        },
    }


def retrieve(intent: Intent, ctx: dict, query: str) -> List[dict]:
    """Retrieval stub; RAG integration is owned by the relevant teammate."""
    return []  # Expected chunk format: {"id": str, "text": str}


def generate(
    intent: Intent,
    ctx: dict,
    chunks: List[dict],
    user_message: str = "",
) -> Tuple[str, List[str], List[str]]:
    """Generate a response through the configured intent pipeline."""
    from app.config import get_settings

    # Preserve the existing Day 1 mock response expected by API tests.
    if get_settings().use_mock:
        return "(mock reply)", [], []

    result = run_pipeline(
        user_message=user_message,
        quick_action=intent.value,
        journey_stage=ctx.get("stage", "Not provided"),
        retrieved_context=json.dumps(
            {
                "profiles": ctx.get("profiles", {}),
                "chunks": chunks,
            },
            ensure_ascii=False,
        ),
    )

    if not isinstance(result, dict):
        raise ValueError("Pipeline returned an invalid result.")

    if result.get("intent") != intent.value:
        raise ValueError("Pipeline returned a mismatched intent.")

    responses = result.get("response")

    if not isinstance(responses, list) or not responses:
        raise ValueError("Pipeline returned an invalid response.")

    if not all(isinstance(item, str) for item in responses):
        raise ValueError("Pipeline returned invalid response items.")

    reply = "\n\n".join(responses).strip()

    if not reply:
        raise ValueError("Pipeline returned an empty reply.")

    return reply, [], []


def handle(req: GuideRequest) -> GuideResponse:
    """Handle a guide request with input/output safety and template fallback."""
    intent = route(req)

    in_flags = guard.check_input(req.message or "")

    if in_flags:
        return GuideResponse(
            intent=intent,
            reply=guard.safe_reply(in_flags),
            safety=Safety(
                status=SafetyStatus.blocked,
                flags=in_flags,
            ),
            fallback_used=True,
        )

    out_flags = []

    try:
        ctx = build_context(req)
        chunks = retrieve(
            intent,
            ctx,
            req.message or req.topic or "",
        )

        reply, questions, chips = generate(
            intent,
            ctx,
            chunks,
            user_message=req.message or req.topic or "",
        )

        out_flags = guard.check_output(reply)

        if out_flags:
            raise ValueError("Output failed safety checks.")

        return GuideResponse(
            intent=intent,
            reply=reply,
            questions=questions[:5],
            chips=chips[:4],
            sources=[
                chunk["id"]
                for chunk in chunks
                if "id" in chunk
            ],
        )

    except Exception:
        # Use a safe, intent-specific response if generation fails.
        text, questions = TEMPLATES[intent]
        status = (
            SafetyStatus.modified
            if out_flags
            else SafetyStatus.passed
        )

        return GuideResponse(
            intent=intent,
            reply=text,
            questions=questions,
            safety=Safety(
                status=status,
                flags=out_flags,
            ),
            fallback_used=True,
        )
