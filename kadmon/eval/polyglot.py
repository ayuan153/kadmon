"""Aider Polyglot benchmark runner for kadmon."""

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

import click


EXERCISM_REPOS = {
    "python": "https://github.com/exercism/python.git",
    "javascript": "https://github.com/exercism/javascript.git",
    "go": "https://github.com/exercism/go.git",
    "rust": "https://github.com/exercism/rust.git",
    "java": "https://github.com/exercism/java.git",
    "cpp": "https://github.com/exercism/cpp.git",
}

# Test commands per language
TEST_COMMANDS = {
    "python": ["pytest", "-x"],
    "javascript": ["npm", "test"],
    "go": ["go", "test", "./..."],
    "rust": ["cargo", "test", "--", "--include-ignored"],
    "java": ["./gradlew", "test"],
    "cpp": ["bash", "-c", "mkdir -p build && cd build && cmake .. && make && ctest"],
}

# Files to exclude from solution (test files, metadata)
TEST_FILE_PATTERNS = {
    "python": "*_test.py",
    "javascript": "*.spec.js",
    "go": "*_test.go",
    "rust": None,  # tests are in the same file or tests/ dir
    "java": "src/test/**",
    "cpp": "*_test.cpp",
}


@dataclass
class ExerciseResult:
    name: str
    language: str
    passed_try1: bool = False
    passed_try2: bool = False
    error: str = ""
    duration: float = 0.0
    tokens_used: int = 0


@dataclass
class BenchmarkSummary:
    total: int = 0
    passed_try1: int = 0
    passed_try2: int = 0
    errors: int = 0
    results: list[ExerciseResult] = field(default_factory=list)

    @property
    def pass_rate_1(self) -> float:
        return self.passed_try1 / self.total if self.total else 0

    @property
    def pass_rate_2(self) -> float:
        return self.passed_try2 / self.total if self.total else 0


class PolyglotRunner:
    """Runs kadmon against Aider Polyglot benchmark exercises."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        provider: str = "anthropic",
        aws_region: str = "us-west-2",
        exercises_dir: str = "tmp.benchmarks/polyglot",
        max_attempts: int = 2,
        languages: list[str] | None = None,
        timeout: int = 180,
    ):
        self.model = model
        self.provider_name = provider
        self.aws_region = aws_region
        self.exercises_dir = Path(exercises_dir)
        self.max_attempts = max_attempts
        self.languages = languages or list(EXERCISM_REPOS.keys())
        self.timeout = timeout

    def setup(self):
        """Clone exercism repos if not already present."""
        self.exercises_dir.mkdir(parents=True, exist_ok=True)
        for lang in self.languages:
            lang_dir = self.exercises_dir / lang
            if not lang_dir.exists():
                url = EXERCISM_REPOS[lang]
                subprocess.run(
                    ["git", "clone", "--depth=1", "--quiet", url, str(lang_dir)],
                    check=True,
                )

    def list_exercises(self) -> list[tuple[str, Path]]:
        """List all available exercises as (language, exercise_path) tuples."""
        exercises = []
        for lang in self.languages:
            practice_dir = self.exercises_dir / lang / "exercises" / "practice"
            if not practice_dir.exists():
                continue
            for ex_dir in sorted(practice_dir.iterdir()):
                if ex_dir.is_dir() and (ex_dir / ".docs" / "instructions.md").exists():
                    exercises.append((lang, ex_dir))
        return exercises

    def run(
        self, limit: int | None = None, output_dir: str = "eval_results/polyglot"
    ) -> BenchmarkSummary:
        """Run the benchmark. Returns summary."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        exercises = self.list_exercises()
        if limit:
            exercises = exercises[:limit]

        summary = BenchmarkSummary(total=len(exercises))

        for i, (lang, ex_path) in enumerate(exercises, 1):
            click.echo(f"  [{i}/{len(exercises)}] {lang}/{ex_path.name}...", nl=False)
            result = self._run_exercise(lang, ex_path)
            # Print result inline
            if result.passed_try1:
                click.echo(f" ✓ pass (try 1, {result.duration:.1f}s)")
            elif result.passed_try2:
                click.echo(f" ✓ pass (try 2, {result.duration:.1f}s)")
            elif result.error:
                click.echo(f" ✗ error: {result.error[:60]}")
            else:
                click.echo(f" ✗ fail ({result.duration:.1f}s)")

            summary.results.append(result)
            if result.passed_try1:
                summary.passed_try1 += 1
            if result.passed_try1 or result.passed_try2:
                summary.passed_try2 += 1
            if result.error:
                summary.errors += 1

            # Save per-exercise result
            result_file = out / f"{lang}_{result.name}.json"
            result_file.write_text(
                json.dumps(
                    {
                        "name": result.name,
                        "language": lang,
                        "passed_try1": result.passed_try1,
                        "passed_try2": result.passed_try2,
                        "error": result.error,
                        "duration": result.duration,
                    },
                    indent=2,
                )
            )

        # Save summary
        (out / "summary.json").write_text(
            json.dumps(
                {
                    "total": summary.total,
                    "passed_try1": summary.passed_try1,
                    "passed_try2": summary.passed_try2,
                    "pass_rate_1": summary.pass_rate_1,
                    "pass_rate_2": summary.pass_rate_2,
                    "errors": summary.errors,
                    "model": self.model,
                    "provider": self.provider_name,
                },
                indent=2,
            )
        )

        return summary

    def _run_exercise(self, lang: str, ex_path: Path) -> ExerciseResult:
        """Run a single exercise with up to max_attempts tries."""
        name = ex_path.name
        start = time.time()

        try:
            # Create working copy
            work_dir = self._setup_work_dir(lang, ex_path)
            solution_files = self._find_solution_files(lang, work_dir)

            if not solution_files:
                return ExerciseResult(name=name, language=lang, error="No solution files found")

            # Build prompt from instructions
            prompt = self._build_prompt(ex_path, solution_files)

            # Attempt 1: run kadmon with instructions
            self._run_kadmon(work_dir, prompt)
            passed = self._run_tests(lang, work_dir)

            if passed:
                return ExerciseResult(
                    name=name,
                    language=lang,
                    passed_try1=True,
                    duration=time.time() - start,
                )

            # Attempt 2: retry with test error output
            if self.max_attempts >= 2:
                error_output = self._get_test_error(lang, work_dir)
                retry_prompt = self._build_retry_prompt(error_output, solution_files)
                self._run_kadmon(work_dir, retry_prompt)
                passed = self._run_tests(lang, work_dir)

                if passed:
                    return ExerciseResult(
                        name=name,
                        language=lang,
                        passed_try2=True,
                        duration=time.time() - start,
                    )

            return ExerciseResult(name=name, language=lang, duration=time.time() - start)

        except Exception as e:
            return ExerciseResult(
                name=name,
                language=lang,
                error=str(e),
                duration=time.time() - start,
            )

    def _setup_work_dir(self, lang: str, ex_path: Path) -> Path:
        """Create a fresh working copy of the exercise."""
        work_dir = Path(f"/tmp/kadmon_polyglot/{lang}/{ex_path.name}")
        if work_dir.exists():
            shutil.rmtree(work_dir)
        shutil.copytree(ex_path, work_dir)
        # Init git so kadmon's submit tool works
        subprocess.run(["git", "init", "--quiet"], cwd=work_dir, check=True)
        subprocess.run(["git", "add", "."], cwd=work_dir, check=True)
        subprocess.run(
            ["git", "commit", "--quiet", "-m", "initial", "--allow-empty"],
            cwd=work_dir,
            check=True,
        )
        return work_dir

    def _find_solution_files(self, lang: str, work_dir: Path) -> list[str]:
        """Find the solution files the agent should edit."""
        exclude = {".docs", ".meta", "__pycache__", "node_modules", ".git", "build"}
        test_pattern = TEST_FILE_PATTERNS.get(lang, "")
        solution_files = []

        ext_map = {
            "python": ".py",
            "javascript": ".js",
            "go": ".go",
            "rust": ".rs",
            "java": ".java",
            "cpp": ".cpp",
        }

        for f in work_dir.rglob("*"):
            if not f.is_file():
                continue
            if any(part in exclude for part in f.parts):
                continue
            # Skip test files
            if test_pattern and f.match(test_pattern):
                continue
            # Only include source files for the language
            if f.suffix == ext_map.get(lang, ""):
                solution_files.append(str(f.relative_to(work_dir)))

        return solution_files

    def _build_prompt(self, ex_path: Path, solution_files: list[str]) -> str:
        """Build the task prompt from exercise docs."""
        docs_dir = ex_path / ".docs"
        parts = []

        intro = docs_dir / "introduction.md"
        if intro.exists():
            parts.append(intro.read_text())

        instructions = docs_dir / "instructions.md"
        if instructions.exists():
            parts.append(instructions.read_text())

        append = docs_dir / "instructions.append.md"
        if append.exists():
            parts.append(append.read_text())

        file_list = " ".join(solution_files)
        parts.append(
            f"\nUse the above instructions to modify the supplied files: {file_list}\n"
            "Don't change the names of existing functions or classes, as they may be "
            "referenced from other code like unit tests, etc.\n"
            "Only use standard libraries, don't suggest installing any packages."
        )

        return "\n\n".join(parts)

    def _build_retry_prompt(self, error_output: str, solution_files: list[str]) -> str:
        """Build retry prompt from test error output."""
        file_list = " ".join(solution_files)
        return (
            "See the testing errors below. The tests are correct, don't try and "
            f"change them. Fix the code in {file_list} to resolve the errors.\n\n"
            f"{error_output}"
        )

    def _run_kadmon(self, work_dir: Path, prompt: str):
        """Run kadmon agent on the exercise."""
        from kadmon.agent.loop import AgentLoop
        from kadmon.tools import create_default_registry

        provider = self._get_provider()
        tools = create_default_registry(str(work_dir))
        agent = AgentLoop(provider=provider, tools=tools, use_planning=False)
        agent.run(prompt)

    def _get_provider(self):
        """Create the LLM provider."""
        if self.provider_name == "bedrock":
            from kadmon.providers.bedrock import BedrockProvider

            return BedrockProvider(model=self.model, aws_region=self.aws_region)
        else:
            from kadmon.providers.anthropic import AnthropicProvider

            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            return AnthropicProvider(model=self.model, api_key=api_key)

    def _run_tests(self, lang: str, work_dir: Path) -> bool:
        """Run tests for the exercise. Returns True if all pass."""
        cmd = TEST_COMMANDS.get(lang)
        if not cmd:
            return False
        try:
            subprocess.run(
                cmd,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=True,
            )
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return False

    def _get_test_error(self, lang: str, work_dir: Path) -> str:
        """Get test error output for retry prompt."""
        cmd = TEST_COMMANDS.get(lang, [])
        try:
            result = subprocess.run(
                cmd,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            output = result.stdout + result.stderr
            # Truncate to avoid blowing up context
            return output[:5000]
        except subprocess.TimeoutExpired:
            return "Tests timed out after 3 minutes."
