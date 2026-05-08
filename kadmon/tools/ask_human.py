"""Tool for asking the human questions."""

from kadmon.human.channel import HumanChannel, Question, QuestionBatcher
from kadmon.tools.base import Tool, ToolResult


class AskHumanTool(Tool):
    """Ask the human a question when the agent is uncertain or needs clarification."""

    name = "ask_human"
    description = (
        "Ask the human to resolve ambiguity. Use when: the requirement has multiple valid "
        "interpretations, you're missing information you can't infer from the codebase, "
        "or a design decision could go either way. Batch related questions together. "
        "Do NOT use for permission — just for genuine uncertainty about what to build."
    )
    parameters = {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "The question"},
                        "context": {"type": "string", "description": "Why you need this info"},
                        "options": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Suggested answers (optional)",
                        },
                    },
                    "required": ["text"],
                },
                "description": "Questions to ask (batch related ones together)",
            },
        },
        "required": ["questions"],
    }

    def __init__(self, channel: HumanChannel):
        self._channel = channel
        self._batcher = QuestionBatcher()

    def execute(self, questions: list[dict] | None = None, **kwargs) -> ToolResult:
        if not questions:
            return ToolResult(output="Error: provide at least one question", error=True)

        q_objects = [
            Question(
                text=q["text"],
                context=q.get("context", ""),
                options=q.get("options", []),
                category=q.get("category", "general"),
            )
            for q in questions
        ]

        for q in q_objects:
            self._batcher.add(q)

        batch = self._batcher.flush()
        answers = self._channel.ask(batch)

        parts = []
        for a in answers:
            q = next((q for q in batch if q.id == a.question_id), None)
            q_text = q.text if q else "?"
            parts.append(f"Q: {q_text}\nA: {a.text}")

        return ToolResult(output="Human responses:\n\n" + "\n\n".join(parts))
