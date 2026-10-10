import json


SUPPORTED_INTENTS = {
    "conversation_ideas",
    "help_me_understand",
    "next_steps",
    "privacy_safety",
}


def create_response(intent, user_message):
    """
    Create a template response for the selected intent.

    This is used as a fallback when the LLM response
    is unavailable or invalid.
    """

    if intent == "conversation_ideas":
        return {
            "intent": intent,
            "response": [
                "What is something you both enjoy discussing?",
                "What is something you would like to understand better about each other?",
                "What topic would you both feel comfortable talking about?"
            ]
        }

    elif intent == "help_me_understand":
        return {
            "intent": intent,
            "response": [
                "Let's break the topic down into simpler points.",
                "You can look at the different perspectives involved.",
                "If something is still unclear, you can ask a more specific question."
            ]
        }

    elif intent == "next_steps":
        return {
            "intent": intent,
            "response": [
                "You could discuss the topic openly with each other.",
                "You could identify what is still unclear.",
                "You could decide together what you would like to discuss next."
            ]
        }

    elif intent == "privacy_safety":
        return {
            "intent": intent,
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


def validate_response(response):
    """
    Validate that the response follows the expected JSON structure.

    Required structure:

    {
        "intent": "<supported intent>",
        "response": ["string", "string", ...]
    }
    """

    try:
        json_data = json.dumps(response)
        parsed = json.loads(json_data)

        if not isinstance(parsed, dict):
            return False

        if "intent" not in parsed:
            return False

        if "response" not in parsed:
            return False

        if parsed["intent"] not in SUPPORTED_INTENTS:
            return False

        if not isinstance(parsed["response"], list):
            return False

        if len(parsed["response"]) == 0:
            return False

        for item in parsed["response"]:
            if not isinstance(item, str):
                return False

        return True

    except (TypeError, ValueError, json.JSONDecodeError):
        return False


if __name__ == "__main__":

    test_intent = "conversation_ideas"
    test_message = "What can we talk about?"

    result = create_response(
        test_intent,
        test_message
    )

    print("Generated Response:")
    print(json.dumps(result, indent=2))

    print("\nValidation Result:")
    print(validate_response(result))