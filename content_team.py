"""
Content Team (OpenClaw)
Generates blogs, social posts, video scripts, etc.
Only runs on demand (dashboard button).
"""
import json
from typing import Optional
from agents.base import BaseAgent

SYSTEM_PROMPT = """You are the Content Team of MACH-1, an AI company.
You create high-quality content about technology, robotics, embedded systems,
AI/ML, and related topics.

Your output types:
- blog: 800-1500 word blog post in Markdown
- social_post: Short engaging post (< 280 chars for Twitter, longer for LinkedIn)
- video_script: 3-5 minute video script with timestamps
- tweet: Punchy tweet under 280 characters
- linkedin_post: Professional LinkedIn post (200-500 words)
- instagram_caption: Engaging caption with hashtags
- reddit_post: Informative post matching subreddit tone
- newsletter: Email newsletter section

Always output clean Markdown. Be engaging, technical but accessible.
Include relevant hashtags for social media.
Focus on embedded engineering, robotics, AI, and tech trends."""

RANK_SYSTEM = """You are a topic ranker. Score each topic from 0.0 to 10.0 based on:
- Relevance to embedded engineering, robotics, AI (weight: 3x)
- Trending/timely (weight: 2x)
- Audience engagement potential (weight: 2x)
- Uniqueness (weight: 1x)

Respond ONLY with valid JSON array: [{"id": N, "score": X.X, "reason": "brief"}]"""


class ContentTeam(BaseAgent):
    team_name = "content"

    def run_task(self, task: dict) -> dict:
        """Execute a content creation task."""
        desc = task.get("description", "")
        content_type = task.get("content_type", "blog")
        topic_id = task.get("topic_id")
        platform = task.get("platform")

        prompt = f"""Create a {content_type} about the following:
{desc}

Target platform: {platform or 'general'}
Output clean Markdown content only. No meta-commentary."""

        result = self.ask(prompt, system=SYSTEM_PROMPT, max_tokens=3000)

        if result:
            # Extract title from first line if markdown
            lines = result.strip().split("\n")
            title = lines[0].lstrip("#").strip() if lines[0].startswith("#") else desc[:100]

            content_id = self.db.add_content(
                topic_id=topic_id,
                content_type=content_type,
                title=title,
                body=result,
                platform=platform,
            )
            return {"success": True, "result": result, "content_id": content_id}

        return {"success": False, "result": "All LLM providers failed"}

    def rank_topics(self, topics: list) -> list:
        """Score a batch of topics for relevance."""
        if not topics:
            return []

        topic_list = "\n".join(
            [f"- ID {t['id']}: {t['title']}" for t in topics[:30]]
        )

        prompt = f"Rank these topics:\n{topic_list}"
        result = self.ask_json(prompt, system=RANK_SYSTEM, max_tokens=2000)

        if result and isinstance(result, list):
            for item in result:
                try:
                    self.db.update_topic_score(item["id"], float(item["score"]))
                except (KeyError, ValueError):
                    continue
            return result

        return []

    def generate_batch(self, topics: list, content_type: str = "blog",
                       platform: str = None) -> list:
        """Generate content for multiple topics."""
        results = []
        for topic in topics:
            task = {
                "description": topic.get("title", ""),
                "content_type": content_type,
                "topic_id": topic.get("id"),
                "platform": platform,
            }
            result = self.run_task(task)
            results.append(result)
            self.log.info(
                f"Generated {content_type} for topic {topic.get('id')}: "
                f"{'✓' if result['success'] else '✗'}"
            )
        return results
