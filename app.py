# 每日 AI 新闻助手 — Web 界面
# 提供: 填身份/订阅偏好 (profile.json)、查看历史简报、手动触发一次生成、查看推送信封。
# 跑法: python app.py   (默认 http://127.0.0.1:8000)

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import profile_store, orchestrator, news_engine
from pathlib import Path
import uvicorn, json

BASE = Path(__file__).resolve().parent
STATIC = BASE / "static"
app = FastAPI(title="Daily AI News Agent")


@app.get("/api/profile")
def get_profile():
    return profile_store.load()


@app.post("/api/profile")
def save_profile(profile: dict):
    profile_store.save(profile)
    return {"ok": True, "profile": profile}


@app.get("/api/briefings")
def list_briefings():
    files = sorted((BASE / "briefings").glob("*.md"), reverse=True)
    return [
        {"file": f.name, "path": str(f), "size": f.stat().st_size} for f in files
    ]


@app.get("/api/briefings/{name}")
def get_briefing(name: str):
    f = BASE / "briefings" / name
    if not f.is_file():
        return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
    return {"ok": True, "file": name, "markdown": f.read_text(encoding="utf-8")}


@app.get("/api/push")
def list_push():
    files = sorted((BASE / "outbox").glob("*.json"), reverse=True)
    out = []
    for f in files:
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            out.append({"file": f.name, "error": "parse failed"})
    return out


@app.post("/api/run")
def run_now():
    """手动触发一次完整任务: 抓新闻 + LLM 筛选/摘要/写简报/写推送。"""
    return orchestrator.run_daily()


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
