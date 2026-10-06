from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator


class Stage(str, Enum):
    connect = "connect"
    understand = "understand"
    reflect = "reflect"
    discuss = "discuss"
    agree = "agree"
    family = "family"
    reflect_again = "reflect_again"
    decision = "decision"


class Intent(str, Enum):
    conversation_ideas = "conversation_ideas"
    help_me_understand = "help_me_understand"
    next_steps = "next_steps"
    privacy_safety = "privacy_safety"


class SafetyStatus(str, Enum):
    passed = "pass"
    modified = "modified"
    blocked = "blocked"


class SafetyFlag(str, Enum):
    outcome_prediction = "outcome_prediction"
    decision_request = "decision_request"
    private_data_request = "private_data_request"
    prompt_injection = "prompt_injection"
    unsupported_claim = "unsupported_claim"
    distress = "distress"


class GuideRequest(BaseModel):
    user_id: str
    match_id: str
    stage: Stage
    intent: Optional[Intent] = None
    message: Optional[str] = Field(default=None, max_length=500)
    topic: Optional[str] = Field(default=None, max_length=100)
    context: Optional[Dict[str, Dict[str, Any]]] = None  # {"viewer": {...}, "match": {...}}, consented fields only

    @model_validator(mode="after")
    def need_intent_or_message(self):
        if self.intent is None and not (self.message and self.message.strip()):
            raise ValueError("either intent or message is required")
        return self


class Safety(BaseModel):
    status: SafetyStatus = SafetyStatus.passed
    flags: List[SafetyFlag] = Field(default_factory=list)


class GuideResponse(BaseModel):
    intent: Intent
    reply: str
    questions: List[str] = Field(default_factory=list, max_length=5)
    chips: List[str] = Field(default_factory=list, max_length=4)
    sources: List[str] = Field(default_factory=list)
    safety: Safety = Field(default_factory=Safety)
    fallback_used: bool = False
