
import os
import json
from google import genai


class LLMProvider:
    """Base class for LLM providers."""

    def generate(self, prompt):
        raise NotImplementedError(
            "LLM provider has not been configured yet."
        )


class MockLLMProvider(LLMProvider):
    """Mock provider for development and automated tests."""

    def generate(self, prompt):
        prompt_lower = prompt.lower()

        if (
            "conversation ideas" in prompt_lower
            or "suggest conversation" in prompt_lower
        ):
            return {
                "intent": "conversation_ideas",
                "response": [
                    "What is something you both enjoy discussing?",
                    "What is something you would like to understand better about each other?",
                    "What topic would you both feel comfortable talking about?"
                ]
            }

        if (
            "help me understand" in prompt_lower
            or "explain the topic" in prompt_lower
            or "explain the situation" in prompt_lower
        ):
            return {
                "intent": "help_me_understand",
                "response": [
                    "Let's break the topic down into simpler points.",
                    "You can look at the different perspectives involved.",
                    "If something is still unclear, you can ask a more specific question."
                ]
            }

        if (
            "next steps" in prompt_lower
            or "what to do next" in prompt_lower
        ):
            return {
                "intent": "next_steps",
                "response": [
                    "You could discuss the topic openly with each other.",
                    "You could identify what is still unclear.",
                    "You could decide together what you would like to discuss next."
                ]
            }

        if (
            "privacy and safety" in prompt_lower
            or "privacy or safety" in prompt_lower
            or "privacy_safety" in prompt_lower
        ):
            return {
                "intent": "privacy_safety",
                "response": [
                    "Please review the available privacy and safety information before sharing sensitive information.",
                    "Avoid sharing unnecessary personal or sensitive details.",
                    "If you have a specific privacy concern, ask about that concern directly."
                ]
            }

        return {
            "intent": None,
            "response": [
                "I could not confidently identify the request."
            ]
        }


class GeminiLLMProvider(LLMProvider):
    """Gemini provider using the project's configured API key."""

    def __init__(self, api_key=None, timeout_seconds=10.0):
        api_key = api_key or os.environ.get("LLM_API_KEY")

        if not api_key:
            raise ValueError(
                "LLM_API_KEY is required for Gemini."
            )

        self.client = genai.Client(
            api_key=api_key,
            http_options={
                "timeout": int(timeout_seconds * 1000)
            }
        )

    def generate(self, prompt):
        try:
            interaction = self.client.interactions.create(
                model="gemini-3.8-flash",
                input=prompt
            )

            output_text = interaction.output_text.strip()

            # Remove Markdown code fences if the provider returns them.
            if output_text.startswith("```json"):
                output_text = output_text[7:]
            elif output_text.startswith("```"):
                output_text = output_text[3:]

            if output_text.endswith("```"):
                output_text = output_text[:-3]

            return json.loads(output_text.strip())

        except Exception:
            # Do not print prompts, credentials, or provider error details.
            return None


if __name__ == "__main__":
    print("Testing MockLLMProvider...")

    provider = MockLLMProvider()

    result = provider.generate(
        "Generate three neutral conversation ideas."
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))