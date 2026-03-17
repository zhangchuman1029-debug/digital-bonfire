"""
Vercel Python Handler - Simple ASGI
"""
import json
import os
import random
from datetime import datetime
from urllib.parse import urlencode, parse_qs, urlparse

DB_FILE = "/tmp/campfire_data.json"

CLIENT_ID = os.getenv("SECONDME_CLIENT_ID", "80f7e9a1-4cc6-4c88-8f8b-41c266bdb3fb")
CLIENT_SECRET = os.getenv("SECONDME_CLIENT_SECRET", "c91baa9bf02e56cd7b6a982ada0f5a76486b85f36662e08826f3e7844fe3f3f4")
REDIRECT_URI = os.getenv("SECONDME_REDIRECT_URI", "https://digital-bonfire.vercel.app/api/auth/callback")

SECONDME_AUTH_URL = "https://go.second.me/oauth/"
SECONDME_TOKEN_URL = "https://api.mindverse.com/gate/lab/api/oauth/token/code"
SECONDME_PROFILE_URL = "https://api.mindverse.com/gate/lab/api/secondme/user/info"
SECONDME_SHADES_URL = "https://api.mindverse.com/gate/lab/api/secondme/user/shades"

MBTI_GROUPS = {
    "INTJ": "智识之火", "INTP": "智识之火", "ENTJ": "智识之火", "ENTP": "智识之火",
    "INFJ": "灵感之火", "INFP": "灵感之火", "ENFJ": "灵感之火", "ENFP": "灵感之火",
    "ISTJ": "秩序之火", "ISFJ": "秩序之火", "ESTJ": "秩序之火", "ESFJ": "秩序之火",
    "ISTP": "实践之火", "ISFP": "实践之火", "ESTP": "实践之火", "ESFP": "实践之火",
}

def load_data():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {"campers": [], "stories": [], "activities": []}

def save_data(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)

async def app(scope, receive, send):
    path = scope.get("path", "/")
    method = scope.get("method", "GET")

    if path == "/" or path == "/index.html":
        try:
            with open("index.html", "r") as f:
                content = f.read()
        except:
            content = "index.html not found"
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"text/html; charset=utf-8"]],
        })
        await send({"type": "http.response.body", "body": content.encode()})
        return

    if path == "/health":
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"application/json"]],
        })
        await send({"type": "http.response.body", "body": json.dumps({"status": "healthy"}).encode()})
        return

    # API routes
    if path == "/api/login":
        state = f"campfire_{random.randint(100000, 999999)}"
        params = {
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": "user.info,chat,user.info.shades,user.info.softmemory",
            "state": state,
            "force_login": "true"
        }
        auth_url = SECONDME_AUTH_URL + "?" + urlencode(params)
        await send({
            "type": "http.response.start",
            "status": 302,
            "headers": [[b"location", auth_url.encode()]],
        })
        await send({"type": "http.response.body"})
        return

    if path == "/api/campers":
        data = load_data()
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"application/json"]],
        })
        await send({"type": "http.response.body", "body": json.dumps(data.get("campers", [])).encode()})
        return

    if path == "/api/status/counts":
        data = load_data()
        campers = data.get("campers", [])
        counts = {"无": 0, "钓鱼": 0, "煮茶": 0, "围炉夜话": 0, "烤棉花糖": 0, "篝火舞会": 0}
        for camper in campers:
            status = camper.get("current_activity", "无") or "无"
            if status in counts:
                counts[status] += 1
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"application/json"]],
        })
        await send({"type": "http.response.body", "body": json.dumps(counts).encode()})
        return

    if path == "/api/story/logs":
        data = load_data()
        stories = sorted(data.get("stories", []), key=lambda x: x.get("created_at", ""), reverse=True)[:50]
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"application/json"]],
        })
        await send({"type": "http.response.body", "body": json.dumps(stories).encode()})
        return

    # Default 404
    await send({
        "type": "http.response.start",
        "status": 404,
        "headers": [[b"content-type", b"application/json"]],
    })
    await send({"type": "http.response.body", "body": json.dumps({"error": "Not found"}).encode()})
