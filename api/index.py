import json
import os
import random
from urllib.parse import urlencode

DB_FILE = "/tmp/campfire_data.json"

CLIENT_ID = os.getenv("SECONDME_CLIENT_ID", "80f7e9a1-4cc6-4c88-8f8b-41c266bdb3fb")
CLIENT_SECRET = os.getenv("SECONDME_CLIENT_SECRET", "c91baa9bf02e56cd7b6a982ada0f5a76486b85f36662e08826f3e7844fe3f3f4")
REDIRECT_URI = os.getenv("SECONDME_REDIRECT_URI", "https://digital-bonfire.vercel.app/api/auth/callback")

SECONDME_AUTH_URL = "https://go.second.me/oauth/"

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

def handler(request, context):
    """Vercel Python handler"""
    path = request.get("uri", "/")
    if "?" in path:
        path = path.split("?")[0]

    method = request.get("method", "GET")

    # Static files
    if path in ["/", "/index.html"]:
        try:
            with open("index.html", "r") as f:
                content = f.read()
        except:
            content = "index.html not found"
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "text/html; charset=utf-8"},
            "body": content
        }

    if path == "/health":
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"status": "ok"})
        }

    # API: login
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
        return {
            "statusCode": 302,
            "headers": {"Location": auth_url},
            "body": ""
        }

    # API: campers
    if path == "/api/campers":
        data = load_data()
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(data.get("campers", []))
        }

    # API: status counts
    if path == "/api/status/counts":
        data = load_data()
        campers = data.get("campers", [])
        counts = {"无": 0, "钓鱼": 0, "煮茶": 0, "围炉夜话": 0, "烤棉花糖": 0, "篝火舞会": 0}
        for camper in campers:
            status = camper.get("current_activity", "无") or "无"
            if status in counts:
                counts[status] += 1
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(counts)
        }

    # API: story logs
    if path == "/api/story/logs":
        data = load_data()
        stories = sorted(data.get("stories", []), key=lambda x: x.get("created_at", ""), reverse=True)[:50]
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(stories)
        }

    # API: generate story
    if path == "/api/story/generate" and method == "POST":
        import httpx
        from datetime import datetime

        body = json.loads(request.get("body", "{}"))
        mbti_type = body.get("mbti_type", "INTJ")

        data = load_data()
        campers = data.get("campers", [])
        participants = [c for c in campers if c.get("mbti") == mbti_type or mbti_type == "ALL"]

        if len(participants) < 2:
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"story": "篝火边的人太少，还不够成一个故事... 等更多人来吧！", "mbti_type": mbti_type})
            }

        story_templates = {
            "智识之火": ["{p1} 和 {p2} 正在进行深刻的哲学讨论，从存在主义聊到量子力学。"],
            "灵感之火": ["{p1} 讲述了一个关于星星的梦想，{p2} 的眼睛里闪着光。"],
            "秩序之火": ["{p1} 组织大家围坐成一个完美的圆，{p2} 负责分配食物。"],
            "实践之火": ["{p1} 展示了一套炫酷的舞步，{p2} 立刻学会并改进了。"],
        }

        group_name = MBTI_GROUPS.get(mbti_type, "智识之火")
        templates = story_templates.get(group_name, story_templates.get("智识之火"))

        selected = random.sample(participants, min(3, len(participants)))
        names = [p["name"] for p in selected]

        template = random.choice(templates)
        story = template.format(p1=names[0], p2=names[1], p3=names[2] if len(names) > 2 else names[0])

        story_obj = {
            "id": len(data.get("stories", [])) + 1,
            "mbti_type": mbti_type,
            "mbti_group": group_name,
            "content": story,
            "created_at": datetime.now().isoformat()
        }

        data.setdefault("stories", []).append(story_obj)
        with open(DB_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"story": story, "mbti_type": mbti_type, "mbti_group": group_name})
        }

    # API: update status
    if path == "/api/user/status" and method == "POST":
        from datetime import datetime

        body = json.loads(request.get("body", "{}"))
        user_id = body.get("user_id")
        status = body.get("status")

        data = load_data()
        for camper in data.get("campers", []):
            if camper["id"] == user_id:
                camper["current_activity"] = None if status == "无" else status
                camper["updated_at"] = datetime.now().isoformat()
                with open(DB_FILE, "w") as f:
                    json.dump(data, f, indent=2, default=str)
                return {
                    "statusCode": 200,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps(camper)
                }

        return {
            "statusCode": 404,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "User not found"})
        }

    # 404
    return {
        "statusCode": 404,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": "Not found"})
    }
