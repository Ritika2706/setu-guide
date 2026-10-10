# Sambandh Setu — Backend Integration Contract

## Purpose

This module provides intent routing, prompt construction, LLM response generation, JSON validation, and fallback handling for the Setu Guide.

The backend can call the pipeline through the `handle_request()` function.

---

## Request Structure

The current internal request format is:

```json
{
    "message": "What can we talk about?",
    "quick_action": null,
    "journey_stage": "Connect",
    "retrieved_context": "Both users want to get to know each other better."
}
```

### Fields

| Field               | Required | Description                                     |
| ------------------- | -------- | ----------------------------------------------- |
| `message`           | Yes      | User's free-text message                        |
| `quick_action`      | No       | Selected Setu Guide action                      |
| `journey_stage`     | No       | Current relationship/journey stage              |
| `retrieved_context` | No       | Context supplied by the RAG/retrieval component |

---

## Response Structure

The pipeline returns:

```json
{
    "intent": "conversation_ideas",
    "response": [
        "What is something you both enjoy discussing?",
        "What is something you would like to understand better about each other?",
        "What topic would you both feel comfortable talking about?"
    ]
}
```

### Response Fields

| Field      | Description                        |
| ---------- | ---------------------------------- |
| `intent`   | One of the supported intent values |
| `response` | List of response strings           |

---

## Supported Intents

```text
conversation_ideas
help_me_understand
next_steps
privacy_safety
```

---

## Processing Flow

```text
Backend Request
       |
       v
handle_request()
       |
       v
Intent Router
       |
       +---- Quick action available?
       |          |
       |          +---- Yes --> Use quick action
       |          |
       |          +---- No --> Classify free text
       |
       v
Load Intent Prompt
       |
       +---- Journey Stage
       |
       +---- User Message
       |
       +---- Retrieved Context
       |
       v
LLM Provider
       |
       +---- Valid JSON
       |        |
       |        v
       |     Validate
       |
       +---- Failure / Invalid JSON
                |
                v
          Template Fallback
       |
       v
Schema-valid Response
```

---

## Fallback Behavior

If the LLM provider:

* is unavailable,
* returns invalid JSON,
* returns an unsupported intent,
* returns an invalid response structure,

the pipeline uses a predefined template response.

This prevents the backend from receiving an unusable LLM response.

---

## Unknown Intent

If the router cannot confidently determine the user's intent, the pipeline returns:

```json
{
    "intent": null,
    "response": [
        "I could not confidently understand your request. Please try asking your question in a little more detail."
    ]
}
```

---

## Backend Integration Note

The final API request/response schema should be aligned with the backend team's agreed contract before production integration.

The current `handle_request()` interface is an internal integration boundary and can be adapted once the final backend schema is provided.

Expected backend endpoint from the assignment:

```text
POST /v1/guide/chat
```

The AI/ML module should not independently redefine the backend API contract.

---

## Safety Requirements

Responses should remain:

* Neutral
* Non-judgmental
* Respectful
* Supportive

The system should not:

* Make relationship decisions for users
* Pressure users toward a particular outcome
* Provide one-sided relationship advice
* Invent privacy guarantees
* Request unnecessary sensitive information
* Expose retrieved context unnecessarily
