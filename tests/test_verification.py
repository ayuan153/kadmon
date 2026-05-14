"""Tests for the Intelligent Verification system (QARunner, VerifyTool, SubmitTool gate)."""

import subprocess


from kadmon.qa import QARunner
from kadmon.tools.verify import VerifyTool
from kadmon.tools.submit import SubmitTool


# --- QARunner tests ---


def test_discover_pytest(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.pytest]\n")
    runner = QARunner(str(tmp_path))
    profile = runner.discover()
    assert profile["framework"] == "pytest"


def test_discover_npm(tmp_path):
    (tmp_path / "package.json").write_text('{"scripts": {"test": "jest"}}')
    runner = QARunner(str(tmp_path))
    profile = runner.discover()
    assert profile["framework"] == "npm"


def test_discover_cargo(tmp_path):
    (tmp_path / "Cargo.toml").write_text("[package]\nname = \"x\"\n")
    runner = QARunner(str(tmp_path))
    profile = runner.discover()
    assert profile["framework"] == "cargo"


def test_discover_empty(tmp_path):
    runner = QARunner(str(tmp_path))
    profile = runner.discover()
    assert profile["framework"] is None
    assert all(v is None for v in profile["commands"].values())


def test_run_command_success(tmp_path):
    runner = QARunner(str(tmp_path))
    result = runner.run_command("echo hello")
    assert result.passed is True
    assert "hello" in result.output


def test_run_command_failure(tmp_path):
    runner = QARunner(str(tmp_path))
    result = runner.run_command("exit 1")
    assert result.passed is False


def test_run_command_timeout(tmp_path):
    runner = QARunner(str(tmp_path))
    result = runner.run_command("sleep 10", timeout=1)
    assert result.passed is False
    assert "timed out" in result.output.lower()


# --- VerifyTool tests ---


def test_verify_targeted_no_target(tmp_path):
    tool = VerifyTool(str(tmp_path))
    result = tool.execute(scope="targeted", target="")
    assert result.error


def test_verify_custom_no_command(tmp_path):
    tool = VerifyTool(str(tmp_path))
    result = tool.execute(scope="custom", command="")
    assert result.error


def test_verify_discover(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.pytest]\n")
    tool = VerifyTool(str(tmp_path))
    result = tool.execute(scope="discover")
    assert "framework" in result.output
    assert "pytest" in result.output


def test_verify_sets_last_passed(tmp_path):
    tool = VerifyTool(str(tmp_path))
    assert tool.last_passed is False
    tool.execute(scope="custom", command="echo ok")
    assert tool.last_passed is True


def test_verify_custom_passes(tmp_path):
    tool = VerifyTool(str(tmp_path))
    result = tool.execute(scope="custom", command="echo hello")
    assert not result.error
    assert tool.last_passed is True


# --- SubmitTool gate tests ---


def test_submit_blocked_without_verification(tmp_path):
    verify = VerifyTool(str(tmp_path))
    verify.last_passed = False
    tool = SubmitTool(str(tmp_path), verify_tool=verify)
    result = tool.execute()
    assert result.error


def test_submit_allowed_with_verification(tmp_path):
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), capture_output=True)
    (tmp_path / "file.txt").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), capture_output=True)
    (tmp_path / "file.txt").write_text("changed")

    verify = VerifyTool(str(tmp_path))
    verify.last_passed = True
    tool = SubmitTool(str(tmp_path), verify_tool=verify)
    result = tool.execute()
    assert not result.error
    assert "changed" in result.output


def test_submit_no_verify_tool(tmp_path):
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), capture_output=True)
    (tmp_path / "file.txt").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), capture_output=True)
    (tmp_path / "file.txt").write_text("changed")

    tool = SubmitTool(str(tmp_path), verify_tool=None)
    result = tool.execute()
    assert not result.error
