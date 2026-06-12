"""
Marketing Team
Social media strategy, engagement optimization, analytics.
"""
from agents.base import BaseAgent

SYSTEM_PROMPT = """You are the Marketing Team of MACH-1, an AI company.
You focus on social media strategy for tech/robotics/embedded engineering content.

Your capabilities:
- Create platform-specific posting strategies
- Optimize content for engagement (hashtags, timing, formatting)
- Analyze content performance and suggest improvements
- Generate social media calendars
- Adapt content across platforms (Twitter, LinkedIn, Reddit, Dev.to, etc.)

Target audience: engineers, makers, roboticists, AI enthusiasts, tech professionals.
Tone: technical but accessible, enthusiastic, community-focused.
Always output clean, actionable plans or content."""

STRATEGY_SYSTEM = """You are a social media strategist. Given content items,
create a posting plan.

Respond with JSON:
{
  "posts": [
    {
      "platform": "twitter|linkedin|reddit|devto|hashnode|medium|instagram",
      "content": "ready-to-post text",
      "hashtags": ["tag1", "tag2"],
      "best_time": "HH:MM UTC",
      "notes": "any special instructions"
    }
  ],
  "weekly_theme": "overarching theme",
  "engagement_tips": ["tip1", "tip2"]
}"""


class MarketingTeam(BaseAgent):
    team_name = "marketing"

    def run_task(self, task: dict) -> dict:
        """Execute a marketing task."""
        task_type = task.get("type", "strategy")

        if task_type == "strategy":
            return self._create_strategy(task)
        elif task_type == "optimize":
            return self._optimize_content(task)
        elif task_type == "adapt":
            return self._adapt_for_platform(task)

        return {"success": False, "result": f"Unknown task type: {task_type}"}

    def _create_strategy(self, task: dict) -> dict:
        """Create a posting strategy for content items."""
        content_items = task.get("content_items", [])
        if not content_items:
            content_items = self.db.get_content(status="approved", limit=10)

        if not content_items:
            return {"success": False, "result": "No content to strategize"}

        titles = "\n".join([f"- {c.get('title', 'Untitled')}: {c.get('content_type', 'blog')}"
                           for c in content_items])

        prompt = f"""Create a social media posting strategy for these content items:
{titles}

Target audience: embedded engineers, roboticists, AI developers.
Platforms: Twitter/X, LinkedIn, Reddit (r/robotics, r/embedded), Dev.to, Hashnode."""

        result = self.ask_json(prompt, system=STRATEGY_SYSTEM, max_tokens=3000)

        if result:
            return {"success": True, "result": result}
        return {"success": False, "result": "Strategy generation failed"}

    def _optimize_content(self, task: dict) -> dict:
        """Optimize content for better engagement."""
        content = task.get("content", "")
        platform = task.get("platform", "twitter")

        prompt = f"""Optimize this content for {platform}:

{content[:2000]}

Make it more engaging while keeping the technical accuracy.
Output the optimized version directly."""

        result = self.ask(prompt, system=SYSTEM_PROMPT, max_tokens=2000)

        if result:
            return {"success": True, "result": result}
        return {"success": False, "result": "Optimization failed"}

    def _adapt_for_platform(self, task: dict) -> dict:
        """Adapt a piece of content for a specific platform."""
        content = task.get("content", "")
        source_platform = task.get("source_platform", "blog")
        target_platform = task.get("target_platform", "twitter")

        prompt = f"""Adapt this {source_platform} content for {target_platform}:

{content[:2000]}

Follow {target_platform}'s best practices for format, length, and tone."""

        result = self.ask(prompt, system=SYSTEM_PROMPT, max_tokens=1500)

        if result:
            return {"success": True, "result": result}
        return {"success": False, "result": "Adaptation failed"}
