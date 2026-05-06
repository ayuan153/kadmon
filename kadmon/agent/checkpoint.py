import subprocess


class CheckpointManager:
    """Manages git-based checkpoints for backtracking."""

    def __init__(self, repo_root: str):
        self.repo_root = repo_root
        self._checkpoints: list[str] = []  # stack of stash refs or commit hashes

    def save(self, label: str = "") -> str:
        """Save current changes as a checkpoint. Returns checkpoint ID."""
        # Stage all changes
        self._git("add", "-A")
        # Check if there's anything to stash
        status = self._git("status", "--porcelain")
        if not status.strip():
            return ""  # Nothing to checkpoint
        # Create stash with label
        msg = f"kadmon-checkpoint: {label}" if label else "kadmon-checkpoint"
        self._git("stash", "push", "-m", msg, "--include-untracked")
        # Immediately re-apply (we want the changes in working tree)
        self._git("stash", "apply", "--index")
        ref = self._git("stash", "list", "--format=%H", "-1").strip()
        self._checkpoints.append(ref)
        return ref

    def restore(self, checkpoint_id: str = "") -> bool:
        """Restore to a checkpoint. If no ID given, restore last checkpoint."""
        if not checkpoint_id and not self._checkpoints:
            return False
        # Reset working tree
        self._git("checkout", "--", ".")
        self._git("clean", "-fd")
        # Apply the checkpoint
        ref = checkpoint_id or self._checkpoints[-1]
        try:
            self._git("stash", "apply", ref)
            return True
        except subprocess.CalledProcessError:
            return False

    def discard_last(self) -> bool:
        """Discard the most recent checkpoint from the stash stack."""
        if not self._checkpoints:
            return False
        self._checkpoints.pop()
        try:
            self._git("stash", "drop", "stash@{0}")
            return True
        except subprocess.CalledProcessError:
            return False

    def list_checkpoints(self) -> list[str]:
        """List available checkpoints."""
        output = self._git("stash", "list", "--format=%s")
        return [line for line in output.strip().split("\n") if line.startswith("kadmon-checkpoint")]

    @property
    def has_checkpoints(self) -> bool:
        return len(self._checkpoints) > 0

    def _git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
