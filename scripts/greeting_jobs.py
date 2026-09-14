"""Load tracked greeting definitions and reconcile the private Hermes job store."""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

DEFINITIONS_DIR = Path(__file__).resolve().parents[1] / "cron/definitions"
JOB_NAMES = ("morning_greeting", "nightly_greeting")
DEFINITION_FIELDS = {"name", "schedule", "prompt", "script", "no_agent", "deliver", "enabled_toolsets"}


def load_definition(name: str) -> dict:
    if name not in JOB_NAMES:
        raise ValueError("Unknown greeting job.")
    definition = json.loads((DEFINITIONS_DIR / f"{name}.json").read_text(encoding="utf-8"))
    if not isinstance(definition, dict) or set(definition) != DEFINITION_FIELDS:
        raise ValueError("Greeting definitions must contain only the supported static fields.")
    if definition["name"] != name or definition["script"] != f"{name}.py":
        raise ValueError("Greeting name and script must match the definition filename.")
    if (
        definition["no_agent"] is not True
        or definition["deliver"] != "origin"
        or definition["enabled_toolsets"] is not None
    ):
        raise ValueError("Greeting jobs require no-agent mode, origin delivery and no agent toolset override.")
    if not isinstance(definition["prompt"], str) or not definition["prompt"].strip():
        raise ValueError("Greeting job description must not be empty.")
    schedule = definition["schedule"]
    match = re.fullmatch(r"([0-9]{1,2}) ([0-9]{1,2}) \* \* \*", schedule) if isinstance(schedule, str) else None
    if match is None:
        raise ValueError("Greeting schedules must run daily; the scripts handle the workday calendar.")
    dt.time(hour=int(match[2]), minute=int(match[1]))
    return definition


def owner_chat_id(home: Path, allowed: list[str]) -> str:
    """Preserve the configured nightly origin only when it is an allowed owner DM."""
    if not allowed:
        raise RuntimeError("No owner Feishu chat IDs configured.")
    jobs_path = home / "cron/jobs.json"
    if jobs_path.exists():
        for job in json.loads(jobs_path.read_text(encoding="utf-8")).get("jobs", []):
            if Path(job.get("script") or "").name == "nightly_greeting.py":
                origin = job.get("origin") or {}
                if origin.get("platform") == "feishu" and origin.get("chat_id") in allowed:
                    return origin["chat_id"]
    return allowed[0]


def install_job(name: str, home: Path, destination: str) -> dict:
    from cron import jobs

    definition = load_definition(name)
    if not re.fullmatch(r"oc_[A-Za-z0-9_]+", destination):
        raise ValueError("Greeting destination must be a Feishu chat ID.")
    matches = [
        job
        for job in jobs.list_jobs(include_disabled=True)
        if job.get("name") == name or Path(job.get("script") or "").name == definition["script"]
    ]
    if len(matches) > 1:
        raise RuntimeError(f"Multiple {name} jobs exist; refusing to add another.")
    definition.update(origin={"platform": "feishu", "chat_id": destination}, workdir=str(home.resolve()))
    if not matches:
        return jobs.create_job(**definition)

    current = jobs.get_job(matches[0]["id"])
    if current is None:
        raise RuntimeError(f"The {name} job disappeared during installation; retry the update.")
    updates = {key: value for key, value in definition.items() if current.get(key) != value}
    # Reapplying metadata must not advance a pending run or clear a manual run.
    schedule = current.get("schedule") or {}
    if schedule.get("kind") == "cron" and schedule.get("expr") == definition["schedule"]:
        updates.pop("schedule", None)
    return jobs.update_job(current["id"], updates) if updates else current
