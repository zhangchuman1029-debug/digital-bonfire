"""
Flask App for Render deployment
"""
from flask import Flask, request, jsonify, redirect
import json
import os
import random
from datetime import datetime
from urllib.parse import urlencode
import httpx

app = Flask(__name__)

DB_FILE = "campfire_data.json"

CLIENT_ID = os.getenv("SECONDME_CLIENT_ID", "80f7e9a1-4cc6-4c88-8f8b-41c266bdb3fb")
CLIENT_SECRET = os.getenv("SECONDME_CLIENT_SECRET", "c91baa9bf02e56cd7b6a982ada0f5a76486b85f36662e08826f3e7844fe3f3f4")
REDIRECT_URI = os.getenv("SECONDME_REDIRECT_URI", "https://your-app.onrender.com/api/auth/callback")

SECONDME_AUTH_URL = "https://go.second.me/oauth/"
SECONDME_TOKEN_URL = "https://api.mindverse.com/gate/lab/api/oauth/token/code"
SECONDME_CHAT_URL = "https://api.mindverse.com/gate/lab/api/secondme/chat/stream"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-34b5b8fd7abf4939b10ee959f987525d")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

MBTI_GROUPS = {
    "INTJ": "智识之火", "INTP": "智识之火", "ENTJ": "智识之火", "ENTP": "智识之火",
    "INFJ": "灵感之火", "INFP": "灵感之火", "ENFJ": "灵感之火", "ENFP": "灵感之火",
    "ISTJ": "秩序之火", "ISFJ": "秩序之火", "ESTJ": "秩序之火", "ESFJ": "秩序之火",
    "ISTP": "实践之火", "ISFP": "实践之火", "ESTP": "实践之火", "ESFP": "实践之火",
}

MBTI_DESC = {
    "智识之火": "理性、逻辑，分析型思考者，喜欢深入讨论哲学和科学问题",
    "灵感之火": "创意、直觉、富有想象力的理想主义者",
    "秩序之火": "务实、组织性强、注重规则和传统",
    "实践之火": "行动派、灵活、喜欢动手实践和冒险",
}

def load_data():
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r") as f:
                return json.load(f)
    except:
        pass
    return {"campers": [], "stories": [], "activities": []}

def save_data(data):
    try:
        with open(DB_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)
    except:
        pass

def infer_mbti(shades):
    if not shades:
        return random.choice(list(MBTI_GROUPS.keys()))
    shades_str = " ".join(shades).lower()
    if any(w in shades_str for w in ['理性', '逻辑', '分析', '独立', '思考', '技术', '编程']):
        return "INTP" if random.random() > 0.5 else "INTJ"
    if any(w in shades_str for w in ['情感', '感受', '共情', '温暖', '艺术', '创意']):
        return "INFP" if random.random() > 0.5 else "INFJ"
    if any(w in shades_str for w in ['实际', '现实', '务实', '动手']):
        return "ISTP" if random.random() > 0.5 else "ESTP"
    if any(w in shades_str for w in ['传统', '稳定', '可靠', '忠诚']):
        return "ISFJ" if random.random() > 0.5 else "ESFJ"
    return random.choice(list(MBTI_GROUPS.keys()))

# ================== 故事生成 ==================
async def generate_story_async(mbti_type, participants, activity=None, user_token=None):
    """两阶段故事生成"""
    group_name = MBTI_GROUPS.get(mbti_type, "智识之火")
    group_desc = MBTI_DESC.get(group_name, "")

    participant_names = [p.get("name", "某人") for p in participants[:3]]
    names_str = "、".join(participant_names) if participant_names else "几位旅人"

    participant_info = []
    for p in participants[:3]:
        name = p.get("name", "某人")
        shades = p.get("shades", [])
        shades_str = "、".join(shades[:3]) if shades else "热爱生活"
        mbti = p.get("mbti", "?")
        participant_info.append(f"- {name}({mbti}): {shades_str}")

    participants_str = "\n".join(participant_info)

    # 阶段1: SecondMe 确定主题
    story_theme = f"篝火边，{names_str} 围坐在一起"

    if user_token:
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST", SECONDME_CHAT_URL,
                    json={
                        "message": f"用一句话描述篝火故事主题（不超过30字）：群组{group_name}，参与者{names_str}",
                        "systemPrompt": "只输出一句话"
                    },
                    headers={"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"},
                    timeout=30.0
                ) as response:
                    theme_parts = []
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]": break
                            try:
                                content = json.loads(data).get("choices", [{}])[0].get("delta", {}).get("content", "")
                                if content: theme_parts.append(content)
                            except: pass
                    if theme_parts:
                        story_theme = "".join(theme_parts).strip()
        except Exception as e:
            print(f"SecondMe error: {e}")

    # 阶段2: DeepSeek 撰写故事
    if DEEPSEEK_API_KEY:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    DEEPSEEK_API_URL,
                    json={
                        "model": "deepseek-chat",
                        "messages": [
                            {"role": "system", "content": "你是篝火故事家。撰写80-120字的温馨故事，画面感强，体现人物背景。不要引号。"},
                            {"role": "user", "content": f"主题：{story_theme}\n群组：{group_name}({group_desc})\n参与者：{participants_str}\n活动：{activity or '随意聊天'}"}
                        ],
                        "max_tokens": 300, "temperature": 0.8
                    },
                    headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
                    timeout=30.0
                )
                if response.status_code == 200:
                    story = response.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                    if story:
                        return story, group_name
        except Exception as e:
            print(f"DeepSeek error: {e}")

    # 备用
    stories = {
        "智识之火": [f"围坐在篝火旁，{names_str} 讨论宇宙本质，火光映照思考的脸庞。"],
        "灵感之火": [f"{names_str} 在火光中分享各自的梦想，眼睛里闪着光。"],
        "秩序之火": [f"{names_str} 围成圆圈，分工明确，温暖而有序。"],
        "实践之火": [f"{names_str} 展示绝活，笑声不断，行动的快乐感染每个人。"],
    }
    return random.choice(stories.get(group_name, stories["智识之火"])), group_name

# ================== 路由 ==================
@app.route('/')
def index():
    return redirect('/index.html')

@app.route('/index.html')
def index_html():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "index.html not found", 404

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

@app.route('/api/login')
def login():
    state = f"campfire_{random.randint(100000, 999999)}"
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "user.info,chat,user.info.shades,user.info.softmemory",
        "state": state,
        "force_login": "true"
    }
    return redirect(SECONDME_AUTH_URL + "?" + urlencode(params))

@app.route('/api/auth/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return jsonify({"error": "No code"}), 400

    try:
        token_resp = httpx.post(
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

        token_data = token_resp.json()
        if token_data.get("code") != 0:
            return jsonify({"error": token_data.get("message")}), 400

        access_token = token_data.get("data", {}).get("accessToken")
        if not access_token:
            return jsonify({"error": "No token"}), 400

        # 获取用户信息
        profile_resp = httpx.get(
            "https://api.mindverse.com/gate/lab/api/secondme/user/info",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15.0
        )
        shades_resp = httpx.get(
            "https://api.mindverse.com/gate/lab/api/secondme/user/shades",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15.0
        )

        user_info = profile_resp.json().get("data", {})
        name = user_info.get("name", user_info.get("username", "Anonymous")).upper()

        shades = []
        try:
            shades_obj = shades_resp.json().get("data", {})
            if isinstance(shades_obj, dict):
                shades = shades_obj.get("shades", shades_obj.get("tags", []))
            elif isinstance(shades_obj, list):
                shades = shades_obj
        except:
            pass

        # 保存用户
        data = load_data()
        existing = [c for c in data.get("campers", []) if c.get("name", "").upper() == name]

        mbti = infer_mbti(shades)
        group = MBTI_GROUPS.get(mbti)

        if existing:
            camper = existing[0]
            camper.update({
                "access_token": access_token, "shades": shades,
                "mbti": mbti, "mbti_group": group,
                "updated_at": datetime.now().isoformat()
            })
        else:
            camper = {
                "id": len(data.get("campers", [])) + 1,
                "name": name, "access_token": access_token, "shades": shades,
                "mbti": mbti, "mbti_group": group,
                "distance": random.randint(80, 130),
                "angle": random.uniform(0, 360),
                "color": "#a855f7",
                "current_activity": None,
                "joined_at": datetime.now().isoformat()
            }
            data.setdefault("campers", []).append(camper)

        save_data(data)
        return redirect(f"/?joined=true")

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/campers')
def get_campers():
    data = load_data()
    campers = [{k: v for k, v in c.items() if k != "access_token"} for c in data.get("campers", [])]
    return jsonify(campers)

@app.route('/api/status/counts')
def get_status_counts():
    data = load_data()
    campers = data.get("campers", [])
    counts = {"无": 0, "钓鱼": 0, "煮茶": 0, "围炉夜话": 0, "烤棉花糖": 0, "篝火舞会": 0}
    for camper in campers:
        status = camper.get("current_activity", "无") or "无"
        if status in counts:
            counts[status] += 1
    return jsonify(counts)

@app.route('/api/story/logs')
def get_story_logs():
    data = load_data()
    stories = sorted(data.get("stories", []), key=lambda x: x.get("created_at", ""), reverse=True)[:50]
    return jsonify(stories)

@app.route('/api/story/generate', methods=['POST'])
def generate_story():
    body = request.get_json()
    mbti_type = body.get("mbti_type", "INTJ")

    data = load_data()
    campers = data.get("campers", [])
    participants = [c for c in campers if c.get("mbti") == mbti_type or mbti_type == "ALL"]

    if len(participants) < 2:
        return jsonify({"story": "篝火边的人太少，还不够成一个故事... 等更多人来吧！", "mbti_type": mbti_type})

    # 获取 token
    user_token = None
    for c in campers:
        if c.get("access_token"):
            user_token = c["access_token"]
            break

    # 同步调用异步函数
    import asyncio
    story, group_name = asyncio.run(generate_story_async(mbti_type, participants, None, user_token))

    story_obj = {
        "id": len(data.get("stories", [])) + 1,
        "mbti_type": mbti_type,
        "mbti_group": group_name,
        "content": story,
        "created_at": datetime.now().isoformat()
    }

    data.setdefault("stories", []).append(story_obj)
    save_data(data)

    return jsonify({"story": story, "mbti_type": mbti_type, "mbti_group": group_name})

@app.route('/api/user/status', methods=['POST'])
def update_status():
    body = request.get_json()
    user_id = body.get("user_id")
    status = body.get("status")

    data = load_data()
    for camper in data.get("campers", []):
        if camper["id"] == user_id:
            camper["current_activity"] = None if status == "无" else status
            camper["updated_at"] = datetime.now().isoformat()
            save_data(data)
            safe_camper = {k: v for k, v in camper.items() if k != "access_token"}
            return jsonify(safe_camper)

    return jsonify({"error": "User not found"}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
