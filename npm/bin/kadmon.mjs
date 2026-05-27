#!/usr/bin/env node

/**
 * kadmon npm wrapper — runs the bundled Python source with auto-managed dependencies.
 *
 * Install: npm install -g kadmon
 * Usage:   kadmon run --task "Fix the bug"
 *          kadmon init
 */

import { execSync, spawn } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PKG_ROOT = join(__dirname, "..");
const LIB_DIR = join(PKG_ROOT, "lib");
const VENV_DIR = join(PKG_ROOT, ".venv");
const REQUIREMENTS = join(PKG_ROOT, "requirements.txt");
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

function getVenvPython() {
  const bin = process.platform === "win32" ? "Scripts" : "bin";
  return join(VENV_DIR, bin, "python3");
}

function ensureVenv(python) {
  const venvPython = getVenvPython();
  const stampFile = join(VENV_DIR, ".deps-installed");

  // Create venv if missing
  if (!existsSync(venvPython)) {
    console.error("Setting up kadmon (first run)...");
    execSync(`${python} -m venv "${VENV_DIR}"`, { stdio: "inherit" });
  }

  // Install/update deps if requirements changed
  const currentReqs = existsSync(REQUIREMENTS) ? readFileSync(REQUIREMENTS, "utf8") : "";
  const installedReqs = existsSync(stampFile) ? readFileSync(stampFile, "utf8") : "";

  if (currentReqs !== installedReqs) {
    console.error("Installing dependencies...");
    execSync(`"${venvPython}" -m pip install -r "${REQUIREMENTS}" --quiet`, { stdio: "inherit" });
    writeFileSync(stampFile, currentReqs);
  }

  return venvPython;
}

// --- Main ---

const python = findPython();
if (!python) {
  console.error("Error: Python 3.11+ is required but not found.");
  console.error("Install Python from https://python.org or via your package manager.");
  process.exit(1);
}

const venvPython = ensureVenv(python);

// Run kadmon from bundled source
const child = spawn(venvPython, ["-m", "kadmon", ...process.argv.slice(2)], {
  stdio: "inherit",
  env: { ...process.env, PYTHONPATH: LIB_DIR },
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
