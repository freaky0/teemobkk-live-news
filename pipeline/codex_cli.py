"""Direct, subscription-backed Codex CLI calls for the news pipeline."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any

MODEL = "gpt-6-luna"
CODEX_CLI = os.environ.get("CODEX_CLI", "/usr/local/bin/codex")
TIMEOUT_SECONDS = 180


def complete(messages: list[dict[str, str]], *, cwd: str | Path | None = None) -> str:
    """Run Codex directly under the service account; no API key or Hermes fallback."""
    workdir = Path(cwd or os.environ.get(
        "TEEMO_CODEX_WORKDIR", str(Path.home() / ".local/share/teemobkk-news-codex")
    )).expanduser().resolve()
    workdir.mkdir(parents=True, exist_ok=True, mode=0o700)
    prompt = "\n\n".join(
        f"{message.get('role', 'user').upper()}:\n{message.get('content', '')}"
        for message in messages
    )
    with tempfile.NamedTemporaryFile(prefix="codex-response-", suffix=".txt",
                                     dir=workdir, delete=False) as temporary:
        output_path = Path(temporary.name)
    output_path.unlink()
    command = [
        CODEX_CLI, "exec", "--ephemeral", "--model", MODEL,
        "-c", 'model_reasoning_effort="none"',
        "--sandbox", "read-only", "--skip-git-repo-check",
        "--output-last-message", str(output_path),
    ]
    try:
        result = subprocess.run(
            command, input=prompt, cwd=workdir, timeout=TIMEOUT_SECONDS,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            shell=False, check=False,
        )
        if result.returncode:
            detail = (result.stderr or result.stdout or "Codex CLI translation failed").strip()
            raise RuntimeError(detail[:240])
        output = output_path.read_text(encoding="utf-8", errors="replace").strip()
        if not output:
            raise RuntimeError("Codex CLI returned an empty response")
        return output
    finally:
        output_path.unlink(missing_ok=True)
