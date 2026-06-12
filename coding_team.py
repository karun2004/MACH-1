"""
Coding Team
Builds projects from descriptions.
Uses Codestral (primary) → Groq → Ollama qwen2.5-coder (fallback).
3 self-fix attempts → escalate to DevOps → fail.
"""
import json
import os
import subprocess
from pathlib import Path
from typing import Optional
from agents.base import BaseAgent
from config import settings
from utils.notify import notify_project_complete, notify_project_failed

SYSTEM_PROMPT = """You are the Coding Team of MACH-1, an AI company.
You build complete, working projects from descriptions.

When given a project description, respond with ONLY raw JSON (no markdown fences, no explanation):
{
  "files": [
    {"path": "src/main.py", "content": "full file content here"}
  ],
  "setup_commands": ["pip install requests"],
  "test_commands": ["python src/main.py"],
  "readme": "# Project Name\\nDescription here"
}

CRITICAL RULES:
- Output ONLY valid JSON, nothing else
- File paths must be plain strings like "main.py" or "src/app.py"
- Do NOT wrap paths in markdown links
- Do NOT use markdown code fences
- Write clean, documented, production-ready Python code
- Include requirements.txt in files if there are dependencies
- Include proper error handling and logging"""

FIX_SYSTEM = """You are a code debugger. Given error output and source files,
identify the bug and provide the fix.

Respond with JSON:
{
  "diagnosis": "what went wrong",
  "files": [
    {"path": "file.py", "content": "corrected full content"}
  ]
}"""


class CodingTeam(BaseAgent):
    team_name = "coding"

    def __init__(self):
        super().__init__()
        self.projects_dir = settings.MACH1_HOME / "data" / "projects"
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    def run_task(self, task: dict) -> dict:
        """Build a project from description."""
        desc = task.get("description", "")
        template = task.get("template", "flask-api")
        name = task.get("name", "untitled-project")

        project_id = self.db.add_project(
            name=name, description=desc, template=template
        )
        self.db.update_project_status(project_id, "building")

        prompt = f"""Build a project:
Name: {name}
Description: {desc}

Respond with ONLY valid JSON, no markdown fences, no explanation:
{{"files": [{{"path": "filename.py", "content": "code here"}}], "setup_commands": ["pip install x"], "test_commands": ["python filename.py"], "readme": "# Title"}}"""

        self.log.info(f"Requesting project generation for: {name}")
        result = self.ask_json(prompt, system=SYSTEM_PROMPT, max_tokens=4000)

        if not result:
            self.log.error(f"ask_json returned None for project: {name}")
            self.db.update_project_status(project_id, "failed")
            notify_project_failed(name, "LLM generation failed")
            return {"success": False, "result": "LLM failed to generate project"}

        self.log.info(f"Got project JSON with {len(result.get('files', []))} files")

        # Write files to disk
        project_path = self.projects_dir / name
        project_path.mkdir(parents=True, exist_ok=True)

        try:
            import re
            files = result.get("files", [])
            for f in files:
                # Clean markdown links from paths: [file.py](http://...) → file.py
                clean_path = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', f["path"])
                clean_path = clean_path.strip()
                self.log.info(f"  Writing: {clean_path}")
                fp = project_path / clean_path
                fp.parent.mkdir(parents=True, exist_ok=True)
                fp.write_text(f["content"], encoding="utf-8")

            # Write README
            readme = result.get("readme", f"# {name}\n{desc}")
            (project_path / "README.md").write_text(readme, encoding="utf-8")

            # Write setup commands to a file for manual use
            setup_cmds = result.get("setup_commands", [])
            if setup_cmds:
                setup_script = "#!/bin/bash\n" + "\n".join(setup_cmds) + "\n"
                (project_path / "setup.sh").write_text(setup_script, encoding="utf-8")

            self.db.update_project_status(project_id, "complete")
            self.db.update(
                "UPDATE projects SET local_path = ? WHERE id = ?",
                (str(project_path), project_id),
            )
            notify_project_complete(name)
            return {
                "success": True,
                "result": f"Project built at {project_path}",
                "project_id": project_id,
            }

        except Exception as e:
            self.db.update_project_status(project_id, "failed")
            notify_project_failed(name, str(e))
            return {"success": False, "result": str(e)}

    def _run_tests(self, project_path: Path, commands: list) -> bool:
        """Run test commands, return True if all pass."""
        for cmd in commands:
            try:
                proc = subprocess.run(
                    cmd, shell=True, cwd=str(project_path),
                    capture_output=True, text=True, timeout=120,
                )
                if proc.returncode != 0:
                    self.log.warning(f"Test failed: {cmd}\n{proc.stderr}")
                    return False
            except subprocess.TimeoutExpired:
                self.log.warning(f"Test timed out: {cmd}")
                return False
        return True

    def _attempt_fix(self, project_id: int, name: str,
                     project_path: Path, test_cmds: list) -> dict:
        """Try to fix a broken project (up to 3 attempts)."""
        for attempt in range(1, 4):
            self.db.increment_fix_attempts(project_id)
            self.db.update_project_status(project_id, f"fix_attempt_{attempt}")
            self.log.info(f"Fix attempt {attempt}/3 for {name}")

            # Gather error info
            errors = []
            for cmd in test_cmds:
                proc = subprocess.run(
                    cmd, shell=True, cwd=str(project_path),
                    capture_output=True, text=True, timeout=120,
                )
                if proc.returncode != 0:
                    errors.append(f"Command: {cmd}\nError: {proc.stderr[:1000]}")

            # Gather source files
            source_files = []
            for f in project_path.rglob("*.py"):
                try:
                    source_files.append({
                        "path": str(f.relative_to(project_path)),
                        "content": f.read_text(encoding="utf-8")[:2000],
                    })
                except Exception:
                    pass

            prompt = f"""Fix this project. Errors:
{chr(10).join(errors)}

Source files:
{json.dumps(source_files[:10], indent=2)}"""

            fix = self.ask_json(prompt, system=FIX_SYSTEM, max_tokens=4000)
            if fix and "files" in fix:
                for f in fix["files"]:
                    fp = project_path / f["path"]
                    fp.parent.mkdir(parents=True, exist_ok=True)
                    fp.write_text(f["content"], encoding="utf-8")

                if self._run_tests(project_path, test_cmds):
                    self.db.update_project_status(project_id, "complete")
                    notify_project_complete(name)
                    return {
                        "success": True,
                        "result": f"Fixed on attempt {attempt}",
                        "project_id": project_id,
                    }

        # All attempts failed → escalate
        self.db.update_project_status(project_id, "escalated")
        self.log.error(f"Project {name} failed after 3 fix attempts, escalating")
        return {
            "success": False,
            "result": "Failed after 3 fix attempts, escalated to DevOps",
            "project_id": project_id,
        }
