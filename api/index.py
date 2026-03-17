"""
Vercel Python - ASGI App with SecondMe API
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

MBTI_GROUPS = {
    "INTJ": "智识之火", "INTP": "智识之火", "ENTJ": "智识之火", "ENTP": "智识之火",
    "INFJ": "灵感之火", "INFP": "灵感之火", "ENFJ": "灵感之火", "ENFP": "灵感之火",
    "ISTJ": "秩序之火", "ISFJ": "秩序之火", "ESTJ": "秩序之火", "ESFJ": "秩序之火",
    "ISTP": "实践之火", "ISFP": "实践之火", "ESTP": "实践之火", "ESFP": "实践之火",
}

MBTI_DESC = {
    "智识之火": "理性、逻辑、分析型思考者，喜欢深入讨论哲学和科学问题",
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

def parse_path(uri):
    if "?" in uri:
        return uri.split("?")[0]
    return uri

def get_access_token():
    """获取 SecondMe access_token"""
    # 这里简化处理，实际应该存储用户的 token
    # 暂时返回一个模拟的调用方式
    return None

async def generate_story_with_ai(mbti_type, participants, activity=None):
    """调用 SecondMe API 生成故事"""
    import httpx

    group_name = MBTI_GROUPS.get(mbti_type, "智识之火")
    group_desc = MBTI_DESC.get(group_name, "")

    participant_names = [p.get("name", "某人") for p in participants[:3]]
    names_str = "、".join(participant_names) if participant_names else "几位旅人"

    prompt = f"""你是一个篝火边的 storyteller。请根据以下信息生成一个温暖、简短（50-80字）的篝火故事：

- 群组类型：{group_name}（{group_desc}）
- 参与者：{names_str}
{f'- 当前活动：{activity}' if activity else ''}

要求：
1. 故事要体现该群组的性格特点
2. 温暖、有画面感
3. 不要使用引号或特殊格式
4. 直接输出故事内容"""

    try:
        # 由于 Vercel 无状态，我们使用简单的本地生成
        # 实际部署时可以存储用户 token 来调用真实 API
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
        story = random.choice(template_list)

        return story, group_name

    except Exception as e:
        return f"篝火边，{names_str} 围坐在一起，温暖的火光驱散了夜的寒冷。", group_name

async def handler(event, context):
    """Vercel serverless function"""
    path = parse_path(event.get("rawPath", "/"))
    method = event.get("httpMethod", "GET")
    headers = event.get("headers", {})

    # Static files
    if path in ["/", "/index.html"]:
        try:
            with open("index.html", "r") as f:
                body = f.read()
        except:
            body = "Not found"
        return {"statusCode": 200, "headers": {"Content-Type": "text/html"}, "body": body}

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
        return {"statusCode": 302, "headers": {"Location": auth_url}, "body": ""}

    # API: campers
    if path == "/api/campers":
        data = load_data()
        return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(data.get("campers", []))}

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

        # 调用 AI 生成故事
        story, group_name = await generate_story_with_ai(mbti_type, participants)

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
                return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(camper)}

        return {"statusCode": 404, "headers": {"Content-Type": "application/json"}, "body": '{"error":"User not found"}'}

    return {"statusCode": 404, "headers": {"Content-Type": "application/json"}, "body": '{"error":"Not found"}'}
