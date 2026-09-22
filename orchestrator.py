# 编排层: 把"抓新闻 -> LLM 筛选/摘要 -> 写简报 -> 推送"串成一次任务。
# 抓取是确定性步骤(快而稳), 但"筛选/摘要/排版/推送"交给 agent_loop 的
# 工具调用循环完成, 由模型自行决定调用 read_file / search_content / write_file / bash 的次数与顺序。

import json
from datetime import datetime
from pathlib import Path

import news_engine
import profile_store
from agent_loop import react_loop

BASE = Path(__file__).resolve().parent
OUTBOX = BASE / "outbox"
BRIEFINGS = BASE / "briefings"
LOGS = BASE / "logs"
PUSH = BASE / "outbox"  # 推送信封也放 outbox (工具沙箱根之一)
for p in (OUTBOX, BRIEFINGS, LOGS):
    p.mkdir(parents=True, exist_ok=True)

BRIEFING_TEMPLATE = """# 每日 AI 新闻简报 — {date}

> 生成于 {gen_time} | 订阅者: {name} ({role})
> 话题: {topics}
> 数据来源: {n} 条聚合新闻, {n_err} 个源不可达

## 重点 (Top 3)
{top3}

## 按话题分组
{sections}

## 我可能关心的 (关键词命中)
{keyword_hits}

## 数据说明
- 本轮不可达的源: {errors}
- 共 {total} 条原始新闻, 保留 {kept} 条
"""


def _build_user_prompt(profile: dict, news_path: str, today: str) -> str:
    sub = profile.get("subscription", {})
    topics = ", ".join(sub.get("topics", []))
    kws = ", ".join(sub.get("keywords", []))
    excluded = ", ".join(sub.get("excluded", [])) or "(无)"
    lang = sub.get("language", "zh")
    ident = profile.get("identity", {})
    name = ident.get("name") or "(未填写)"
    role = ident.get("role") or "(未填写)"

    return f"""今天的日期是 {today}。聚合好的新闻在 {news_path} (JSON: {{"ai_items":[...]}})。

请为我完成一份 AI 新闻简报, 要求:
1) 先用 read_file 读取该 JSON;
2) 按订阅者身份筛选: 名字={name}, 角色={role}, 关注话题=[{topics}], 关键词=[{kws}], 排除词=[{excluded}], 语言偏好={lang};
3) 挑选最相关的至多 {sub.get('max_items_per_briefing', 12)} 条, 每条给 1 行摘要(中文), 并标注来源;
4) 按 BRIEFING_TEMPLATE 的版式排版 (重点 Top3 / 按话题分组 / 关键词命中 / 数据说明);
5) 用 write_file 把完整 markdown 写到 briefings/{today}.md;
6) 用 write_file 把"推送信封"(含收件人、主题、正文摘要、链接) 写到 outbox/{today}.json (kind='outbox');
7) 最后用 bash 执行 `echo pushed {today}` 验证写入成功 (无网络)。
完成所有步骤后, 输出一句话总结即可。

BRIEFING_TEMPLATE 如下:
{BRIEFING_TEMPLATE}"""


def run_daily() -> dict:
    """跑一轮完整任务: 抓新闻 -> 写 outbox -> LLM 循环筛选/摘要/写简报/写推送。"""
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")

    # 1) 确定性抓取 (容错)
    try:
        fetch = news_engine.run()
    except Exception as e:
        fetch = {"file": str(OUTBOX / "today" / f"{today}.json"),
                 "ai_items": 0, "raw_items": 0,
                 "errors": [f"fetch failed: {e}"], "elapsed_sec": 0}

    profile = profile_store.load()

    # 2) 让模型驱动工具循环去筛选/摘要/写简报/写推送
    user_prompt = _build_user_prompt(profile, fetch["file"], today)
    system = (
        "你是用户的私人 AI 新闻编辑。你有 5 个工具: list_dir/read_file/search_content/write_file/bash。"
        "请自主决定调用顺序与次数: 先读数据, 必要时用 search_content 按关键词找重点, "
        "最后 write_file 写简报与推送文件, 再用 bash 验证。全部完成后停止。"
    )
    trace_path = str(LOGS / f"trace-{today}.json")
    res = react_loop(user_prompt, system, trace_path=trace_path)

    return {
        "date": today,
        "briefing_path": str(BRIEFINGS / f"{today}.md"),
        "push_path": str(PUSH / f"{today}.json"),
        "trace_path": trace_path,
        "fetch": fetch,
        "llm": {"rounds": res["rounds"], "tool_calls": len(res["tool_calls"]),
                 "final": res["final_text"][:500]},
    }


if __name__ == "__main__":
    out = run_daily()
    print(json.dumps(out, ensure_ascii=False, indent=1))
