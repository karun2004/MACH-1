"""
DevOps Team
Code review, git operations, system health monitoring.
Handles escalated projects from Coding Team.
"""
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from agents.base import BaseAgent
from config import settings
from utils.notify import notify, notify_health_report
from utils.database import db

REVIEW_SYSTEM = """You are the DevOps Team code reviewer for MACH-1.
Review code for: bugs, security issues, performance, best practices.

Respond with JSON:
{
  "score": 0-10,
  "issues": [{"severity": "high|medium|low", "file": "path", "line": N, "issue": "desc", "fix": "suggestion"}],
  "summary": "overall assessment",
  "approved": true/false
}"""

FIX_SYSTEM = """You are the DevOps Team fixer. Given a failed project
(already failed 3 coding team fix attempts), perform a deeper analysis.

Respond with JSON:
{
  "root_cause": "deep analysis",
  "files": [{"path": "file.py", "content": "complete fixed content"}],
  "additional_commands": ["any setup needed"]
}"""


class DevOpsTeam(BaseAgent):
    team_name = "devops"

    def run_task(self, task: dict) -> dict:
        """Execute a DevOps task (review, fix, deploy, health check)."""
        task_type = task.get("type", "review")

        if task_type == "review":
            return self._review_project(task)
        elif task_type == "fix_escalated":
            return self._fix_escalated(task)
        elif task_type == "git_push":
            return self._git_push(task)
        elif task_type == "health_check":
            return self._health_check()
        elif task_type == "backup":
            return self._backup()

        return {"success": False, "result": f"Unknown task type: {task_type}"}

    def _review_project(self, task: dict) -> dict:
        """Review a project's code quality."""
        project_path = task.get("project_path", "")
        if not project_path or not Path(project_path).exists():
            return {"success": False, "result": "Project path not found"}

        # Gather source files
        source_files = []
        for ext in ["*.py", "*.js", "*.ts", "*.html", "*.css"]:
            for f in Path(project_path).rglob(ext):
                try:
                    content = f.read_text(encoding="utf-8")
                    if len(content) > 3000:
                        content = content[:3000] + "\n... (truncated)"
                    source_files.append({
                        "path": str(f.relative_to(project_path)),
                        "content": content,
                    })
                except Exception:
                    pass

        if not source_files:
            return {"success": False, "result": "No source files found"}

        import json
        prompt = f"Review this project:\n{json.dumps(source_files[:15], indent=2)}"
        result = self.ask_json(prompt, system=REVIEW_SYSTEM, max_tokens=3000)

        if result:
            return {"success": True, "result": result}
        return {"success": False, "result": "Review failed"}

    def _fix_escalated(self, task: dict) -> dict:
        """Fix a project that failed 3 coding team attempts."""
        project_id = task.get("project_id")
        project_path = task.get("project_path", "")

        if not project_path or not Path(project_path).exists():
            self.db.update_project_status(project_id, "failed")
            return {"success": False, "result": "Project path not found"}

        # Gather everything
        import json
        source_files = []
        for f in Path(project_path).rglob("*.py"):
            try:
                source_files.append({
                    "path": str(f.relative_to(project_path)),
                    "content": f.read_text(encoding="utf-8")[:3000],
                })
            except Exception:
                pass

        prompt = f"""This project failed 3 fix attempts by the Coding Team.
Perform a deep analysis and fix.

Files:
{json.dumps(source_files[:15], indent=2)}

Description: {task.get('description', 'N/A')}"""

        result = self.ask_json(prompt, system=FIX_SYSTEM, max_tokens=4000)

        if result and "files" in result:
            for f in result["files"]:
                fp = Path(project_path) / f["path"]
                fp.parent.mkdir(parents=True, exist_ok=True)
                fp.write_text(f["content"], encoding="utf-8")

            self.db.update_project_status(project_id, "complete")
            return {"success": True, "result": result.get("root_cause", "Fixed")}

        self.db.update_project_status(project_id, "failed")
        from utils.notify import notify_project_failed
        notify_project_failed(task.get("name", "unknown"), "DevOps fix also failed")
        return {"success": False, "result": "DevOps fix failed"}

    def _git_push(self, task: dict) -> dict:
        """Push a project to GitHub."""
        project_path = task.get("project_path", "")
        repo_name = task.get("repo_name", "")

        if not settings.GITHUB_TOKEN or not settings.GITHUB_USERNAME:
            return {"success": False, "result": "GitHub not configured"}

        if not project_path or not Path(project_path).exists():
            return {"success": False, "result": "Project path not found"}

        try:
            pp = Path(project_path)

            # Init git if needed
            if not (pp / ".git").exists():
                subprocess.run(["git", "init"], cwd=str(pp), check=True,
                               capture_output=True)
                subprocess.run(
                    ["git", "remote", "add", "origin",
                     f"https://{settings.GITHUB_TOKEN}@github.com/{settings.GITHUB_USERNAME}/{repo_name}.git"],
                    cwd=str(pp), check=True, capture_output=True,
                )

            # Add, commit, push
            subprocess.run(["git", "add", "."], cwd=str(pp), check=True,
                           capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", f"MACH-1 auto-deploy: {repo_name}"],
                cwd=str(pp), capture_output=True,
            )
            result = subprocess.run(
                ["git", "push", "-u", "origin", "main"],
                cwd=str(pp), capture_output=True, text=True, timeout=60,
            )

            if result.returncode == 0:
                repo_url = f"https://github.com/{settings.GITHUB_USERNAME}/{repo_name}"
                self.db.update(
                    "UPDATE projects SET repo_url = ? WHERE local_path = ?",
                    (repo_url, str(pp)),
                )
                return {"success": True, "result": repo_url}
            else:
                return {"success": False, "result": result.stderr[:500]}

        except Exception as e:
            return {"success": False, "result": str(e)}

    def _health_check(self) -> dict:
        """Run system health check."""
        checks = {}

        # Disk space
        try:
            stat = shutil.disk_usage(str(settings.MACH1_HOME))
            free_gb = stat.free / (1024**3)
            checks["disk"] = {
                "status": "ok" if free_gb > 5 else ("warn" if free_gb > 1 else "error"),
                "message": f"{free_gb:.1f} GB free",
            }
            if free_gb < 1:
                notify("disk_low", "Disk Space Low", f"Only {free_gb:.1f} GB free!")
        except Exception as e:
            checks["disk"] = {"status": "error", "message": str(e)}

        # Database size
        try:
            db_size = settings.DB_PATH.stat().st_size / (1024**2)
            checks["database"] = {
                "status": "ok",
                "message": f"{db_size:.1f} MB",
            }
        except Exception as e:
            checks["database"] = {"status": "error", "message": str(e)}

        # Ollama
        try:
            import requests
            resp = requests.get(f"{settings.OLLAMA_HOST}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                checks["ollama"] = {
                    "status": "ok",
                    "message": f"Models: {', '.join(models)}",
                }
            else:
                checks["ollama"] = {"status": "warn", "message": "Responded but error"}
        except Exception:
            checks["ollama"] = {"status": "down", "message": "Not reachable"}

        # API keys configured
        for name, key in [("groq", settings.GROQ_API_KEY),
                          ("mistral", settings.MISTRAL_API_KEY),
                          ("google", settings.GOOGLE_AI_KEY)]:
            checks[f"api_{name}"] = {
                "status": "ok" if key else "warn",
                "message": "configured" if key else "NOT SET",
            }

        # Log to database
        for component, info in checks.items():
            db.log_health(component, info["status"], info["message"])

        # Build summary
        summary_lines = [f"{k}: {v['status']} ({v['message']})" for k, v in checks.items()]
        summary = "\n".join(summary_lines)
        notify_health_report(summary)

        return {"success": True, "result": checks}

    def _backup(self) -> dict:
        """Backup the database."""
        try:
            now = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_path = settings.BACKUP_DIR / f"mach1_{now}.db"
            shutil.copy2(str(settings.DB_PATH), str(backup_path))

            # Keep only last 7 backups
            backups = sorted(settings.BACKUP_DIR.glob("mach1_*.db"))
            for old in backups[:-7]:
                old.unlink()

            db.log_health("backup", "ok", f"Backed up to {backup_path.name}")
            notify("backup_done", "Backup Complete", f"Database backed up: {backup_path.name}")
            return {"success": True, "result": str(backup_path)}
        except Exception as e:
            db.log_health("backup", "error", str(e))
            return {"success": False, "result": str(e)}
