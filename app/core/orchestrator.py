"""Pipeline: route -> input safety -> context -> retrieve -> generate -> output safety.
route/build_context/retrieve/generate are stubs; teammates replace them without changing handle()."""
from typing import List, Tuple
from app.schemas.guide import GuideRequest, GuideResponse, Intent, Safety, SafetyStatus
from app.safety import guard

KEYWORDS = {
    Intent.privacy_safety: ["privacy", "safe", "safety", "private", "report", "block"],
    Intent.conversation_ideas: ["question", "ask", "conversation", "talk about", "idea"],
    Intent.help_me_understand: ["understand", "profile", "common", "match", "compatib"],
    Intent.next_steps: ["next", "what now", "tip", "step"],
}
TEMPLATES = {
    Intent.conversation_ideas: ("Here are some questions you can explore. Choose the ones that feel right.",
                                ["What does a typical day look like for you?", "How do you like to spend your weekends?"]),
    Intent.help_me_understand: ("I can compare what you've both chosen to share. Ask about the things you haven't discussed yet.", []),
    Intent.next_steps: ("Take it at your own pace. Pick one topic for this stage and talk it through.", []),
    Intent.privacy_safety: ("I only use details people choose to share, and I can't reveal private answers. You can pause or leave a journey at any time.", []),
}


def route(req: GuideRequest) -> Intent:  # AI/ML 3 replaces
    if req.intent:
        return req.intent
    t = (req.message or "").lower()
    for intent, words in KEYWORDS.items():
        if any(w in t for w in words):
            return intent
    return Intent.conversation_ideas


# Only these consented fields ever reach retrieval or the LLM. Anything else
# (private reflections, readiness answers, contact details) is dropped here.
# Assumed from the Figma onboarding screens; confirm with Shreya.
ALLOWED_FIELDS = {"interests", "lifestyle", "relationship_priorities", "partner_type",
                  "relocation", "career_importance", "languages", "location"}


def _allowed(d):
    return {k: v for k, v in (d or {}).items() if k in ALLOWED_FIELDS}


def build_context(req: GuideRequest) -> dict:  # lead, with Shreya's data
    return {"stage": req.stage.value, "topic": req.topic, "profiles": {"viewer": _allowed((req.context or {}).get("viewer")),
                         "match": _allowed((req.context or {}).get("match"))}}


def retrieve(intent: Intent, ctx: dict, query: str) -> List[dict]:  # AI/ML 2 replaces
    return []  # chunk format: {"id": str, "text": str}


def generate(intent: Intent, ctx: dict, chunks: List[dict]) -> Tuple[str, List[str], List[str]]:  # AI/ML 3 replaces
    return ("(mock reply)", [], [])


def handle(req: GuideRequest) -> GuideResponse:
    intent = route(req)
    in_flags = guard.check_input(req.message or "")
    if in_flags:
        return GuideResponse(intent=intent, reply=guard.safe_reply(in_flags),
                             safety=Safety(status=SafetyStatus.blocked, flags=in_flags),
                             fallback_used=True)
    out_flags = []
    try:
        ctx = build_context(req)
        chunks = retrieve(intent, ctx, req.message or req.topic or "")
        reply, questions, chips = generate(intent, ctx, chunks)
        out_flags = guard.check_output(reply)
        if out_flags:
            raise ValueError("output failed safety")
        return GuideResponse(intent=intent, reply=reply, questions=questions[:5], chips=chips[:4],
                             sources=[c["id"] for c in chunks])
    except Exception:
        text, qs = TEMPLATES[intent]
        status = SafetyStatus.modified if out_flags else SafetyStatus.passed
        return GuideResponse(intent=intent, reply=text, questions=qs,
                             safety=Safety(status=status, flags=out_flags), fallback_used=True)
