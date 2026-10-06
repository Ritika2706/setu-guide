import re
from typing import List
from app.schemas.guide import SafetyFlag

_P = {
    SafetyFlag.prompt_injection: [
        r"ignore (all |any )?(previous|above|prior) (instructions|rules)",
        r"system prompt", r"reveal your (prompt|instructions)", r"you are now",
        r"developer mode", r"pretend (you|to) (are|be)",
    ],
    SafetyFlag.distress: [
        r"want to die", r"kill myself", r"end my life", r"hurt myself", r"self[- ]harm",
        r"no reason to live",
    ],
    SafetyFlag.private_data_request: [
        r"(his|her|their|rohan'?s)\s+(income|salary|phone|number|address|password|date of birth|dob)",
        r"private (answers|data|details)", r"readiness (answers|checklist)",
        r"what did (he|she|they) answer",
    ],
    SafetyFlag.outcome_prediction: [
        r"will (we|it|this|he|she) (work|last|get married|be happy|succeed)",
        r"are we (compatible|meant|a good match)",
        r"is (he|she|this) (the one|right for me)",
        r"chances (of|that)",
    ],
    SafetyFlag.decision_request: [
        r"should i (marry|say yes|say no|reject|accept|break up|leave|continue|stop)",
        r"tell me (what|whether) to decide", r"decide for me",
    ],
}

_OUTPUT_BAD = [
    r"you (will|'ll) (be happy|get married|succeed|last)",
    r"perfect match", r"you should (marry|say yes|say no|break up)",
    r"guaranteed", r"definitely (compatible|meant)",
]
_PRIVATE_OUT = [r"\b\d{10}\b", r"\b[\w.]+@[\w.]+\.\w+\b"]


def check_input(text: str) -> List[SafetyFlag]:
    t = (text or "").lower()
    return [f for f, pats in _P.items() if any(re.search(p, t) for p in pats)]


def check_output(reply: str) -> List[SafetyFlag]:
    t = (reply or "").lower()
    flags = []
    if any(re.search(p, t) for p in _OUTPUT_BAD):
        flags.append(SafetyFlag.outcome_prediction)
    if any(re.search(p, reply or "") for p in _PRIVATE_OUT):
        flags.append(SafetyFlag.private_data_request)
    return flags


SAFE_REPLIES = {
    SafetyFlag.distress: "It sounds like you're going through something heavy. Please reach out to someone you trust or a mental health professional or local helpline right away. I'm here to help with your journey whenever you're ready.",
    SafetyFlag.prompt_injection: "I can only help with guidance for your Setu journey. I can suggest conversation ideas, help you understand a profile, or share next steps.",
    SafetyFlag.private_data_request: "I only use details people have chosen to share, and I can't reveal private answers or personal contact details. I can suggest questions to ask them directly.",
    SafetyFlag.outcome_prediction: "I can't predict how a relationship will go. That depends on both of you. I can suggest questions about future plans and expectations if that helps.",
    SafetyFlag.decision_request: "This decision is yours to make, at your own pace. I can help you reflect with questions about what matters to you.",
    SafetyFlag.unsupported_claim: "I don't have enough information to say that. I can suggest questions you could explore together.",
}
PRIORITY = [SafetyFlag.distress, SafetyFlag.prompt_injection, SafetyFlag.private_data_request,
            SafetyFlag.decision_request, SafetyFlag.outcome_prediction, SafetyFlag.unsupported_claim]


def safe_reply(flags: List[SafetyFlag]) -> str:
    for f in PRIORITY:
        if f in flags:
            return SAFE_REPLIES[f]
    return ""
