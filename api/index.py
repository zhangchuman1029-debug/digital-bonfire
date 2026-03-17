"""
Vercel Python Handler for Digital Bonfire
"""
import os
import json
import random
from datetime import datetime
from urllib.parse import urlencode, parse_qs, urlparse
import httpx

# ================== 配置 ==================
CLIENT_ID = os.getenv("SECONDME_CLIENT_ID", "80f7e9a1-4cc6-4c88-8f8b-41c266bdb3fb")
CLIENT_SECRET = os.getenv("SECONDME_CLIENT_SECRET", "c91baa9bf02e56cd7b6a982ada0f5a76486b85f36662e08826f3e7844fe3f3f4")

SECONDME_AUTH_URL = "https://go.second.me/oauth/"
SECONDME_TOKEN_URL = "https://api.mindverse.com/gate/lab/api/oauth/token/code"
SECONDME_PROFILE_URL = "https://api.mindverse.com/gate/lab/api/secondme/user/info"
SECONDME_SHADES_URL = "https://api.mindverse.com/gate/lab/api/secondme/user/shades"

DB_FILE = "/tmp/campfire_data.json"

# ================== 常量 ==================
ACTIVITIES = {
    "钓鱼": {"emoji": "🎣", "description": "静心垂钓", "mbti": ["INTJ", "INTP", "ISTP", "ISFP"]},
    "煮茶": {"emoji": "🍵", "description": "品茶论道", "mbti": ["INFJ", "INFP", "ENFJ", "ENFP"]},
    "围炉夜话": {"emoji": "💬", "description": "畅所欲言", "mbti": ["ENTJ", "ENTP", "ESTJ", "ESFJ"]},
    "烤棉花糖": {"emoji": "🍡", "description": "甜蜜时光", "mbti": ["ESFP", "ISFJ", "ISTJ", "ESTP"]},
    "篝火舞会": {"emoji": "💃", "description": "尽情起舞", "mbti": ["ALL"]},
}

MBTI_GROUPS = {
    "INTJ": "智识之火", "INTP": "智识之火", "ENTJ": "智识之火", "ENTP": "智识之火",
    "INFJ": "灵感之火", "INFP": "灵感之火", "ENFJ": "灵感之火", "ENFP": "灵感之火",
    "ISTJ": "秩序之火", "ISFJ": "秩序之火", "ESTJ": "秩序之火", "ESFJ": "秩序之火",
    "ISTP": "实践之火", "ISFP": "实践之火", "ESTP": "实践之火", "ESFP": "实践之火",
}

# ================== 数据存储 ==================
def load_data():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {"campers": [], "messages": [], "activities": [], "stories": [], "mbti_groups": {}}

def save_data(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)

def infer_mbti(shades):
    if not shades:
        return random.choice(list(MBTI_GROUPS.keys()))
    shades_str = " ".join(shades).lower()
    if any(w in shades_str for w in ['理性', '逻辑', '分析', '独立', '思考']):
        if any(w in shades_str for w in ['内向', '安静', '独处']):
            return "INTJ" if random.random() > 0.5 else "INTP"
        else:
            return "ENTJ" if random.random() > 0.5 else "ENTP"
    if any(w in shades_str for w in ['情感', '感受', '共情', '温暖']):
        if any(w in shades_str for w in ['内向', '安静', '独处']):
            return "INFJ" if random.random() > 0.5 else "INFP"
        else:
            return "ENFJ" if random.random() > 0.5 else "ENFP"
    if any(w in shades_str for w in ['实际', '现实', '务实', '动手']):
        if any(w in shades_str for w in ['内向', '安静']):
            return "ISTJ" if random.random() > 0.5 else "ISTP"
        else:
            return "ESTJ" if random.random() > 0.5 else "ESTP"
    if any(w in shades_str for w in ['传统', '稳定', '可靠', '忠诚']):
        if any(w in shades_str for w in ['内向', '安静']):
            return "ISFJ"
        else:
            return "ESFJ"
    if any(w in shades_str for w in ['自由', '灵活', '创意', '热情']):
        if any(w in shades_str for w in ['内向', '安静']):
            return "ISFP"
        else:
            return "ESFP"
    return random.choice(list(MBTI_GROUPS.keys()))

# ================== HTTP 响应 ==================
def json_response(data, status=200):
    return {
        "statusCode": status,
        "headers": { "Content-Type": "application/json" },
        "body": json.dumps(data, ensure_ascii=False)
    }

def redirect(url, status=302):
    return {
        "statusCode": status,
        "headers": { "Location": url }
    }

def html_response(body, status=200):
    return {
        "statusCode": status,
        "headers": { "Content-Type": "text/html; charset=utf-8" },
        "body": body
    }

# ================== 路由处理 ==================
def get_path(request):
    parsed = urlparse(request.get("uri", "/"))
    return parsed.path

def get_query(request):
    parsed = urlparse(request.get("uri", "/"))
    return parse_qs(parsed.query)

async def handle_api_login(request):
    state = f"campfire_{random.randint(100000, 999999)}"
    redirect_uri = os.getenv("SECONDME_REDIRECT_URI", "https://digital-bonfire.vercel.app/api/auth/callback")
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "user.info,chat,user.info.shades,user.info.softmemory,note.add",
        "state": state,
        "force_login": "true"
    }
    auth_url = SECONDME_AUTH_URL + "?" + urlencode(params)
    with open("/tmp/auth_state", "w") as f:
        f.write(state)
    return redirect(auth_url)

async def handle_callback(request):
    query = get_query(request)
    code = query.get("code", [None])[0]
    state = query.get("state", [None])[0]

    if not code:
        return json_response({"error": "No code provided"}, 400)

    redirect_uri = os.getenv("SECONDME_REDIRECT_URI", "https://digital-bonfire.vercel.app/api/auth/callback")

    try:
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                SECONDME_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0
            )

            token_data = token_resp.json()
            if token_data.get("code") != 0:
                return json_response({"error": token_data.get("message")}, 400)

            access_token = token_data.get("data", {}).get("accessToken")
            if not access_token:
                return json_response({"error": "No access token"}, 400)

            profile_resp = await client.get(SECONDME_PROFILE_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=15.0)
            shades_resp = await client.get(SECONDME_SHADES_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=15.0)

    except Exception as e:
        return json_response({"error": str(e)}, 500)

    profile = profile_resp.json()
    user_info = profile.get("data", profile)
    name = user_info.get("name", user_info.get("username", "Anonymous"))

    shades = []
    try:
        shades_data = shades_resp.json()
        shades_obj = shades_data.get("data", {})
        if isinstance(shades_obj, dict):
            shades = shades_obj.get("shades", shades_obj.get("tags", []))
        elif isinstance(shades_obj, list):
            shades = shades_obj
    except:
        pass

    mbti = infer_mbti(shades)

    keywords_logic = ['python', 'code', 'dev', '后端', 'algorithm', 'logic', 'ai', 'ml', 'data', '技术', '编程']
    keywords_creative = ['design', 'art', 'creative', 'music', '画', '创意', '设计', '艺术', '绘画']
    shades_lower = [s.lower() for s in shades]
    is_logic = any(any(kw in s for kw in keywords_logic) for s in shades_lower)
    is_creative = any(any(kw in s for kw in keywords_creative) for s in shades_lower)

    if is_logic and not is_creative:
        distance, color = 130, "#00d4ff"
    elif is_creative and not is_logic:
        distance, color = 85, "#ff6b35"
    else:
        distance, color = 110, "#a855f7"

    data = load_data()
    existing = [c for c in data.get("campers", []) if c.get("name", "").upper() == name.upper()]

    if existing:
        camper = existing[0]
        camper["distance"] = distance
        camper["color"] = color
        camper["shades"] = shades
        camper["mbti"] = mbti
        camper["mbti_group"] = MBTI_GROUPS.get(mbti, "misc")
        camper["updated_at"] = datetime.now().isoformat()
    else:
        camper = {
            "id": len(data.get("campers", [])) + 1,
            "name": name.upper(),
            "intro": "通过 SecondMe 登录",
            "distance": distance,
            "angle": random.uniform(0, 360),
            "color": color,
            "shades": shades,
            "mbti": mbti,
            "mbti_group": MBTI_GROUPS.get(mbti, "misc"),
            "current_activity": None,
            "joined_at": datetime.now().isoformat()
        }
        data.setdefault("campers", []).append(camper)

    save_data(data)

    base_url = redirect_uri.replace("/api/auth/callback", "")
    return redirect(f"{base_url}?joined=true")

async def handle_campers(request):
    data = load_data()
    return json_response(data.get("campers", []))

async def handle_status_counts(request):
    data = load_data()
    campers = data.get("campers", [])
    counts = {"无": 0}
    for act in ACTIVITIES.keys():
        counts[act] = 0
    for camper in campers:
        status = camper.get("current_activity", "无") or "无"
        if status in counts:
            counts[status] += 1
        else:
            counts["无"] += 1
    return json_response(counts)

async def handle_update_status(request):
    body = json.loads(request.get("body", "{}"))
    user_id = body.get("user_id")
    status = body.get("status")

    data = load_data()
    campers = data.get("campers", [])

    for camper in campers:
        if camper["id"] == user_id:
            camper["current_activity"] = None if status == "无" else status
            camper["updated_at"] = datetime.now().isoformat()
            save_data(data)
            return json_response(camper)

    return json_response({"error": "User not found"}, 404)

async def handle_story_logs(request):
    data = load_data()
    stories = data.get("stories", [])
    stories = sorted(stories, key=lambda x: x.get("created_at", ""), reverse=True)[:50]
    return json_response(stories)

async def handle_generate_story(request):
    body = json.loads(request.get("body", "{}"))
    mbti_type = body.get("mbti_type", "INTJ")
    target_user_id = body.get("target_user_id")

    data = load_data()
    campers = data.get("campers", [])
    activities = data.get("activities", [])

    participants = [c for c in campers if c.get("mbti") == mbti_type or mbti_type == "ALL"]

    if len(participants) < 2:
        return json_response({"story": "篝火边的人太少，还不够成一个故事... 等更多人来吧！", "mbti_type": mbti_type})

    current_activity = None
    for activity in activities:
        if activity["name"] in ["围炉夜话", "篝火舞会"] or not activity.get("participants"):
            current_activity = activity
            break

    story_templates = {
        "智识之火": [
            "{p1} 和 {p2} 正在进行深刻的哲学讨论，从存在主义聊到量子力学，{p3} 偶尔插几句嘴，气氛十分热烈。",
            "围绕篝火，{p1} 提出了一个关于宇宙本质的问题，{p2} 和 {p3} 陷入了沉思...",
            "{p1} 分享了一个有趣的逻辑悖论，{p2} 立刻给出了解决方案，{p3} 则提出了另一种思考角度。",
        ],
        "灵感之火": [
            "{p1} 讲述了一个关于星星的梦想，{p2} 的眼睛里闪着光，{p3} 轻声说：'我们可以一起实现它'。",
            "在温暖的火光中，{p1} 突然灵感爆发，画出了一幅美丽的画，{p2} 和 {p3} 成了第一批观众。",
            "{p1} 和 {p2} 合唱了一首歌，{p3} 打着节拍，歌声在夜空中回荡。",
        ],
        "秩序之火": [
            "{p1} 组织大家围坐成一个完美的圆，{p2} 负责分配食物，{p3} 负责记录这美好的时刻。",
            "在 {p1} 的提议下，大家制定了今晚的守则：{p2} 负责添柴，{p3} 负责讲笑话。",
            "{p1} 讲解着篝火的正确生法，{p2} 认真学习，{p3} 已经迫不及待想烤棉花糖了。",
        ],
        "实践之火": [
            "{p1} 展示了一套炫酷的舞步，{p2} 立刻学会并改进了，{p3} 笑得合不拢嘴。",
            "{p1} 钓到了一条大鱼！{p2} 帮忙处理，{p3} 生起了火，准备烤鱼大餐。",
            "{p1} 和 {p2} 比赛谁先把火生起来，{p3} 当裁判，笑声不断。",
        ],
    }

    group_name = MBTI_GROUPS.get(mbti_type, "misc")
    templates = story_templates.get(group_name, story_templates.get("智识之火"))

    selected = random.sample(participants, min(3, len(participants)))
    names = [p["name"] for p in selected]

    template = random.choice(templates)
    story = template.format(p1=names[0], p2=names[1], p3=names[2] if len(names) > 2 else names[0])

    if current_activity:
        story = f"大家正在一起{current_activity['name']}，" + story

    target_user = None
    if target_user_id:
        for c in campers:
            if c["id"] == target_user_id:
                target_user = c
                break

    story_obj = {
        "id": len(data.get("stories", [])) + 1,
        "mbti_type": mbti_type,
        "mbti_group": group_name,
        "content": story,
        "participants": [p["id"] for p in selected],
        "participant_names": [p["name"] for p in selected],
        "activity": current_activity["name"] if current_activity else None,
        "target_user_id": target_user_id,
        "target_user_name": target_user["name"] if target_user else None,
        "created_at": datetime.now().isoformat()
    }

    data.setdefault("stories", []).append(story_obj)
    save_data(data)

    return json_response({"story": story, "mbti_type": mbti_type, "mbti_group": group_name})

# ================== 主入口 ==================
async def handler(request, context):
    path = get_path(request)
    method = request.get("method", "GET")

    # 静态文件
    if path in ["/", "/index.html"]:
        try:
            with open("index.html", "r") as f:
                return html_response(f.read())
        except:
            return html_response("index.html not found", 404)

    if path == "/health":
        return json_response({"status": "healthy"})

    # API 路由
    if path == "/api/login":
        return await handle_api_login(request)

    if path == "/api/auth/callback":
        return await handle_callback(request)

    if path == "/api/campers":
        return await handle_campers(request)

    if path == "/api/status/counts":
        return await handle_status_counts(request)

    if path == "/api/user/status" and method == "POST":
        return await handle_update_status(request)

    if path == "/api/story/logs":
        return await handle_story_logs(request)

    if path == "/api/story/generate" and method == "POST":
        return await handle_generate_story(request)

    return json_response({"error": "Not found"}, 404)
