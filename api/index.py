"""
Digital Bonfire 后端服务
- FastAPI + Supabase 存储 + MBTI 分组 + 故事生成
"""
import os
import json
import random
from datetime import datetime
from urllib.parse import urlencode, quote
from typing import Optional, List

from fastapi import FastAPI, Query, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse, JSONResponse
from pydantic import BaseModel
import httpx

# ================== 配置 ==================
CLIENT_ID = os.getenv("SECONDME_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("SECONDME_CLIENT_SECRET", "")
REDIRECT_URI = os.getenv("SECONDME_REDIRECT_URI", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "")

SECONDME_AUTH_URL = "https://go.second.me/oauth/"
SECONDME_TOKEN_URL = "https://api.mindverse.com/gate/lab/api/oauth/token/code"
SECONDME_PROFILE_URL = "https://api.mindverse.com/gate/lab/api/secondme/user/info"
SECONDME_SHADES_URL = "https://api.mindverse.com/gate/lab/api/secondme/user/shades"

# ================== Supabase 存储 ==================
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
TABLE_NAME = "campfire_storage"

_supabase_client = None

def get_supabase() -> Client:
    global _supabase_client
    if not _supabase_client and SUPABASE_URL and SUPABASE_KEY:
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client

def load_data():
    """从 Supabase 加载数据"""
    print(f"[DEBUG] load_data: SUPABASE_URL={bool(SUPABASE_URL)}, SUPABASE_KEY={bool(SUPABASE_KEY)}")
    try:
        client = get_supabase()
        if not client:
            print("[DEBUG] No Supabase client")
            return get_default_data()

        response = client.table(TABLE_NAME).select("data").eq("id", "main_data").execute()
        print(f"[DEBUG] load response: {response.data}")
        if response.data and len(response.data) > 0:
            return response.data[0].get("data", {})
    except Exception as e:
        print(f"[DEBUG] Supabase load error: {e}")

    return get_default_data()

def save_data(data):
    """保存数据到 Supabase（upsert）"""
    print(f"[DEBUG] save_data: SUPABASE_URL={bool(SUPABASE_URL)}, SUPABASE_KEY={bool(SUPABASE_KEY)}")
    try:
        client = get_supabase()
        if not client:
            print("[DEBUG] No Supabase client for save")
            return

        result = client.table(TABLE_NAME).upsert({
            "id": "main_data",
            "data": data
        }).execute()
        print(f"[DEBUG] save result: {result.data}")
    except Exception as e:
        print(f"Supabase save error: {e}")

def get_default_data():
    return {
        "campers": [],
        "messages": [],
        "activities": [],
        "stories": [],
        "mbti_groups": {}
    }

# ================== FastAPI 应用 ==================
app = FastAPI(title="Digital Bonfire API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="."), name="static")

# ================== 数据模型 ==================
class ActivityCreate(BaseModel):
    name: str
    description: str = ""
    host_id: int

class ActivityJoin(BaseModel):
    activity_id: int
    user_id: int

class StoryRequest(BaseModel):
    mbti_type: str
    participants: list = []
    target_user_id: int = None

class StatusUpdate(BaseModel):
    user_id: int
    status: str

# ================== 常量 ==================
ACTIVITIES = {
    "钓鱼": {"emoji": "🎣", "description": "静心垂钓，等待鱼儿上钩", "mbti": ["INTJ", "INTP", "ISTP", "ISFP"]},
    "煮茶": {"emoji": "🍵", "description": "煮一壶好茶，品味人生", "mbti": ["INFJ", "INFP", "ENFJ", "ENFP"]},
    "围炉夜话": {"emoji": "💬", "description": "围坐火旁，畅所欲言", "mbti": ["ENTJ", "ENTP", "ESTJ", "ESFJ"]},
    "烤棉花糖": {"emoji": "🍡", "description": "烤一份甜蜜，享受当下", "mbti": ["ESFP", "ISFJ", "ISTJ", "ESTP"]},
    "篝火舞会": {"emoji": "💃", "description": "火光中起舞，尽情释放", "mbti": ["ALL"]},
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

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/api/campers")
async def get_campers(response: Response):
    data = load_data()
    campers = [{k: v for k, v in c.items() if k != "access_token"} for c in data.get("campers", [])]
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return campers

@app.get("/api/me")
async def get_me(response: Response, authorization: str = None):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    if not authorization or not authorization.startswith("Bearer "):
        return {"authenticated": False}

    token = authorization.replace("Bearer ", "")
    data = load_data()

    for c in data.get("campers", []):
        if c.get("access_token") == token:
            user = {k: v for k, v in c.items() if k != "access_token"}
            return {"authenticated": True, "user": user}

    return {"authenticated": False}

@app.get("/api/activities")
async def get_activities():
    data = load_data()
    return data.get("activities", [])

@app.get("/api/mbti/groups")
async def get_mbti_groups():
    data = load_data()
    campers = data.get("campers", [])

    groups = {}
    for camper in campers:
        mbti = camper.get("mbti", "UNKNOWN")
        group_name = MBTI_GROUPS.get(mbti, "misc")

        if group_name not in groups:
            groups[group_name] = {"name": group_name, "mbti_types": [], "members": []}

        if mbti not in groups[group_name]["mbti_types"]:
            groups[group_name]["mbti_types"].append(mbti)

        if camper not in groups[group_name]["members"]:
            groups[group_name]["members"].append(camper)

    return list(groups.values())

@app.post("/api/activity")
async def create_activity(act: ActivityCreate):
    data = load_data()

    activity = {
        "id": len(data.get("activities", [])) + 1,
        "name": act.name,
        "emoji": ACTIVITIES.get(act.name, {}).get("emoji", "🔥"),
        "description": act.description or ACTIVITIES.get(act.name, {}).get("description", ""),
        "host_id": act.host_id,
        "participants": [act.host_id],
        "created_at": datetime.now().isoformat()
    }

    data.setdefault("activities", []).append(activity)
    save_data(data)

    return activity

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

@app.post("/api/activity/join")
async def join_activity(join_req: ActivityJoin):
    data = load_data()
    activities = data.get("activities", [])

    for activity in activities:
        if activity["id"] == join_req.activity_id:
            if join_req.user_id not in activity["participants"]:
                activity["participants"].append(join_req.user_id)
                save_data(data)
            return activity

    raise HTTPException(status_code=404, detail="Activity not found")

@app.post("/api/activity/leave")
async def leave_activity(join_req: ActivityJoin):
    data = load_data()
    activities = data.get("activities", [])

    for activity in activities:
        if activity["id"] == join_req.activity_id:
            if join_req.user_id in activity["participants"]:
                activity["participants"].remove(join_req.user_id)
                save_data(data)
            return activity

    raise HTTPException(status_code=404, detail="Activity not found")

@app.get("/api/stories")
async def get_stories(mbti: str = None):
    data = load_data()
    stories = data.get("stories", [])

    if mbti:
        stories = [s for s in stories if s.get("mbti_type") == mbti]

    return stories[-10:][::-1]

@app.get("/api/story/logs")
async def get_story_logs(limit: int = 50):
    data = load_data()
    stories = data.get("stories", [])
    return sorted(stories, key=lambda x: x.get("created_at", ""), reverse=True)[:limit]

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
        story = f"大家正在一起{current_activity['name']}，" + story

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
    return RedirectResponse(url=auth_url)

@app.get("/api/auth/callback")
async def callback(code: str = Query(...), state: str = Query(...)):
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
    try:
        profile = profile_resp.json()
        user_info = profile.get("data", profile)
        name = user_info.get("name", user_info.get("username", "Anonymous"))
    except Exception as e:
        name = "USER"

    # 解析 shades
    shades = []
    try:
        shades_data = shades_resp.json()
        shades_obj = shades_data.get("data", {})
        if isinstance(shades_obj, dict):
            shades = shades_obj.get("shades", shades_obj.get("tags", []))
        elif isinstance(shades_obj, list):
            shades = shades_obj
    except Exception:
        shades = []

    # 推断 MBTI
    mbti = infer_mbti(shades)

    # 根据 shades 分类
    keywords_logic = ['python', 'code', 'dev', '后端', 'algorithm', 'logic', 'ai', 'ml', 'data', '技术', '编程']
    keywords_creative = ['design', 'art', 'creative', 'music', '画', '创意', '设计', '艺术', '绘画']

    shades_lower = [s.lower() for s in shades]
    is_logic = any(any(kw in s for kw in keywords_logic) for s in shades_lower)
    is_creative = any(any(kw in s for kw in keywords_creative) for s in shades_lower)

    if is_logic and not is_creative:
        distance = 130
        color = "#00d4ff"
        type_label = "LOGIC"
    elif is_creative and not is_logic:
        distance = 85
        color = "#ff6b35"
        type_label = "CREATIVE"
    else:
        distance = 110
        color = "#a855f7"
        type_label = "HYBRID"

    # 保存用户
    data = load_data()
    existing = [c for c in data.get("campers", []) if c.get("name", "").upper() == name.upper()]

    if existing:
        camper = existing[0]
        camper["access_token"] = access_token
        camper["distance"] = distance
        camper["color"] = color
        camper["type"] = type_label
        camper["shades"] = shades
        camper["mbti"] = mbti
        camper["mbti_group"] = MBTI_GROUPS.get(mbti, "misc")
        camper["updated_at"] = datetime.now().isoformat()
    else:
        camper = {
            "id": len(data.get("campers", [])) + 1,
            "name": name.upper(),
            "access_token": access_token,
            "intro": "通过 SecondMe 登录",
            "distance": distance,
            "angle": random.uniform(0, 360),
            "color": color,
            "type": type_label,
            "shades": shades,
            "mbti": mbti,
            "mbti_group": MBTI_GROUPS.get(mbti, "misc"),
            "current_activity": None,
            "joined_at": datetime.now().isoformat()
        }
        data.setdefault("campers", []).append(camper)

    save_data(data)

    # 通过 URL 参数传递 access_token
    frontend_url = f"{FRONTEND_URL}?joined=true&user_id={camper['id']}&user_name={quote(camper['name'])}&token={quote(access_token)}"
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
        return "ISFJ" if random.random() > 0.5 else "ESFJ"

    if any(w in shades_str for w in ['自由', '灵活', '创意', '热情']):
        return "ISFP" if random.random() > 0.5 else "ESFP"

    return random.choice(list(MBTI_GROUPS.keys()))

@app.get("/api/user/info")
async def get_user_info(token: str):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(SECONDME_PROFILE_URL, headers=headers, timeout=10.0)
            return resp.json()
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/chat")
async def chat_with_secondme(message: str, token: str):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"message": message, "model": "secondme"}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.mindverse.com/gate/lab/api/v1/chat",
                headers=headers,
                json=payload,
                timeout=30.0
            )
            return resp.json()
    except Exception as e:
        return {"error": str(e)}
