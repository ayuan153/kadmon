"""Human-in-the-loop: question model, batching, and channel abstraction."""

import time
from dataclasses import dataclass, field
from typing import Protocol

import click


@dataclass
class Question:
    """A question for the human."""

    text: str
    category: str = "general"  # general | architecture | ambiguity | confirmation
    context: str = ""  # Why the agent needs this info
    options: list[str] = field(default_factory=list)  # Suggested answers (optional)
    id: str = ""  # Auto-assigned by batcher


@dataclass
class Answer:
    """Human's response to a question."""

    question_id: str
    text: str
    timestamp: str = ""


class QuestionBatcher:
    """Collects questions and batches them for delivery to the human."""

    def __init__(self, max_batch_size: int = 5):
        self.max_batch_size = max_batch_size
        self._pending: list[Question] = []
        self._next_id = 1

    def add(self, question: Question) -> str:
        """Add a question to the batch. Returns the question ID."""
        question.id = f"q{self._next_id}"
        self._next_id += 1
        self._pending.append(question)
        return question.id

    def is_ready(self) -> bool:
        """True if batch has questions ready to send."""
        return len(self._pending) > 0

    def is_full(self) -> bool:
        """True if batch is at max size."""
        return len(self._pending) >= self.max_batch_size

    def flush(self) -> list[Question]:
        """Return and clear pending questions."""
        batch = self._pending[:]
        self._pending.clear()
        return batch

    @property
    def pending_count(self) -> int:
        return len(self._pending)


class HumanChannel(Protocol):
    """Protocol for delivering questions to a human and getting answers."""

    def ask(self, questions: list[Question]) -> list[Answer]:
        """Send questions to human, block until answers received."""
        ...

    def notify(self, message: str) -> None:
        """Send a non-blocking notification to the human."""
        ...


class CLIChannel:
    """Interactive CLI channel — blocks on input()."""

    def __init__(self, timeout: int = 300):
        self.timeout = timeout

    def ask(self, questions: list[Question]) -> list[Answer]:
        """Print questions to terminal, collect answers via input()."""
        click.echo("\n" + "=" * 60)
        click.echo("🤔 Kadmon needs your input:")
        click.echo("=" * 60)

        answers = []
        for i, q in enumerate(questions, 1):
            click.echo(f"\n[{i}/{len(questions)}] {q.text}")
            if q.context:
                click.echo(f"   Context: {q.context}")
            if q.options:
                for j, opt in enumerate(q.options, 1):
                    click.echo(f"   {j}. {opt}")
                click.echo("   (Enter number or type your answer)")

            response = input("\n> ").strip()

            # If they entered a number and we have options, map it
            if q.options and response.isdigit():
                idx = int(response) - 1
                if 0 <= idx < len(q.options):
                    response = q.options[idx]

            answers.append(
                Answer(
                    question_id=q.id,
                    text=response,
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                )
            )

        click.echo("\n" + "=" * 60)
        click.echo("✓ Got it. Continuing...")
        click.echo("=" * 60 + "\n")
        return answers

    def notify(self, message: str) -> None:
        """Print notification to terminal."""
        click.echo(f"📋 {message}")


class WebhookChannel:
    """Push questions via webhook, poll for responses.

    Posts questions to a URL. Polls a response URL until answers arrive.
    Useful for Slack bots, email integrations, or custom UIs.
    """

    def __init__(
        self,
        push_url: str,
        poll_url: str = "",
        poll_interval: int = 10,
        timeout: int = 3600,
        headers: dict | None = None,
    ):
        self.push_url = push_url
        self.poll_url = poll_url or push_url
        self.poll_interval = poll_interval
        self.timeout = timeout
        self.headers = headers or {}

    def ask(self, questions: list["Question"]) -> list["Answer"]:
        """Post questions to webhook, poll for answers."""
        import json
        import urllib.error
        import urllib.request

        # Push questions
        payload = json.dumps({
            "type": "questions",
            "questions": [
                {
                    "id": q.id,
                    "text": q.text,
                    "category": q.category,
                    "context": q.context,
                    "options": q.options,
                }
                for q in questions
            ],
        }).encode()

        req = urllib.request.Request(
            self.push_url,
            data=payload,
            headers={"Content-Type": "application/json", **self.headers},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=30)

        # Poll for responses
        start = time.time()
        while time.time() - start < self.timeout:
            time.sleep(self.poll_interval)
            try:
                poll_req = urllib.request.Request(
                    self.poll_url,
                    headers=self.headers,
                    method="GET",
                )
                resp = urllib.request.urlopen(poll_req, timeout=30)
                data = json.loads(resp.read())

                if data.get("status") == "answered" and data.get("answers"):
                    return [
                        Answer(
                            question_id=a["question_id"],
                            text=a["text"],
                            timestamp=a.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ")),
                        )
                        for a in data["answers"]
                    ]
            except (urllib.error.URLError, json.JSONDecodeError, KeyError):
                continue  # Keep polling

        # Timeout — return empty answers
        return [
            Answer(question_id=q.id, text="", timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"))
            for q in questions
        ]

    def notify(self, message: str) -> None:
        """Post a notification to the webhook."""
        import json
        import urllib.request

        payload = json.dumps({"type": "notification", "message": message}).encode()
        req = urllib.request.Request(
            self.push_url,
            data=payload,
            headers={"Content-Type": "application/json", **self.headers},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=30)
        except Exception:
            pass  # Notifications are best-effort
