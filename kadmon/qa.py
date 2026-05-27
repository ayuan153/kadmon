from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class QAResult:
    passed: bool
    output: str
    duration: float
    command: str


class QARunner:
    """Discovers and runs verification commands for a project."""

    def __init__(self, repo_root: str, timeout: int = 60):
        self._root = Path(repo_root)
        self._timeout = timeout

    def discover(self) -> dict:
        """Auto-detect test infrastructure. Returns verification profile data."""
        profile: dict = {"framework": None, "commands": {}}

        # Python: pytest
        if (self._root / "pyproject.toml").exists():
            content = (self._root / "pyproject.toml").read_text()
            if "pytest" in content or "[tool.pytest" in content:
                profile["framework"] = "pytest"
                profile["commands"]["unit"] = "pytest tests/ -x"
                profile["commands"]["targeted"] = "pytest {target} -x"
                profile["commands"]["full"] = "pytest tests/"
            if "ruff" in content:
                profile["commands"]["lint"] = "ruff check ."

        # JavaScript: jest/vitest/mocha
        pkg_json = self._root / "package.json"
        if pkg_json.exists():
            import json
            try:
                pkg = json.loads(pkg_json.read_text())
                scripts = pkg.get("scripts", {})
                if "test" in scripts:
                    profile["framework"] = profile["framework"] or "npm"
                    profile["commands"]["unit"] = "npm test"
                    profile["commands"]["full"] = "npm test"
                if "lint" in scripts:
                    profile["commands"]["lint"] = "npm run lint"
            except (json.JSONDecodeError, KeyError):
                pass

        # Rust: cargo
        if (self._root / "Cargo.toml").exists():
            profile["framework"] = profile["framework"] or "cargo"
            profile["commands"]["unit"] = "cargo test"
            profile["commands"]["full"] = "cargo test"
            profile["commands"]["lint"] = "cargo clippy"

        # Makefile
        if (self._root / "Makefile").exists():
            content = (self._root / "Makefile").read_text()
            if "test:" in content or "test :" in content:
                profile["commands"].setdefault("full", "make test")
            if "lint:" in content or "lint :" in content:
                profile["commands"].setdefault("lint", "make lint")

        # Go
        if (self._root / "go.mod").exists():
            profile["framework"] = profile["framework"] or "go"
            profile["commands"].setdefault("unit", "go test ./...")
            profile["commands"].setdefault("targeted", "go test {target}")
            profile["commands"].setdefault("full", "go test ./...")
            profile["commands"].setdefault("lint", "go vet ./...")

        # Java: Gradle
        if (self._root / "build.gradle").exists() or (self._root / "build.gradle.kts").exists():
            profile["framework"] = profile["framework"] or "gradle"
            profile["commands"].setdefault("unit", "./gradlew test")
            profile["commands"].setdefault("full", "./gradlew test")
            profile["commands"].setdefault("lint", "./gradlew check")

        # Java: Maven
        if (self._root / "pom.xml").exists():
            profile["framework"] = profile["framework"] or "maven"
            profile["commands"].setdefault("unit", "mvn test -q")
            profile["commands"].setdefault("full", "mvn test -q")

        # TypeScript
        tsconfig = self._root / "tsconfig.json"
        if tsconfig.exists():
            profile["commands"].setdefault("lint", "npx tsc --noEmit")

        return profile

    def run_targeted(self, target: str) -> QAResult:
        """Run a targeted test (single file or test function)."""
        profile = self.discover()
        cmd_template = profile["commands"].get("targeted", profile["commands"].get("unit", ""))
        if not cmd_template:
            return QAResult(passed=True, output="No test command found.", duration=0, command="")
        cmd = cmd_template.replace("{target}", target)
        return self._run(cmd)

    def run_module(self, module_path: str) -> QAResult:
        """Run tests for a module/directory."""
        profile = self.discover()
        cmd_template = profile["commands"].get("targeted", profile["commands"].get("unit", ""))
        if not cmd_template:
            return QAResult(passed=True, output="No test command found.", duration=0, command="")
        cmd = cmd_template.replace("{target}", module_path)
        return self._run(cmd)

    def run_full(self) -> QAResult:
        """Run the full test suite."""
        profile = self.discover()
        cmd = profile["commands"].get("full", "")
        if not cmd:
            return QAResult(passed=True, output="No test command found.", duration=0, command="")
        return self._run(cmd)

    def run_lint(self) -> QAResult:
        """Run linter."""
        profile = self.discover()
        cmd = profile["commands"].get("lint", "")
        if not cmd:
            return QAResult(passed=True, output="No lint command found.", duration=0, command="")
        return self._run(cmd)

    def run_command(self, command: str, timeout: int | None = None) -> QAResult:
        """Run an arbitrary verification command."""
        return self._run(command, timeout=timeout or self._timeout)

    def _run(self, command: str, timeout: int | None = None) -> QAResult:
        """Execute a command and return QAResult."""
        start = time.time()
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=str(self._root),
                timeout=timeout or self._timeout,
            )
            duration = time.time() - start
            passed = result.returncode == 0
            output = result.stdout + result.stderr
            # Truncate long output
            if len(output) > 3000:
                output = output[:1500] + "\n...truncated...\n" + output[-1500:]
            return QAResult(passed=passed, output=output.strip(), duration=duration, command=command)
        except subprocess.TimeoutExpired:
            return QAResult(passed=False, output=f"Command timed out after {timeout or self._timeout}s", duration=time.time() - start, command=command)
