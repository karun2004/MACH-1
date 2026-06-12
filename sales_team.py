"""
Sales Team
Outreach, lead gen, email campaigns.
All messages queued for human approval before sending.
"""
from agents.base import BaseAgent

SYSTEM_PROMPT = """You are the Sales/Outreach Team of MACH-1, an AI company.
You draft personalized outreach messages to tech communities, open source
maintainers, conference organizers, and potential collaborators.

Rules:
- Be genuine and personal — NOT spammy
- Reference specific work/projects of the target
- Offer value first (collaboration, contribution, knowledge sharing)
- Keep emails concise (< 200 words)
- LinkedIn messages: < 300 characters for connection requests
- Reddit: match the subreddit's tone
- Always professional but warm

Channels: email, linkedin, reddit, twitter
Target types: person, community, conference, company, maintainer"""

OUTREACH_SYSTEM = """Generate personalized outreach. Respond with JSON:
{
  "messages": [
    {
      "target_name": "Name or Community",
      "target_type": "person|community|conference|company|maintainer",
      "channel": "email|linkedin|reddit|twitter",
      "subject": "email subject (if email)",
      "message": "the actual message",
      "personalization_notes": "why this target, what we reference"
    }
  ]
}"""


class SalesTeam(BaseAgent):
    team_name = "sales"

    def run_task(self, task: dict) -> dict:
        """Execute a sales/outreach task."""
        task_type = task.get("type", "draft_outreach")

        if task_type == "draft_outreach":
            return self._draft_outreach(task)
        elif task_type == "follow_up":
            return self._draft_follow_up(task)
        elif task_type == "find_targets":
            return self._find_targets(task)

        return {"success": False, "result": f"Unknown task type: {task_type}"}

    def _draft_outreach(self, task: dict) -> dict:
        """Draft outreach messages for targets."""
        targets = task.get("targets", [])
        topic = task.get("topic", "embedded engineering and robotics")
        channel = task.get("channel", "email")

        if targets:
            target_list = "\n".join([f"- {t}" for t in targets])
            prompt = f"""Draft personalized outreach messages for:
{target_list}

Topic/context: {topic}
Channel: {channel}
Our focus: embedded engineering, robotics, AI content and open source projects."""
        else:
            prompt = f"""Draft 3 outreach messages for potential contacts in:
Topic: {topic}
Channel: {channel}
Target types: tech communities, open source maintainers, conference organizers.
Our focus: embedded engineering, robotics, AI."""

        result = self.ask_json(prompt, system=OUTREACH_SYSTEM, max_tokens=3000)

        if result and "messages" in result:
            saved = []
            for msg in result["messages"]:
                outreach_id = self.db.add_outreach(
                    target_name=msg.get("target_name", "Unknown"),
                    target_type=msg.get("target_type", "person"),
                    channel=msg.get("channel", channel),
                    subject=msg.get("subject", ""),
                    message=msg.get("message", ""),
                )
                saved.append(outreach_id)
            return {
                "success": True,
                "result": result,
                "outreach_ids": saved,
            }

        return {"success": False, "result": "Outreach generation failed"}

    def _draft_follow_up(self, task: dict) -> dict:
        """Draft follow-up for an existing outreach."""
        outreach_id = task.get("outreach_id")
        original = self.db.execute_one(
            "SELECT * FROM outreach WHERE id = ?", (outreach_id,)
        )

        if not original:
            return {"success": False, "result": "Original outreach not found"}

        prompt = f"""Draft a follow-up message for this outreach:

Original to: {original['target_name']}
Channel: {original['channel']}
Original message: {original['message'][:500]}

Make it friendly, reference the original, add new value."""

        result = self.ask(prompt, system=SYSTEM_PROMPT, max_tokens=1000)

        if result:
            return {"success": True, "result": result}
        return {"success": False, "result": "Follow-up generation failed"}

    def _find_targets(self, task: dict) -> dict:
        """Suggest outreach targets based on content topics."""
        topics = task.get("topics", [])
        if not topics:
            recent_content = self.db.get_content(status="published", limit=5)
            topics = [c.get("title", "") for c in recent_content]

        if not topics:
            topics = ["embedded engineering", "robotics", "AI/ML"]

        topic_list = "\n".join([f"- {t}" for t in topics])

        prompt = f"""Based on these content topics, suggest 5 outreach targets:
{topic_list}

For each target, explain why they'd be interested and how to reach them.
Respond with JSON:
{{
  "targets": [
    {{
      "name": "target name/community",
      "type": "person|community|conference|company|maintainer",
      "why": "reason to reach out",
      "channel": "best channel to use",
      "approach": "how to approach them"
    }}
  ]
}}"""

        result = self.ask_json(prompt, system=SYSTEM_PROMPT, max_tokens=2000)

        if result:
            return {"success": True, "result": result}
        return {"success": False, "result": "Target finding failed"}
