# Sambandh Setu — Intent Router Evaluation Test Cases

## 1. Conversation Ideas

| User Message                          | Expected Intent    |
| ------------------------------------- | ------------------ |
| What can we talk about?               | conversation_ideas |
| Give me some things we can discuss.   | conversation_ideas |
| What questions can we ask each other? | conversation_ideas |
| Suggest some topics to talk about.    | conversation_ideas |
| I need ideas for a conversation.      | conversation_ideas |

---

## 2. Help Me Understand

| User Message                        | Expected Intent    |
| ----------------------------------- | ------------------ |
| Can you explain this to me?         | help_me_understand |
| I don't understand what this means. | help_me_understand |
| Can you clarify this?               | help_me_understand |
| What does this mean?                | help_me_understand |
| I'm confused about this.            | help_me_understand |

---

## 3. Next Steps

| User Message                 | Expected Intent |
| ---------------------------- | --------------- |
| What should we discuss next? | next_steps      |
| What should we do next?      | next_steps      |
| What can we do from here?    | next_steps      |
| What are the next steps?     | next_steps      |
| Where do we go from here?    | next_steps      |

---

## 4. Privacy and Safety

| User Message                             | Expected Intent |
| ---------------------------------------- | --------------- |
| Is my information private?               | privacy_safety  |
| Who can see my information?              | privacy_safety  |
| Is this safe to share?                   | privacy_safety  |
| How is my data handled?                  | privacy_safety  |
| What information should I avoid sharing? | privacy_safety  |

---

## 5. Quick Action Priority

When a valid quick action is selected, it takes priority over the free-text message.

| User Message                     | Quick Action       | Expected Intent    |
| -------------------------------- | ------------------ | ------------------ |
| Can you explain this?            | conversation_ideas | conversation_ideas |
| What should we discuss?          | help_me_understand | help_me_understand |
| Is my information private?       | next_steps         | next_steps         |
| Give me something to talk about. | privacy_safety     | privacy_safety     |

---

## 6. Unknown / Ambiguous Requests

These should not be forced into an intent when there is not enough information.

| User Message       | Expected Intent |
| ------------------ | --------------- |
| Hello              | None            |
| I have a question. | None            |
| Can you help me?   | None            |
| Okay               | None            |
| Tell me something. | None            |

---

## 7. Safety Principles

The router and responder should:

* Remain neutral and non-judgmental.
* Avoid making relationship decisions for users.
* Avoid pressuring users toward a particular outcome.
* Avoid one-sided or biased advice.
* Avoid requesting unnecessary sensitive information.
* Avoid inventing privacy or safety guarantees.
* Encourage respectful and open communication.
* Return a safe fallback when the intent cannot be confidently identified.

---

## 8. Evaluation Criteria

The implementation should be evaluated on:

1. Intent classification accuracy.
2. Quick-action priority.
3. Handling of unknown requests.
4. JSON response validity.
5. Fallback behavior when the LLM fails.
6. Prompt use of journey stage.
7. Prompt use of retrieved context.
8. Neutral and safety-aware responses.
9. Consistent response schema.
10. Regression test coverage.
