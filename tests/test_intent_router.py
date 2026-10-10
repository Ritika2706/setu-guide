from app.core.router import route_intent


# ---------------------------------------------------------
# Conversation Ideas
# ---------------------------------------------------------

def test_conversation_ideas_variations():

    messages = [
        "What can we talk about?",
        "Give me some things we can discuss.",
        "What questions can we ask each other?",
        "Suggest some topics to talk about.",
        "I need ideas for a conversation.",
    ]

    for message in messages:
        assert route_intent(message) == "conversation_ideas"


# ---------------------------------------------------------
# Help Me Understand
# ---------------------------------------------------------

def test_help_me_understand_variations():

    messages = [
        "Can you explain this to me?",
        "I don't understand what this means.",
        "Can you clarify this?",
        "What does this mean?",
        "I'm confused about this.",
    ]

    for message in messages:
        assert route_intent(message) == "help_me_understand"


# ---------------------------------------------------------
# Next Steps
# ---------------------------------------------------------

def test_next_steps_variations():

    messages = [
        "What should we discuss next?",
        "What should we do next?",
        "What can we do from here?",
        "What are the next steps?",
        "Where do we go from here?",
    ]

    for message in messages:
        assert route_intent(message) == "next_steps"


# ---------------------------------------------------------
# Privacy and Safety
# ---------------------------------------------------------

def test_privacy_safety_variations():

    messages = [
        "Is my information private?",
        "Who can see my information?",
        "Is this safe to share?",
        "How is my data handled?",
        "What information should I avoid sharing?",
    ]

    for message in messages:
        assert route_intent(message) == "privacy_safety"


# ---------------------------------------------------------
# Quick Action Priority
# ---------------------------------------------------------

def test_quick_action_always_takes_priority():

    assert route_intent(
        "Can you explain this?",
        quick_action="conversation_ideas"
    ) == "conversation_ideas"

    assert route_intent(
        "What should we discuss?",
        quick_action="help_me_understand"
    ) == "help_me_understand"

    assert route_intent(
        "Is my information private?",
        quick_action="next_steps"
    ) == "next_steps"

    assert route_intent(
        "Give me something to talk about.",
        quick_action="privacy_safety"
    ) == "privacy_safety"


# ---------------------------------------------------------
# Unknown / Ambiguous Requests
# ---------------------------------------------------------

def test_ambiguous_messages_return_none():

    messages = [
        "Hello, I have a question.",
        "Can you help me?",
        "Okay.",
        "Tell me something.",
    ]

    for message in messages:
        assert route_intent(message) is None


# ---------------------------------------------------------
# Empty Messages
# ---------------------------------------------------------

def test_empty_messages_return_none():

    assert route_intent("") is None
    assert route_intent(None) is None
    assert route_intent("   ") is None


# ---------------------------------------------------------
# Invalid Quick Action
# ---------------------------------------------------------

def test_invalid_quick_action_falls_back_to_message():

    result = route_intent(
        "What can we talk about?",
        quick_action="invalid_action"
    )

    assert result == "conversation_ideas"
