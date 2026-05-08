#!/usr/bin/env node

/**
 * kadmon npm wrapper — ensures the Python package is installed and spawns it.
 *
 * Install: npm install -g kadmon
 * Usage:   kadmon run --task "Fix the bug"
 *          kadmon init
 */

import { execSync, spawn } from "node:child_process";
import { existsSync } from "node:fs";

const MIN_PYTHON_VERSION = [3, 11];

function findPython() {
  for (const cmd of ["python3", "python"]) {
    try {
      const version = execSync(`${cmd} --version 2>&1`, { encoding: "utf8" }).trim();
      const match = version.match(/Python (\d+)\.(\d+)/);
      if (match) {
        const [major, minor] = [parseInt(match[1]), parseInt(match[2])];
        if (major > MIN_PYTHON_VERSION[0] || (major === MIN_PYTHON_VERSION[0] && minor >= MIN_PYTHON_VERSION[1])) {
          return cmd;
        }
      }
    } catch {}
  }
  return null;
}

function isKadmonInstalled(python) {
  try {
    execSync(`${python} -c "import kadmon"`, { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

function installKadmon(python) {
  console.error("Installing kadmon Python package...");
  try {
    execSync(`${python} -m pip install kadmon --quiet`, { stdio: "inherit" });
    return true;
  } catch {
    // Try pipx as fallback
    try {
      execSync("pipx install kadmon", { stdio: "inherit" });
      return true;
    } catch {
      return false;
    }
  }
}

// --- Main ---

const python = findPython();
if (!python) {
  console.error("Error: Python 3.11+ is required but not found.");
  console.error("Install Python from https://python.org or via your package manager.");
  process.exit(1);
}

if (!isKadmonInstalled(python)) {
  if (!installKadmon(python)) {
    console.error("Error: Failed to install kadmon Python package.");
    console.error(`Try manually: ${python} -m pip install kadmon`);
    process.exit(1);
  }
}

// Spawn kadmon with all args, forwarding stdio and signals
const child = spawn(python, ["-m", "kadmon", ...process.argv.slice(2)], {
  stdio: "inherit",
  env: process.env,
});

child.on("close", (code) => process.exit(code ?? 1));
child.on("error", (err) => {
  console.error(`Error: ${err.message}`);
  process.exit(1);
});

// Forward signals
for (const sig of ["SIGINT", "SIGTERM", "SIGHUP"]) {
  process.on(sig, () => child.kill(sig));
}
