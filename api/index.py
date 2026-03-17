"""
Vercel Python Handler for Digital Bonfire
"""
import os
import json
import random
from datetime import datetime
from urllib.parse import urlencode

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import RedirectResponse, FileResponse, JSONResponse
from pydantic import BaseModel
import httpx

# ================== 配置 ==================
CLIENT_ID = os.getenv("SECONDME_CLIENT_ID", "80f7e9a1-4cc6-4c88-8f8b-41c266bdb3fb")
CLIENT_SECRET = os.getenv("SECONDME_CLIENT_SECRET", "c91baa9bf02e56cd7b6a982ada0f5a76486b85f36662e08826f3e7844fe3f3f4")
REDIRECT_URI = os.getenv("SECONDME_REDIRECT_URI", "https://your-project.vercel.app/api/auth/callback")

SECONDME_AUTH_URL = "https://go.second.me/oauth/"
SECONDME_TOKEN_URL = "https://api.mindverse.com/gate/lab/api/oauth/token/code"
SECONDME_PROFILE_URL = "https://api.mindverse.com/gate/lab/api/secondme/user/info"
SECONDME_SHADES_URL = "https://api.mindverse.com/gate/lab/api/secondme/user/shades"

# Vercel 环境使用 /tmp 目录存储数据
DB_FILE = "/tmp/campfire_data.json"

app = FastAPI()

# ================== 数据模型 ==================
class JoinRequest(BaseModel):
    name: str
    intro: str = ""
    avatar_color: str = None
    shades: list = []
    mbti: str = None

class StatusUpdate(BaseModel):
    user_id: int
    status: str

class StoryRequest(BaseModel):
    mbti_type: str
    participants: list = []
    target_user_id: int = None

# ================== 数据存储 ==================
def load_data():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {"campers": [], "messages": [], "activities": [], "stories": [], "mbti_groups": {}}

def save_data(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)

# ================== 常量 ==================
ACTIVITIES = {
    "钓鱼": {"emoji": "🎣", "description": "静心垂钓", "mbti": ["INTJ", "INTP", "ISTP", "ISFP"]},
    "煮茶": {"emoji": "🍵", "description": "品茶论道", "mbti": ["INFJ", "INFP", "ENFJ", "ENFP"]},
    "围炉夜话": {"emoji": "💬", "description": "畅所欲言", "mbti": ["ENTJ", "ENTP", "ESTJ", "ESFJ"]},
    "烤棉花糖": {"emoji": "🍡", "description": "甜蜜时光", "mbti": ["ESFP", "ISFJ", "ISTJ", "ESTP"]},
    "篝火舞会": {"emoji": "💃", "desc": "尽情起舞", "mbti": ["ALL"]},
}

MBTI_GROUPS = {
    "INTJ": "智识之火", "INTP": "智识之火", "ENTJ": "智识之火", "ENTP": "智识之火",
    "INFJ": "灵感之火", "INFP": "灵感之火", "ENFJ": "灵感之火", "ENFP": "灵感之火",
    "ISTJ": "秩序之火", "ISFJ": "秩序之火", "ESTJ": "秩序之火", "ESFJ": "秩序之火",
    "ISTP": "实践之火", "ISFP": "实践之火", "ESTP": "实践之火", "ESFP": "实践之火",
}

# ================== API 端点 ==================

@app.get("/")
async def root():
    return FileResponse("index.html")

@app.get("/index.html")
async def index():
    return FileResponse("index.html")

@app.get("/health")
async def health():
    return {"status": "healthy"}

# 获取所有用户
@app.get("/api/campers")
async def get_campers():
    data = load_data()
    return data.get("campers", [])

# 获取各状态人数
@app.get("/api/status/counts")
async def get_status_counts():
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

    return counts

# 更新用户状态
@app.post("/api/user/status")
async def update_user_status(update: StatusUpdate):
    data = load_data()
    campers = data.get("campers", [])

    for camper in campers:
        if camper["id"] == update.user_id:
            if update.status == "无":
                camper["current_activity"] = None
            else:
                camper["current_activity"] = update.status

            camper["updated_at"] = datetime.now().isoformat()
            save_data(data)
            return camper

    raise HTTPException(status_code=404, detail="User not found")

# 获取故事日志
@app.get("/api/story/logs")
async def get_story_logs(limit: int = 50):
    data = load_data()
    stories = data.get("stories", [])
    return sorted(stories, key=lambda x: x.get("created_at", ""), reverse=True)[:limit]

# 生成故事
@app.post("/api/story/generate")
async def generate_story(req: StoryRequest):
    data = load_data()
    campers = data.get("campers", [])
    activities = data.get("activities", [])

    participants = []
    for camper in campers:
        if camper.get("mbti") == req.mbti_type or req.mbti_type == "ALL":
            participants.append(camper)

    if len(participants) < 2:
        return {"story": "篝火边的人太少，还不够成一个故事... 等更多人来吧！", "mbti_type": req.mbti_type}

    current_activity = None
    for activity in activities:
        if activity["name"] in ["围炉夜话", "篝火舞会"] or not activity["participants"]:
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

    group_name = MBTI_GROUPS.get(req.mbti_type, "misc")
    templates = story_templates.get(group_name, story_templates.get("智识之火"))

    selected = random.sample(participants, min(3, len(participants)))
    names = [p["name"] for p in selected]

    template = random.choice(templates)
    story = template.format(p1=names[0], p2=names[1], p3=names[2] if len(names) > 2 else names[0])

    if current_activity:
        activity_text = f"大家正在一起{current_activity['name']}，"
        story = activity_text + story

    target_user = None
    if req.target_user_id:
        for c in campers:
            if c["id"] == req.target_user_id:
                target_user = c
                break

    story_obj = {
        "id": len(data.get("stories", [])) + 1,
        "mbti_type": req.mbti_type,
        "mbti_group": group_name,
        "content": story,
        "participants": [p["id"] for p in selected],
        "participant_names": [p["name"] for p in selected],
        "activity": current_activity["name"] if current_activity else None,
        "target_user_id": req.target_user_id,
        "target_user_name": target_user["name"] if target_user else None,
        "created_at": datetime.now().isoformat()
    }

    data.setdefault("stories", []).append(story_obj)
    save_data(data)

    return {"story": story, "mbti_type": req.mbti_type, "mbti_group": group_name}

# ================== SecondMe OAuth ==================

@app.get("/api/login")
async def login():
    state = f"campfire_{random.randint(100000, 999999)}"
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "user.info,chat,user.info.shades,user.info.softmemory,note.add",
        "state": state,
        "force_login": "true"
    }
    auth_url = SECONDME_AUTH_URL + "?" + urlencode(params)

    # 保存 state 到临时文件
    with open("/tmp/auth_state", "w") as f:
        f.write(state)

    return RedirectResponse(url=auth_url)


@app.get("/api/auth/callback")
async def callback(code: str = Query(...), state: str = Query(...)):
    try:
        with open("/tmp/auth_state", "r") as f:
            saved_state = f.read().strip()
        if state != saved_state:
            raise HTTPException(status_code=400, detail="Invalid state parameter")
    except FileNotFoundError:
        pass

    try:
        async with httpx.AsyncClient() as client:
            # 1. 获取 token
            token_resp = await client.post(
                SECONDME_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": REDIRECT_URI,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0
            )

            if token_resp.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_resp.text}")

            token_data = token_resp.json()
            if token_data.get("code") != 0:
                raise HTTPException(status_code=400, detail=f"Token exchange error: {token_data.get('message')}")

            token_info = token_data.get("data", {})
            access_token = token_info.get("accessToken")

            if not access_token:
                raise HTTPException(status_code=400, detail="No access token received")

            # 2. 获取用户资料
            profile_resp = await client.get(
                SECONDME_PROFILE_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=15.0
            )

            # 3. 获取 shades
            shades_resp = await client.get(
                SECONDME_SHADES_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=15.0
            )

    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"API request failed: {type(e).__name__}: {str(e)}")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=500, detail=f"HTTP error: {e.response.status_code} - {e.response.text}")

    # 解析用户资料
    profile = profile_resp.json()
    user_info = profile.get("data", profile)
    name = user_info.get("name", user_info.get("username", "Anonymous"))

    # 解析 shades
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

    # 根据 shades 推断 MBTI
    mbti = infer_mbti(shades)

    # 根据 shades 分类
    keywords_logic = ['python', 'code', 'dev', '后端', 'algorithm', 'logic', 'ai', 'ml', 'data', '技术', '编程']
    keywords_creative = ['design', 'art', 'creative', 'music', '画', '创意', '设计', '艺术', '绘画']

    shades_lower = [s.lower() for s in shades]
    is_logic = any(any(kw in s for kw in keywords_logic) for s in shades_lower)
    is_creative = any(any(kw in s for kw in keywords_creative) for s in shades_lower)

    if is_logic and not is_logic:
        distance = 130
        color = "#00d4ff"
    elif is_creative and not is_logic:
        distance = 85
        color = "#ff6b35"
    else:
        distance = 110
        color = "#a855f7"

    # 保存用户
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

    # 跳转到前端页面
    base_url = REDIRECT_URI.replace("/api/auth/callback", "")
    frontend_url = f"{base_url}?joined=true"
    return RedirectResponse(url=frontend_url)


def infer_mbti(shades: list) -> str:
    """根据性格标签推断 MBTI"""
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


# Vercel handler
def handler(request, context):
    return app(request, context)
