1. conversation_ideas
2. help_me_understand
3. next_steps
4. privacy_safety



# Sambandh Setu - Intent Router

## Supported Intents

### 1. conversation_ideas

Purpose:
Help the user generate respectful and meaningful conversation ideas.

Examples:
- "What can we talk about?"
- "Give us some questions to discuss."
- "Can you suggest some conversation topics?"

---

### 2. help_me_understand

Purpose:
Help the user understand or clarify a topic, question, or situation.

Examples:
- "Can you explain this to me?"
- "I don't understand this."
- "What does this mean?"

---

### 3. next_steps

Purpose:
Provide guidance about possible next steps based on the user's current conversation or journey stage.

Examples:
- "What should we discuss next?"
- "What can we do next?"
- "What should I ask now?"

---

### 4. privacy_safety

Purpose:
Handle questions or concerns related to privacy, consent, safety, and sensitive information.

Examples:
- "Is my information private?"
- "Who can see my information?"
- "How is my data used?"
- "Is this conversation safe?"

---

# Intent Routing Logic

## Rule 1: Quick Action Priority

If the user selects a quick action, the selected quick action takes priority over free-text classification.

Example:

Quick Action:
conversation_ideas

User Message:
"I don't know what to talk about."

Result:
conversation_ideas


## Rule 2: Free-Text Classification

If no quick action is selected, classify the user's message based on its meaning.

The message should be classified into one of the supported intents:

- conversation_ideas
- help_me_understand
- next_steps
- privacy_safety


## Rule 3: Pass the Intent Forward

After identifying the intent, pass the selected intent to the corresponding prompt and LLM responder.

The LLM responder will then generate the appropriate response.