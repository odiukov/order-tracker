"""Run tests before replacing the app, then check the deployed image over HTTP."""

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    return subprocess.run(args, cwd=ROOT, check=True, **kwargs)


run("uv", "run", "--frozen", "pytest", "-q")
sha = run("git", "rev-parse", "--short", "HEAD", capture_output=True, text=True).stdout.strip()
tag = f"{sha}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
run("docker", "compose", "up", "--build", "-d", "--wait", "app", env={**os.environ, "ORDER_TRACKER_TAG": tag})
run("uv", "run", "--frozen", "python", "scripts/check_app.py")
print(f"Verified deployed image order-tracker:{tag}")
