"""
MACH-1 Flask Dashboard
Replaces Next.js — zero Node.js dependencies.
Pure Python + HTML/CSS/JS.
"""
import json
from datetime import datetime, timezone
from flask import Flask, render_template, request, jsonify, redirect, url_for

from config import settings
from utils.database import db
from utils.logger import get_logger
from agents.ceo import CEOAgent

log = get_logger("mach1.dashboard")

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
)
app.secret_key = settings.FLASK_SECRET_KEY

# Initialize CEO (and all sub-teams)
ceo = CEOAgent()


# ═══════════════════════════════════════════════════
#  DASHBOARD HOME
# ═══════════════════════════════════════════════════

@app.route("/")
def index():
    overview = ceo.get_overview()
    return render_template("index.html", overview=overview)


# ═══════════════════════════════════════════════════
#  PLANS
# ═══════════════════════════════════════════════════

@app.route("/plans")
def plans():
    all_plans = db.get_plans(limit=20)
    return render_template("plans.html", plans=all_plans)


@app.route("/api/plans/create", methods=["POST"])
def api_create_plan():
    plan = ceo.create_daily_plan()
    if plan:
        return jsonify({"success": True, "plan": plan})
    return jsonify({"success": False, "error": "Plan creation failed"}), 500


@app.route("/api/plans/<int:plan_id>/approve", methods=["POST"])
def api_approve_plan(plan_id):
    notes = request.json.get("notes", "") if request.is_json else ""
    db.update_plan_status(plan_id, "approved", human_notes=notes)
    return jsonify({"success": True})


@app.route("/api/plans/<int:plan_id>/reject", methods=["POST"])
def api_reject_plan(plan_id):
    notes = request.json.get("notes", "") if request.is_json else ""
    db.update_plan_status(plan_id, "rejected", human_notes=notes)
    return jsonify({"success": True})


@app.route("/api/plans/<int:plan_id>/execute", methods=["POST"])
def api_execute_plan(plan_id):
    result = ceo.execute_plan(plan_id)
    return jsonify(result)


# ═══════════════════════════════════════════════════
#  CONTENT
# ═══════════════════════════════════════════════════

@app.route("/content")
def content():
    status_filter = request.args.get("status", None)
    items = db.get_content(status=status_filter, limit=100)
    return render_template("content.html", items=items, current_status=status_filter)


@app.route("/content/<int:content_id>")
def content_detail(content_id):
    item = db.execute_one("SELECT * FROM content WHERE id = ?", (content_id,))
    if not item:
        return "Not found", 404
    return render_template("content_detail.html", item=item)


@app.route("/api/content/<int:content_id>/approve", methods=["POST"])
def api_approve_content(content_id):
    db.update_content_status(content_id, "approved")
    return jsonify({"success": True})


@app.route("/api/content/<int:content_id>/reject", methods=["POST"])
def api_reject_content(content_id):
    db.update_content_status(content_id, "rejected")
    return jsonify({"success": True})


@app.route("/api/content/<int:content_id>/publish", methods=["POST"])
def api_publish_content(content_id):
    db.update_content_status(content_id, "published")
    db.update(
        "UPDATE content SET published_at = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), content_id),
    )
    return jsonify({"success": True})


# ═══════════════════════════════════════════════════
#  TOPICS
# ═══════════════════════════════════════════════════

@app.route("/topics")
def topics():
    status_filter = request.args.get("status", None)
    items = db.get_topics(status=status_filter, limit=100)
    return render_template("topics.html", items=items, current_status=status_filter)


@app.route("/api/topics/<int:topic_id>/reject", methods=["POST"])
def api_reject_topic(topic_id):
    db.update_topic_status(topic_id, "rejected")
    return jsonify({"success": True})


@app.route("/api/topics/<int:topic_id>/select", methods=["POST"])
def api_select_topic(topic_id):
    db.update_topic_status(topic_id, "selected")
    return jsonify({"success": True})


# ═══════════════════════════════════════════════════
#  PROJECTS
# ═══════════════════════════════════════════════════

@app.route("/projects")
def projects():
    status_filter = request.args.get("status", None)
    items = db.get_projects(status=status_filter, limit=100)
    return render_template("projects.html", items=items, current_status=status_filter)


@app.route("/api/projects/<int:project_id>/push", methods=["POST"])
def api_push_project(project_id):
    project = db.execute_one("SELECT * FROM projects WHERE id = ?", (project_id,))
    if not project or not project.get("local_path"):
        return jsonify({"success": False, "error": "Project path not found"}), 404

    result = ceo.devops.run_task({
        "type": "git_push",
        "project_path": project["local_path"],
        "repo_name": project["name"],
    })
    return jsonify(result)


# ═══════════════════════════════════════════════════
#  OUTREACH
# ═══════════════════════════════════════════════════

@app.route("/outreach")
def outreach():
    status_filter = request.args.get("status", None)
    items = db.get_outreach(status=status_filter, limit=100)
    return render_template("outreach.html", items=items, current_status=status_filter)


@app.route("/api/outreach/<int:outreach_id>/approve", methods=["POST"])
def api_approve_outreach(outreach_id):
    db.update_outreach_status(outreach_id, "approved")
    return jsonify({"success": True})


@app.route("/api/outreach/<int:outreach_id>/reject", methods=["POST"])
def api_reject_outreach(outreach_id):
    db.update_outreach_status(outreach_id, "rejected")
    return jsonify({"success": True})


@app.route("/api/outreach/<int:outreach_id>/sent", methods=["POST"])
def api_mark_outreach_sent(outreach_id):
    db.update_outreach_status(outreach_id, "sent")
    db.update(
        "UPDATE outreach SET sent_at = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), outreach_id),
    )
    return jsonify({"success": True})


# ═══════════════════════════════════════════════════
#  ACTIONS (On-Demand Buttons)
# ═══════════════════════════════════════════════════

@app.route("/api/actions/scrape", methods=["POST"])
def api_scrape():
    result = ceo.run_scrape()
    return jsonify(result)


@app.route("/api/actions/rank", methods=["POST"])
def api_rank():
    result = ceo.run_rank_topics()
    return jsonify(result)


@app.route("/api/actions/openclaw", methods=["POST"])
def api_openclaw():
    data = request.json or {}
    content_type = data.get("content_type", "blog")
    count = min(int(data.get("count", 5)), 20)
    platform = data.get("platform")
    result = ceo.run_openclaw(content_type, count, platform)
    return jsonify(result)


@app.route("/api/actions/health", methods=["POST"])
def api_health_check():
    result = ceo.devops.run_task({"type": "health_check"})
    return jsonify(result)


@app.route("/api/actions/backup", methods=["POST"])
def api_backup():
    result = ceo.devops.run_task({"type": "backup"})
    return jsonify(result)


# ═══════════════════════════════════════════════════
#  API STATS
# ═══════════════════════════════════════════════════

@app.route("/api/stats")
def api_stats():
    return jsonify(db.get_dashboard_stats())


@app.route("/api/health")
def api_health():
    return jsonify(db.get_health_latest())


@app.route("/api/usage")
def api_usage():
    return jsonify(db.get_api_usage_today())


# ═══════════════════════════════════════════════════
#  PHOTO UPLOADS (cover + profile)
# ═══════════════════════════════════════════════════

import os

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


@app.route("/api/upload/cover", methods=["POST"])
def upload_cover():
    f = request.files.get("file")
    if not f:
        return jsonify({"success": False, "error": "No file"}), 400
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        return jsonify({"success": False, "error": "Bad file type"}), 400
    path = os.path.join(UPLOAD_DIR, "cover" + ext)
    # Remove old covers
    for old in os.listdir(UPLOAD_DIR):
        if old.startswith("cover."):
            os.remove(os.path.join(UPLOAD_DIR, old))
    f.save(path)
    return jsonify({"success": True, "url": f"/static/uploads/cover{ext}"})


@app.route("/api/upload/profile", methods=["POST"])
def upload_profile():
    f = request.files.get("file")
    if not f:
        return jsonify({"success": False, "error": "No file"}), 400
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        return jsonify({"success": False, "error": "Bad file type"}), 400
    path = os.path.join(UPLOAD_DIR, "profile" + ext)
    for old in os.listdir(UPLOAD_DIR):
        if old.startswith("profile."):
            os.remove(os.path.join(UPLOAD_DIR, old))
    f.save(path)
    return jsonify({"success": True, "url": f"/static/uploads/profile{ext}"})


@app.route("/api/photos")
def get_photos():
    """Return current cover and profile photo URLs."""
    cover = None
    profile = None
    if os.path.exists(UPLOAD_DIR):
        for f in os.listdir(UPLOAD_DIR):
            if f.startswith("cover."):
                cover = f"/static/uploads/{f}"
            elif f.startswith("profile."):
                profile = f"/static/uploads/{f}"
    return jsonify({"cover": cover, "profile": profile})


# ═══════════════════════════════════════════════════
#  RUN
# ═══════════════════════════════════════════════════

if __name__ == "__main__":
    log.info(f"Dashboard starting on {settings.FLASK_HOST}:{settings.FLASK_PORT}")
    app.run(
        host=settings.FLASK_HOST,
        port=settings.FLASK_PORT,
        debug=False,
    )
