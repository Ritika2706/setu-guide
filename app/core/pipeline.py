"""Intent routing, prompt construction, LLM generation and fallback validation."""

from pathlib import Path

from app.config import get_settings
from app.core.router import route_intent
from app.core.llm_provider import MockLLMProvider, GeminiLLMProvider
from app.core.responder import create_response, validate_response


PROMPT_DIR = Path(__file__).resolve().parent / "prompts"

PROMPT_FILES = {
    "conversation_ideas": "conversation_ideas.txt",
    "help_me_understand": "help_me_understand.txt",
    "next_steps": "next_steps.txt",
    "privacy_safety": "privacy_safety.txt",
}


def load_prompt(
    intent,
    user_message,
    journey_stage="Not provided",
    retrieved_context="Not provided",
):
    """Load an intent-specific prompt and insert request context."""
    if intent not in PROMPT_FILES:
        raise ValueError("Unsupported prompt intent.")

    prompt_path = PROMPT_DIR / PROMPT_FILES[intent]
    prompt = prompt_path.read_text(encoding="utf-8")

    replacements = {
        "[USER_MESSAGE]": user_message or "",
        "[JOURNEY_STAGE]": journey_stage or "Not provided",
        "[RETRIEVED_CONTEXT]": retrieved_context or "Not provided",
    }

    for placeholder, value in replacements.items():
        prompt = prompt.replace(placeholder, str(value))

    return prompt


def get_provider(use_gemini=None):
    """Select a provider using application settings.

    Mock mode always takes precedence to prevent unintended API calls.
    The optional argument remains for compatibility with existing callers.
    """
    settings = get_settings()

    if settings.use_mock:
        return MockLLMProvider()

    provider_name = settings.llm_provider.strip().lower()

    if provider_name == "gemini":
        return GeminiLLMProvider(
            api_key=settings.llm_api_key,
            timeout_seconds=settings.llm_timeout_seconds,
        )

    raise ValueError("Unsupported LLM provider configuration.")


def run_pipeline(
    user_message,
    quick_action=None,
    journey_stage="Not provided",
    retrieved_context="Not provided",
    use_gemini=False,
):
    """Route a request, generate a response, validate it, or use a fallback."""
    intent = route_intent(
        user_message=user_message,
        quick_action=quick_action,
    )

    if intent is None:
        return {
            "intent": None,
            "response": [
                "I could not confidently identify the request. "
                "Could you tell me whether you want conversation ideas, "
                "help understanding a topic, next steps, or privacy guidance?"
            ],
        }

    prompt = load_prompt(
        intent=intent,
        user_message=user_message,
        journey_stage=journey_stage,
        retrieved_context=retrieved_context,
    )

    try:
        provider = get_provider()
        llm_result = provider.generate(prompt)
    except Exception:
        llm_result = None

    if (
        validate_response(llm_result)
        and llm_result.get("intent") == intent
    ):
        return llm_result

    return create_response(intent, user_message)


def handle_request(request, use_gemini=False):
    """Preserve the existing dictionary-based integration interface."""
    return run_pipeline(
        user_message=request.get(
            "message",
            request.get("user_message", ""),
        ),
        quick_action=request.get("quick_action"),
        journey_stage=request.get(
            "journey_stage", "Not provided"
        ),
        retrieved_context=request.get(
            "retrieved_context", "Not provided"
        ),
        use_gemini=use_gemini,
    )


if __name__ == "__main__":
    test_cases = [
        ("What can we talk about?", None),
        ("Can you explain this to me?", None),
        ("What should we discuss next?", None),
        ("Is my information private?", "privacy_safety"),
    ]

    for message, quick_action in test_cases:
        result = run_pipeline(
            user_message=message,
            quick_action=quick_action,
        )
        print(f"\nMessage: {message}")
        print(f"Result: {result}")