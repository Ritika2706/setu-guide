from app.core.pipeline import run_pipeline


# ---------------------------------------------------------
# Basic intent tests
# ---------------------------------------------------------

def test_conversation_ideas():
    result = run_pipeline("What can we talk about?")

    assert result["intent"] == "conversation_ideas"
    assert isinstance(result["response"], list)
    assert len(result["response"]) > 0


def test_help_me_understand():
    result = run_pipeline("Can you explain this to me?")

    assert result["intent"] == "help_me_understand"
    assert isinstance(result["response"], list)
    assert len(result["response"]) > 0


def test_next_steps():
    result = run_pipeline("What should we discuss next?")

    assert result["intent"] == "next_steps"
    assert isinstance(result["response"], list)
    assert len(result["response"]) > 0


def test_privacy_safety():
    result = run_pipeline("Is my information private?")

    assert result["intent"] == "privacy_safety"
    assert isinstance(result["response"], list)
    assert len(result["response"]) > 0


# ---------------------------------------------------------
# Quick-action priority
# ---------------------------------------------------------

def test_quick_action_priority():
    result = run_pipeline(
        "Can you explain this?",
        quick_action="conversation_ideas"
    )

    assert result["intent"] == "conversation_ideas"


# ---------------------------------------------------------
# Unknown requests
# ---------------------------------------------------------

def test_unknown_message():
    result = run_pipeline("Hello, I have a question.")

    assert result["intent"] is None
    assert isinstance(result["response"], list)
    assert len(result["response"]) > 0


# ---------------------------------------------------------
# LLM response validation
# ---------------------------------------------------------

def test_invalid_llm_response_fallback():
    from app.core.responder import validate_response

    invalid_response = {
        "intent": "invalid_intent",
        "response": ["Some response"]
    }

    assert validate_response(invalid_response) is False


def test_pipeline_uses_fallback_when_llm_response_is_invalid():

    class InvalidProvider:

        def generate(self, prompt):
            return {
                "intent": "invalid_intent",
                "response": ["Invalid response"]
            }

    from app.core import pipeline

    original_get_provider = pipeline.get_provider

    pipeline.get_provider = lambda use_gemini=False: InvalidProvider()

    try:
        result = pipeline.run_pipeline(
            "What can we talk about?",
            use_gemini=True
        )

        assert result["intent"] == "conversation_ideas"
        assert isinstance(result["response"], list)

    finally:
        pipeline.get_provider = original_get_provider


def test_pipeline_fallback_when_provider_fails():

    class FailingProvider:

        def generate(self, prompt):
            raise RuntimeError("Simulated provider failure")

    from app.core import pipeline

    original_get_provider = pipeline.get_provider

    pipeline.get_provider = lambda use_gemini=False: FailingProvider()

    try:
        result = pipeline.run_pipeline(
            "What can we talk about?",
            use_gemini=True
        )

        assert result["intent"] == "conversation_ideas"
        assert isinstance(result["response"], list)

    finally:
        pipeline.get_provider = original_get_provider


# ---------------------------------------------------------
# Additional evaluation cases
# ---------------------------------------------------------

def test_conversation_question_variant():
    result = run_pipeline(
        "What questions can we ask each other?"
    )

    assert result["intent"] == "conversation_ideas"


def test_privacy_question_variant():
    result = run_pipeline(
        "Who can see my information?"
    )

    assert result["intent"] == "privacy_safety"


def test_next_steps_variant():
    result = run_pipeline(
        "What are the next steps?"
    )

    assert result["intent"] == "next_steps"


def test_understanding_variant():
    result = run_pipeline(
        "I don't understand what this means."
    )

    assert result["intent"] == "help_me_understand"


# ---------------------------------------------------------
# Journey stage and retrieved context
# ---------------------------------------------------------

def test_journey_stage_and_context():

    result = run_pipeline(
        user_message="What can we talk about?",
        journey_stage="Connect",
        retrieved_context=(
            "Both users want to get to know each other better."
        )
    )

    assert result["intent"] == "conversation_ideas"
    assert isinstance(result["response"], list)

# ---------------------------------------------------------
# Day 3 - LLM Response Evaluation
# ---------------------------------------------------------

def test_valid_response_schema():

    from app.core.responder import validate_response

    valid_response = {
        "intent": "conversation_ideas",
        "response": [
            "What do you enjoy talking about?",
            "What would you like to learn about each other?"
        ]
    }

    assert validate_response(valid_response) is True


def test_invalid_intent_schema():

    from app.core.responder import validate_response

    invalid_response = {
        "intent": "unknown_intent",
        "response": [
            "Some response"
        ]
    }

    assert validate_response(invalid_response) is False


def test_missing_response_field():

    from app.core.responder import validate_response

    invalid_response = {
        "intent": "conversation_ideas"
    }

    assert validate_response(invalid_response) is False


def test_response_must_be_list():

    from app.core.responder import validate_response

    invalid_response = {
        "intent": "conversation_ideas",
        "response": "This should be a list."
    }

    assert validate_response(invalid_response) is False


def test_response_items_must_be_strings():

    from app.core.responder import validate_response

    invalid_response = {
        "intent": "conversation_ideas",
        "response": [
            "Valid string",
            123
        ]
    }

    assert validate_response(invalid_response) is False


def test_empty_response_is_invalid():

    from app.core.responder import validate_response

    invalid_response = {
        "intent": "conversation_ideas",
        "response": []
    }

    assert validate_response(invalid_response) is False


def test_fallback_after_invalid_provider_response():

    class InvalidProvider:

        def generate(self, prompt):
            return {
                "intent": "invalid_intent",
                "response": [
                    "Invalid response"
                ]
            }

    from app.core import pipeline

    original_get_provider = pipeline.get_provider

    pipeline.get_provider = lambda use_gemini=False: InvalidProvider()

    try:

        result = pipeline.run_pipeline(
            "What can we talk about?",
            use_gemini=True
        )

        assert result["intent"] == "conversation_ideas"
        assert isinstance(result["response"], list)
        assert len(result["response"]) > 0

    finally:

        pipeline.get_provider = original_get_provider


def test_fallback_after_provider_failure():

    class FailingProvider:

        def generate(self, prompt):
            raise RuntimeError("Simulated LLM failure")

    from app.core import pipeline

    original_get_provider = pipeline.get_provider

    pipeline.get_provider = lambda use_gemini=False: FailingProvider()

    try:

        result = pipeline.run_pipeline(
            "What can we talk about?",
            use_gemini=True
        )

        assert result["intent"] == "conversation_ideas"
        assert isinstance(result["response"], list)
        assert len(result["response"]) > 0

    finally:

        pipeline.get_provider = original_get_provider

# ---------------------------------------------------------
# Day 3 - Journey Stage, Context and Safety Evaluation
# ---------------------------------------------------------

def test_journey_stage_is_used_in_prompt():

    from app.core import pipeline

    captured_prompt = {}

    class CaptureProvider:

        def generate(self, prompt):
            captured_prompt["value"] = prompt

            return {
                "intent": "conversation_ideas",
                "response": [
                    "What would you both like to discuss?"
                ]
            }

    original_get_provider = pipeline.get_provider

    pipeline.get_provider = lambda use_gemini=False: CaptureProvider()

    try:

        result = pipeline.run_pipeline(
            user_message="What can we talk about?",
            journey_stage="Connect",
            retrieved_context="Both users want to know each other better.",
            use_gemini=True
        )

        assert result["intent"] == "conversation_ideas"
        assert "Connect" in captured_prompt["value"]

    finally:

        pipeline.get_provider = original_get_provider


def test_retrieved_context_is_used_in_prompt():

    from app.core import pipeline

    captured_prompt = {}

    class CaptureProvider:

        def generate(self, prompt):
            captured_prompt["value"] = prompt

            return {
                "intent": "conversation_ideas",
                "response": [
                    "What would you both like to discuss?"
                ]
            }

    original_get_provider = pipeline.get_provider

    pipeline.get_provider = lambda use_gemini=False: CaptureProvider()

    try:

        result = pipeline.run_pipeline(
            user_message="What can we talk about?",
            journey_stage="Understand",
            retrieved_context="The users are discussing expectations.",
            use_gemini=True
        )

        assert result["intent"] == "conversation_ideas"
        assert "The users are discussing expectations." in captured_prompt["value"]

    finally:

        pipeline.get_provider = original_get_provider


def test_all_supported_intents_return_valid_responses():

    from app.core import pipeline

    test_cases = [
        ("What can we talk about?", "conversation_ideas"),
        ("Can you explain this?", "help_me_understand"),
        ("What should we do next?", "next_steps"),
        ("Is my information private?", "privacy_safety"),
    ]

    for message, expected_intent in test_cases:

        result = pipeline.run_pipeline(
            user_message=message,
            use_gemini=False
        )

        assert result["intent"] == expected_intent
        assert isinstance(result["response"], list)
        assert len(result["response"]) > 0

        for item in result["response"]:
            assert isinstance(item, str)


def test_unknown_request_is_handled_safely():

    from app.core import pipeline

    result = pipeline.run_pipeline(
        user_message="Hello, I have a question.",
        use_gemini=False
    )

    assert result["intent"] is None
    assert isinstance(result["response"], list)
    assert len(result["response"]) > 0


def test_quick_action_overrides_free_text_in_pipeline():

    from app.core import pipeline

    result = pipeline.run_pipeline(
        user_message="Can you explain this to me?",
        quick_action="conversation_ideas",
        use_gemini=False
    )

    assert result["intent"] == "conversation_ideas"


def test_privacy_prompt_contains_safety_guidance():

    from app.core import pipeline

    prompt = pipeline.load_prompt(
        "privacy_safety",
        "Is my information private?",
        journey_stage="Connect",
        retrieved_context="No additional context provided."
    )

    prompt_lower = prompt.lower()

    assert "privacy" in prompt_lower
    assert "safety" in prompt_lower
    assert "sensitive" in prompt_lower


def test_prompts_contain_required_context_placeholders():

    from app.core import pipeline

    for intent in pipeline.PROMPT_FILES:

        prompt = pipeline.load_prompt(
            intent,
            "Test user message",
            journey_stage="Reflect",
            retrieved_context="Test retrieved context."
        )

        assert "Test user message" in prompt
        assert "Reflect" in prompt
        assert "Test retrieved context." in prompt


def test_pipeline_falls_back_when_provider_returns_malformed_output(monkeypatch):
    from app.core import pipeline

    class MalformedProvider:
        def generate(self, prompt):
            return '{"intent": "conversation_ideas", "response": '

    monkeypatch.setattr(
        pipeline, "get_provider", lambda: MalformedProvider()
    )

    result = pipeline.run_pipeline("What can we talk about?")

    assert result["intent"] == "conversation_ideas"
    assert result["response"]
    assert all(isinstance(item, str) for item in result["response"])


def test_pipeline_falls_back_when_provider_returns_wrong_intent(monkeypatch):
    from app.core import pipeline

    class WrongIntentProvider:
        def generate(self, prompt):
            return {
                "intent": "privacy_safety",
                "response": ["A valid response for a different intent."]
            }

    monkeypatch.setattr(
        pipeline, "get_provider", lambda: WrongIntentProvider()
    )

    result = pipeline.run_pipeline("What can we talk about?")

    assert result["intent"] == "conversation_ideas"
    assert "What is something you both enjoy discussing?" in result["response"]


def test_pipeline_falls_back_when_provider_returns_none(monkeypatch):
    from app.core import pipeline

    class EmptyProvider:
        def generate(self, prompt):
            return None

    monkeypatch.setattr(
        pipeline, "get_provider", lambda: EmptyProvider()
    )

    result = pipeline.run_pipeline("What can we talk about?")

    assert result["intent"] == "conversation_ideas"
    assert result["response"]
    assert all(isinstance(item, str) for item in result["response"])


def test_mock_mode_does_not_initialize_live_provider(monkeypatch):
    from types import SimpleNamespace
    from app.core import pipeline

    monkeypatch.setattr(
        pipeline,
        "get_settings",
        lambda: SimpleNamespace(
            use_mock=True,
            llm_provider="gemini",
        ),
    )

    provider = pipeline.get_provider()

    assert isinstance(provider, pipeline.MockLLMProvider)