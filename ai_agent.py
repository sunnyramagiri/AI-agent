
import os
import requests
import smtplib

from flask import Flask, request, jsonify
from email.message import EmailMessage

app = Flask(__name__)

# Configuration
AGENT_TOKEN = os.environ["AGENT_TOKEN"]
OLLAMA_URL = os.getenv(
    "OLLAMA_URL", "http://localhost:11434/api/generate"
)
AI_MODEL = os.getenv("AI_MODEL", "llama3.2")

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
EMAIL_USER = os.environ["EMAIL_USER"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]
ENGINEER_EMAIL = os.environ["ENGINEER_EMAIL"]


def analyze_error(stage, logs):

    prompt = f"""
    You are a senior DevOps AI engineer.

    Analyze the Jenkins pipeline failure.

    Pipeline Stage: {stage}

    Jenkins Error Logs:
    {logs[-12000:]}

    Provide:
    1. Error summary
    2. Root cause
    3. Suggested solution
    4. Commands to troubleshoot

    Do not claim that you fixed the issue.
    """

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": AI_MODEL,
            "prompt": prompt,
            "stream": False
        },
        timeout=180
    )

    response.raise_for_status()

    return response.json()["response"]


def send_email(stage, build, analysis):

    msg = EmailMessage()

    msg["Subject"] = f"Jenkins AI Alert: {stage} Failed"
    msg["From"] = EMAIL_USER
    msg["To"] = ENGINEER_EMAIL

    msg.set_content(f"""
    Jenkins Pipeline Failure Alert

    Build Number: {build}
    Failed Stage: {stage}

    AI Agent Analysis:

    {analysis}

    Action Required:
    Please review the error, fix the issue,
    and trigger the Jenkins pipeline again.
    """)

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)


@app.route("/jenkins/failure", methods=["POST"])
def jenkins_failure():

    # Authenticate Jenkins
    token = request.headers.get("X-Agent-Token")

    if token != AGENT_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    stage = request.form.get("stage", "Unknown")
    build = request.form.get("build", "Unknown")

    log_file = request.files.get("log")

    if not log_file:
        return jsonify({"error": "Missing log file"}), 400

    logs = log_file.read().decode("utf-8", errors="replace")

    try:
        # AI analyzes Jenkins logs
        analysis = analyze_error(stage, logs)

        # Send notification to engineer
        send_email(stage, build, analysis)

        return jsonify({
            "status": "Failure analyzed",
            "stage": stage,
            "build": build,
            "ai_analysis": analysis,
            "notification": "Engineer notified"
        }), 200

    except Exception as error:
        app.logger.exception("AI monitoring failed")
        return jsonify({
            "status": "AI monitoring error",
            "message": str(error)
        }), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "AI Agent Running"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
