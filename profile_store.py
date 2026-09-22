# 用户偏好 / 身份: 极简 JSON 存储 (单用户示例)。
# 订阅偏好: topics(话题标签), keywords(关键词), excluded(排除词), 语言, 推送渠道。

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
PROFILE_FILE = BASE / "profile.json"

DEFAULT_PROFILE = {
    "identity": {
        "name": "",
        "role": "",
        "timezone": "Asia/Shanghai",
    },
    "subscription": {
        "topics": ["LLM", "Agents", "Multimodal"],
        "keywords": ["openai", "anthropic", "google", "deepseek", "hugging face"],
        "excluded": [],
        "language": "zh",
        "max_items_per_briefing": 12,
    },
    "delivery": {
        "channel": "outbox",  # outbox=本地文件推送(默认), 可扩展 email/webhook
        "time": "08:00",
    },
}


def load() -> dict:
    if not PROFILE_FILE.exists():
        save(DEFAULT_PROFILE)
    return json.loads(PROFILE_FILE.read_text(encoding="utf-8"))


def save(profile: dict) -> None:
    PROFILE_FILE.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    print(json.dumps(load(), ensure_ascii=False, indent=1))
