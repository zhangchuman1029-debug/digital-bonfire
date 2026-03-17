"""
Vercel Python - ASGI App with SecondMe Chat API
"""
import json
import os
import random
from datetime import datetime
from urllib.parse import urlencode

DB_FILE = "/tmp/campfire_data.json"

CLIENT_ID = os.getenv("SECONDME_CLIENT_ID", "80f7e9a1-4cc6-4c88-8f8b-41c266bdb3fb")
CLIENT_SECRET = os.getenv("SECONDME_CLIENT_SECRET", "c91baa9bf02e56cd7b6a982ada0f5a76486b85f36662e08826f3e7844fe3f3f4")
REDIRECT_URI = os.getenv("SECONDME_REDIRECT_URI", "https://digital-bonfire.vercel.app/api/auth/callback")

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

def infer_mbti(shades):
    """根据兴趣标签推断 MBTI"""
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

def parse_path(uri):
    if "?" in uri:
        return uri.split("?")[0]
    return uri

async def generate_story_with_chat_api(mbti_type, participants, activity=None, user_token=None):
    """两阶段故事生成：SecondMe 确定主题 + DeepSeek 撰写故事"""
    import httpx

    group_name = MBTI_GROUPS.get(mbti_type, "智识之火")
    group_desc = MBTI_DESC.get(group_name, "")

    participant_names = [p.get("name", "某人") for p in participants[:3]]
    names_str = "、".join(participant_names) if participant_names else "几位旅人"

    # 获取参与者的背景信息
    participant_info = []
    for p in participants[:3]:
        name = p.get("name", "某人")
        shades = p.get("shades", [])
        shades_str = "、".join(shades[:3]) if shades else "热爱生活"
        mbti = p.get("mbti", "?")
        participant_info.append(f"- {name}({mbti}): {shades_str}")

    participants_str = "\n".join(participant_info)

    # ====== 阶段1: SecondMe API 确定故事主题 ======
    story_theme = f"篝火边，{names_str} 围坐在一起"

    if user_token:
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    SECONDME_CHAT_URL,
                    json={
                        "message": f"""根据以下信息，用一句话描述一个篝火故事的背景和主题（不超过30字）：
- 群组：{group_name}（{group_desc}）
- 参与者：{participants_str}
- 活动：{activity if activity else '随意聊天'}

直接输出，不要解释。""",
                        "systemPrompt": "你是一个故事构思助手，只输出一句话描述故事背景。"
                    },
                    headers={
                        "Authorization": f"Bearer {user_token}",
                        "Content-Type": "application/json"
                    },
                    timeout=30.0
                ) as response:
                    theme_parts = []
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                break
                            try:
                                data_obj = json.loads(data)
                                content = data_obj.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                if content:
                                    theme_parts.append(content)
                            except:
                                pass
                    if theme_parts:
                        story_theme = "".join(theme_parts).strip()
        except Exception as e:
            print(f"SecondMe API error: {e}")

    # ====== 阶段2: DeepSeek API 撰写故事 ======
    if DEEPSEEK_API_KEY:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    DEEPSEEK_API_URL,
                    json={
                        "model": "deepseek-chat",
                        "messages": [
                            {
                                "role": "system",
                                "content": "你是一个温暖的篝火 storyteller。根据给定的故事主题，撰写一个温馨、短小（80-120字）的篝火故事。画面感强，体现人物背景和情感。不要使用引号，直接输出故事。"
                            },
                            {
                                "role": "user",
                                "content": f"""请根据以下信息撰写篝火故事：

故事主题：{story_theme}
- 群组类型：{group_name}（{group_desc}）
- 参与者信息：{participants_str}
{f'- 当前活动：{activity}' if activity else ''}

请写出他们之间的互动，并体现各自的人生经历和当下的心情。"""
                            }
                        ],
                        "max_tokens": 300,
                        "temperature": 0.8
                    },
                    headers={
                        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    timeout=30.0
                )

                if response.status_code == 200:
                    result = response.json()
                    story = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                    if story:
                        return story, group_name
        except Exception as e:
            print(f"DeepSeek API error: {e}")

    # 备用模板
    stories = {

    # 模板备用
    stories = {
        "智识之火": [
            f"围坐在篝火旁，{names_str} 开始讨论宇宙的本质。火焰跳动的光影映照着他们思考的脸庞，深刻的对话让夜空更加明亮。",
            f"{names_str} 就一个悖论展开激烈辩论，从存在主义到量子力学，火光中闪烁着智慧的火花。",
        ],
        "灵感之火": [
            f"{names_str} 在篝火旁分享各自的梦想，星星点点的火光映照着他们眼中的光芒，一个美好的计划在交谈中逐渐成形。",
            f"在温暖的火光中，{names_str} 突然有了灵感即兴创作，歌声和笑声在夜空中回荡。",
        ],
        "秩序之火": [
            f"{names_str} 围成一个完美的圆圈，制定了今晚的守则。火光温暖，大家分工明确，秩序中有温馨。",
            f"在 {names_str} 的组织下，大家有序地添加柴火，分享食物，记录这美好的夜晚。",
        ],
        "实践之火": [
            f"{names_str} 决定比赛谁先升起一堆火，欢笑声中火光越烧越旺，实践的乐趣让大家都沉浸其中。",
            f"火光中，{names_str} 展示着各自的绝活，舞步、技巧，笑声不断，行动的快乐感染着每个人。",
        ],
    }

    template_list = stories.get(group_name, stories["智识之火"])
    return random.choice(template_list), group_name

async def handler(event, context):
    """Vercel serverless function"""
    path = parse_path(event.get("rawPath", "/"))
    method = event.get("httpMethod", "GET")
    headers = event.get("headers", {})

    # Static files - 返回 index.html
    if path in ["/", "/index.html"] or not path.startswith("/api"):
        try:
            with open("index.html", "r", encoding="utf-8") as f:
                body = f.read()
        except Exception as e:
            print(f"Error reading index.html: {e}")
            body = "Not found"
        return {"statusCode": 200, "headers": {"Content-Type": "text/html; charset=utf-8"}, "body": body}

    if path == "/health":
        return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": '{"status":"ok"}'}

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

        # 保存 state
        with open("/tmp/auth_state", "w") as f:
            f.write(state)

        return {"statusCode": 302, "headers": {"Location": auth_url}, "body": ""}

    # API: OAuth callback
    if path == "/api/auth/callback":
        import httpx

        query = event.get("queryStringParameters", {})
        code = query.get("code", "")
        state = query.get("state", "")

        if not code:
            return {"statusCode": 400, "headers": {"Content-Type": "application/json"}, "body": '{"error":"No code"}'}

        try:
            # 交换 token
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
                return {"statusCode": 400, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error": token_data.get("message")})}

            access_token = token_data.get("data", {}).get("accessToken")
            if not access_token:
                return {"statusCode": 400, "headers": {"Content-Type": "application/json"}, "body": '{"error":"No token"}'}

            # 获取用户信息
            profile_resp = httpx.get(
                "https://api.mindverse.com/gate/lab/api/secondme/user/info",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=15.0
            )

            # 获取 shades
            shades_resp = httpx.get(
                "https://api.mindverse.com/gate/lab/api/secondme/user/shades",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=15.0
            )

            profile = profile_resp.json()
            user_info = profile.get("data", profile)
            name = user_info.get("name", user_info.get("username", "Anonymous")).upper()

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

            # 保存用户，包含 token
            data = load_data()
            existing = [c for c in data.get("campers", []) if c.get("name", "").upper() == name]

            # MBTI 推断
            mbti = infer_mbti(shades)
            group = MBTI_GROUPS.get(mbti)

            if existing:
                camper = existing[0]
                camper["access_token"] = access_token
                camper["mbti"] = mbti
                camper["mbti_group"] = group
                camper["updated_at"] = datetime.now().isoformat()
            else:
                camper = {
                    "id": len(data.get("campers", [])) + 1,
                    "name": name,
                    "access_token": access_token,
                    "shades": shades,
                    "mbti": mbti,
                    "mbti_group": group,
                    "distance": random.randint(80, 130),
                    "angle": random.uniform(0, 360),
                    "color": "#a855f7",
                    "current_activity": None,
                    "joined_at": datetime.now().isoformat()
                }
                data.setdefault("campers", []).append(camper)

            save_data(data)

            # 跳转回前端
            base_url = REDIRECT_URI.replace("/api/auth/callback", "")
            return {"statusCode": 302, "headers": {"Location": f"{base_url}?joined=true"}, "body": ""}

        except Exception as e:
            return {"statusCode": 500, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error": str(e)})}

    # API: campers
    if path == "/api/campers":
        data = load_data()
        # 不返回 token
        campers = data.get("campers", [])
        safe_campers = [{k: v for k, v in c.items() if k != "access_token"} for c in campers]
        return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(safe_campers)}

    # API: status counts
    if path == "/api/status/counts":
        data = load_data()
        campers = data.get("campers", [])
        counts = {"无": 0, "钓鱼": 0, "煮茶": 0, "围炉夜话": 0, "烤棉花糖": 0, "篝火舞会": 0}
        for camper in campers:
            status = camper.get("current_activity", "无") or "无"
            if status in counts:
                counts[status] += 1
        return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(counts)}

    # API: story logs
    if path == "/api/story/logs":
        data = load_data()
        stories = sorted(data.get("stories", []), key=lambda x: x.get("created_at", ""), reverse=True)[:50]
        return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(stories)}

    # API: generate story with AI
    if path == "/api/story/generate" and method == "POST":
        body_json = json.loads(event.get("body", "{}"))
        mbti_type = body_json.get("mbti_type", "INTJ")

        data = load_data()
        campers = data.get("campers", [])
        participants = [c for c in campers if c.get("mbti") == mbti_type or mbti_type == "ALL"]

        if len(participants) < 2:
            return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"story": "篝火边的人太少，还不够成一个故事... 等更多人来吧！", "mbti_type": mbti_type})}

        # 获取当前用户的 token
        user_token = None
        for c in campers:
            if c.get("access_token"):
                user_token = c["access_token"]
                break

        # 调用 AI 生成故事
        story, group_name = await generate_story_with_chat_api(mbti_type, participants, None, user_token)

        story_obj = {
            "id": len(data.get("stories", [])) + 1,
            "mbti_type": mbti_type,
            "mbti_group": group_name,
            "content": story,
            "created_at": datetime.now().isoformat()
        }

        data.setdefault("stories", []).append(story_obj)
        save_data(data)

        return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"story": story, "mbti_type": mbti_type, "mbti_group": group_name})}

    # API: update status
    if path == "/api/user/status" and method == "POST":
        body_json = json.loads(event.get("body", "{}"))
        user_id = body_json.get("user_id")
        status = body_json.get("status")

        data = load_data()
        for camper in data.get("campers", []):
            if camper["id"] == user_id:
                camper["current_activity"] = None if status == "无" else status
                camper["updated_at"] = datetime.now().isoformat()
                save_data(data)
                # 不返回 token
                safe_camper = {k: v for k, v in camper.items() if k != "access_token"}
                return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(safe_camper)}

        return {"statusCode": 404, "headers": {"Content-Type": "application/json"}, "body": '{"error":"User not found"}'}

    return {"statusCode": 404, "headers": {"Content-Type": "application/json"}, "body": '{"error":"Not found"}'}
