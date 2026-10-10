# Sambandh Setu - Intent Router


SUPPORTED_INTENTS = {
    "conversation_ideas",
    "help_me_understand",
    "next_steps",
    "privacy_safety",
}


def route_intent(user_message, quick_action=None):
    """
    Determine the user's intent.

    Quick action takes priority over free-text classification.
    """

    # ---------------------------------------------------------
    # Rule 1: Quick action has priority
    # ---------------------------------------------------------

    if quick_action:
        if quick_action in SUPPORTED_INTENTS:
            return quick_action

    # ---------------------------------------------------------
    # Rule 2: Handle empty or invalid messages
    # ---------------------------------------------------------

    if not user_message:
        return None

    message = user_message.lower().strip()

    if not message:
        return None

    # ---------------------------------------------------------
    # Rule 3: Conversation ideas
    # ---------------------------------------------------------

    conversation_keywords = [
        "what can we talk",
        "what should we talk",
        "what do we talk",
        "conversation",
        "questions to ask",
        "questions can we ask",
        "questions to discuss",
        "topics to discuss",
        "things to talk",
        "things we can discuss",
        "what topics",
        "conversation ideas",
        "talk about",
        "discuss with each other",
    ]

    for keyword in conversation_keywords:
        if keyword in message:
            return "conversation_ideas"

    # ---------------------------------------------------------
    # Rule 4: Help me understand
    # ---------------------------------------------------------

    understand_keywords = [
        "explain",
        "don't understand",
        "do not understand",
        "what does this mean",
        "what does that mean",
        "meaning",
        "clarify",
        "confused about",
        "help me understand",
    ]

    for keyword in understand_keywords:
        if keyword in message:
            return "help_me_understand"

    # ---------------------------------------------------------
    # Rule 5: Next steps
    # ---------------------------------------------------------

    next_step_keywords = [
        "what should we do next",
        "what should we discuss next",
        "what can we do next",
        "what do we do next",
        "what are the next steps",
        "next step",
        "next steps",
        "what next",
        "where do we go from here",
        "what can we do from here",
    ]

    for keyword in next_step_keywords:
        if keyword in message:
            return "next_steps"

    # ---------------------------------------------------------
    # Rule 6: Privacy and safety
    # ---------------------------------------------------------

    privacy_keywords = [
        "private",
        "privacy",
        "personal information",
        "my information",
        "who can see",
        "data",
        "safe",
        "safety",
        "consent",
        "data handled",
        "information handled",
        "what information should i avoid",
    ]

    for keyword in privacy_keywords:
        if keyword in message:
            return "privacy_safety"

    # ---------------------------------------------------------
    # Rule 7: No confident match
    # ---------------------------------------------------------

    return None


if __name__ == "__main__":

    test_messages = [
        "What can we talk about?",
        "Can you explain this to me?",
        "What should we discuss next?",
        "Is my information private?",
        "What questions can we ask each other?",
        "Hello, I have a question.",
    ]

    for message in test_messages:

        intent = route_intent(message)

        print(f"Message: {message}")
        print(f"Intent: {intent}")
        print("-" * 50)