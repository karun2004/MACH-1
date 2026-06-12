# ExecutiveAI-AI-leadership-and-execution-platform.
A multi-agent AI company that runs locally on your machine, featuring a CEO agent, content, coding, DevOps, marketing, and sales teams with automated task delegation and workflow management.

## What It Does

Executive AI is a **6-team AI company** managed by a CEO agent:

| Team | Job | Primary Model |
|------|-----|---------------|
| **CEO** | Creates plans, assigns tasks, monitors everything | Groq Llama 3.3 70B |
| **Content** (OpenClaw) | Blogs, social posts, video scripts | Groq → Mistral → Ollama |
| **Coding** | Builds projects from descriptions | Codestral → Groq → Ollama |
| **DevOps** | Code review, git push, health monitoring | Mistral Large → Groq |
| **Marketing** | Social strategy, engagement optimization | Groq → Mistral |
| **Sales** | Outreach drafts, lead generation | Mistral Large → Groq |

## Quick Start

```bash
# 1. Clone and setup
chmod +x setup.sh && ./setup.sh

# 2. Add your API keys
nano .env

# 3. Start
sudo systemctl start executive-ai executive-ai-dashboard

# 4. Open dashboard
firefox http://localhost:5000
