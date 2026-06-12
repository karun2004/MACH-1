"""
CEO Agent — The Master Controller
ONE agent that spawns/controls the other 5 teams.
Creates plans, assigns tasks, monitors outputs, adjusts strategy.
"""
import json
from datetime import datetime, timezone
from typing import Optional

from agents.base import BaseAgent
from agents.content_team import ContentTeam
from agents.coding_team import CodingTeam
from agents.devops_team import DevOpsTeam
from agents.marketing_team import MarketingTeam
from agents.sales_team import SalesTeam
from agents.rss_scraper import scrape_all, init_default_sources
from utils.notify import notify_plan_proposed
from utils.database import db

SYSTEM_PROMPT = """You are the CEO of MACH-1, an AI-powered company focused on
embedded engineering, robotics, and AI content creation.

You manage 5 teams:
1. CONTENT (OpenClaw) — blogs, social posts, video scripts
2. CODING — builds projects from descriptions
3. DEVOPS — code review, git, deployment, system health
4. MARKETING — social media strategy, engagement
5. SALES — outreach, lead gen, email campaigns

Your role:
- Analyze available topics and decide what content to create
- Decide which projects to build
- Plan outreach strategy
- Assign tasks to teams with clear descriptions
- Monitor team outputs and adjust strategy
- Create daily/weekly plans for human approval

Always output structured plans as JSON when asked for plans.
Be strategic and data-driven. Prioritize high-impact activities."""

PLAN_SYSTEM = """Create a daily plan. Respond ONLY with JSON:
{
  "summary": "one-line summary",
  "content_tasks": [
    {"description": "what to write", "content_type": "TYPE", "topic_id": N, "platform": "target"}
  ],
  "coding_tasks": [
    {"name": "project-name", "description": "what to build", "template": "TEMPLATE"}
  ],
  "marketing_tasks": [
    {"type": "strategy|optimize|adapt", "description": "what to do"}
  ],
  "sales_tasks": [
    {"type": "draft_outreach|find_targets", "description": "what to do", "channel": "email|linkedin|reddit"}
  ],
  "devops_tasks": [
    {"type": "review|health_check|backup", "description": "what to do"}
  ],
  "reasoning": "why this plan makes sense today"
}

CRITICAL — use ONLY these exact values:
content_type must be one of: blog, social_post, video_script, tweet, linkedin_post, instagram_caption, reddit_post, newsletter
template must be one of: ros2-node, flask-api, nextjs-app, ml-pipeline, arduino-esp32, data-analysis, cli-tool, fullstack, physics-sim, circuit-design
Do NOT invent new types or templates."""


class CEOAgent(BaseAgent):
    team_name = "ceo"

    def __init__(self):
        super().__init__()
        # Initialize all teams
        self.content = ContentTeam()
        self.coding = CodingTeam()
        self.devops = DevOpsTeam()
        self.marketing = MarketingTeam()
        self.sales = SalesTeam()
        self.teams = {
            "content": self.content,
            "coding": self.coding,
            "devops": self.devops,
            "marketing": self.marketing,
            "sales": self.sales,
        }

    def run_task(self, task: dict) -> dict:
        """CEO doesn't receive tasks — it creates them."""
        return {"success": True, "result": "CEO creates tasks, not receives them"}

    # ── Plan Creation ────────────────────────────────

    def create_daily_plan(self) -> Optional[dict]:
        """Analyze current state and create a daily plan."""
        # Auto-scrape fresh topics every time
        self.log.info("Scraping fresh topics before planning...")
        scrape_all()

        # Auto-rank any new unranked topics
        new_topics = db.get_topics(status="new", limit=30)
        if new_topics:
            self.log.info(f"Ranking {len(new_topics)} new topics...")
            self.content.rank_topics(new_topics)

        stats = db.get_dashboard_stats()

        # Only get topics NOT already used or rejected
        topics = db.get_topics(status="ranked", limit=20)
        if not topics:
            topics = db.get_topics(status="new", limit=20)

        # Gather what was already created (so CEO doesn't repeat)
        recent_content = db.get_content(limit=20)
        recent_titles = [c.get("title", "") for c in recent_content]
        already_done = "\n".join([f"  - {t[:80]}" for t in recent_titles[:10]]) if recent_titles else "  (none yet)"

        recent_projects = db.get_projects(limit=10)
        done_projects = "\n".join([f"  - {p.get('name', '')}" for p in recent_projects[:5]]) if recent_projects else "  (none yet)"

        # Build context for the CEO
        context = f"""Current state:
- Topics available: {sum(stats.get('topics', {}).values())} total, {len(topics)} unused ranked/new
- Content: {json.dumps(stats.get('content', {}))}
- Projects: {json.dumps(stats.get('projects', {}))}
- Outreach: {json.dumps(stats.get('outreach', {}))}

ALREADY CREATED (do NOT repeat these):
Content:
{already_done}
Projects:
{done_projects}

FRESH topics to choose from (pick DIFFERENT ones than above):
{chr(10).join([f"- [ID {t['id']}] {t['title']} (score: {t.get('score', 0)})" for t in topics[:15]])}

Create today's plan using NEW topics only. Be specific. Reference topic IDs."""

        result = self.ask_json(context, system=PLAN_SYSTEM, max_tokens=3000)

        if result:
            plan_id = db.add_plan(
                plan_type="daily",
                summary=result.get("summary", "Daily plan"),
                details=json.dumps(result),
            )
            result["plan_id"] = plan_id
            notify_plan_proposed(result.get("summary", "New daily plan"))
            self.log.info(f"Daily plan created: {result.get('summary')}")
            return result

        self.log.error("Failed to create daily plan")
        return None

    # ── Plan Execution ───────────────────────────────

    def execute_plan(self, plan_id: int) -> dict:
        """Execute an approved plan by assigning tasks to teams."""
        plan = db.execute_one("SELECT * FROM ceo_plans WHERE id = ?", (plan_id,))
        if not plan:
            return {"success": False, "result": "Plan not found"}

        if plan["status"] not in ("approved", "modified"):
            return {"success": False, "result": f"Plan status is '{plan['status']}', needs 'approved'"}

        db.update_plan_status(plan_id, "in_progress")
        details = json.loads(plan["details"])
        results = {"plan_id": plan_id, "tasks": {}}

        # Map of team_name → (task_key, team_instance)
        team_dispatch = [
            ("content_tasks", "content", self.content),
            ("coding_tasks", "coding", self.coding),
            ("marketing_tasks", "marketing", self.marketing),
            ("sales_tasks", "sales", self.sales),
            ("devops_tasks", "devops", self.devops),
        ]

        for task_key, team_name, team_instance in team_dispatch:
            for task in details.get(task_key, []):
                task_id = None
                try:
                    # Sanitize before execution
                    task = self._sanitize_task(task, team_name)
                    task_id = db.add_task(team_name, task.get("description", ""), plan_id)
                    db.update_task(task_id, "running")

                    self.log.info(f"Executing {team_name} task: {task.get('description', '')[:60]}")
                    result = team_instance.run_task(task)

                    status = "completed" if result.get("success") else "failed"
                    db.update_task(task_id, status,
                                   result=str(result.get("result", ""))[:1000])
                    results["tasks"].setdefault(team_name, []).append(result)
                    self.log.info(f"  → {team_name} task: {status}")

                except Exception as e:
                    self.log.error(f"  → {team_name} task CRASHED: {e}")
                    if task_id:
                        db.update_task(task_id, "failed", result=str(e)[:1000])
                    results["tasks"].setdefault(team_name, []).append(
                        {"success": False, "result": f"Crashed: {e}"}
                    )

        db.update_plan_status(plan_id, "completed")

        # Mark all referenced topic IDs as "used" so next plan picks fresh ones
        for task in details.get("content_tasks", []):
            tid = task.get("topic_id")
            if tid:
                try:
                    db.update_topic_status(int(tid), "used")
                except Exception:
                    pass

        self.log.info(f"Plan {plan_id} execution complete")
        return {"success": True, "result": results}

    @staticmethod
    def _sanitize_task(task: dict, team: str) -> dict:
        """Fix invalid values from CEO hallucinations before execution."""
        VALID_CONTENT_TYPES = {
            'blog', 'social_post', 'video_script', 'tweet', 'linkedin_post',
            'instagram_caption', 'reddit_post', 'newsletter'
        }
        VALID_TEMPLATES = {
            'ros2-node', 'flask-api', 'nextjs-app', 'ml-pipeline', 'arduino-esp32',
            'data-analysis', 'cli-tool', 'fullstack', 'physics-sim', 'circuit-design'
        }

        if team == "content":
            ct = task.get("content_type", "blog")
            if ct not in VALID_CONTENT_TYPES:
                # Map common hallucinations
                mapping = {
                    'tutorial': 'blog', 'article': 'blog', 'post': 'blog',
                    'thread': 'tweet', 'reel': 'instagram_caption',
                    'email': 'newsletter', 'youtube': 'video_script',
                }
                task["content_type"] = mapping.get(ct, "blog")

        if team == "coding":
            tmpl = task.get("template", "flask-api")
            if tmpl not in VALID_TEMPLATES:
                # Pick closest match or default
                task["template"] = "flask-api"

        return task

    # ── On-Demand Operations ─────────────────────────

    def run_openclaw(self, content_type: str = "blog", count: int = 5,
                     platform: str = None) -> dict:
        """Run OpenClaw content generation on demand."""
        # Get top ranked topics
        topics = db.get_topics(status="ranked", limit=count)
        if not topics:
            # Try scraping first
            scrape_all()
            topics = db.get_topics(status="new", limit=count * 2)
            if topics:
                self.content.rank_topics(topics)
                topics = db.get_topics(status="ranked", limit=count)

        if not topics:
            return {"success": False, "result": "No topics available"}

        results = self.content.generate_batch(topics, content_type, platform)
        successes = sum(1 for r in results if r["success"])

        # Mark topics as used
        for topic in topics:
            db.update_topic_status(topic["id"], "used")

        return {
            "success": successes > 0,
            "result": f"Generated {successes}/{len(topics)} {content_type} items",
            "details": results,
        }

    def run_scrape(self) -> dict:
        """Scrape RSS feeds for new topics."""
        init_default_sources()
        count = scrape_all()
        return {"success": True, "result": f"Scraped {count} new topics"}

    def run_rank_topics(self) -> dict:
        """Rank unranked topics."""
        topics = db.get_topics(status="new", limit=30)
        if not topics:
            return {"success": False, "result": "No new topics to rank"}
        ranked = self.content.rank_topics(topics)
        return {"success": True, "result": f"Ranked {len(ranked)} topics"}

    def get_overview(self) -> dict:
        """Get a full system overview for the dashboard."""
        stats = db.get_dashboard_stats()
        team_status = {}
        for name, team in self.teams.items():
            team_status[name] = team.get_status()

        from utils.router import rate_limiter
        return {
            "stats": stats,
            "teams": team_status,
            "api_usage": rate_limiter.get_usage(),
        }
