# 每日 AI 新闻简报 Agent

基于 Anthropic 兼容接口（`ANTHROPIC_BASE_URL` + `AGNES_API_KEY`）+ 手写 ReAct /
function-calling 循环的 AI 新闻 Agent。

## 架构

- **工具层**（`agent_tools.py`）：`list_dir` / `read_file` / `search_content` /
  `write_file` / `bash` 共 5 个工具，全部带路径沙箱（outbox / briefings / logs）
  与 bash 网络/危险命令拦截。
- **LLM 循环**（`agent_loop.py` + `llm_client.py`）：纯 function calling 循环，
  工具选择、调用次数、何时结束全部由模型（`agnes-3.0-flash`）决定，不写死线性流程。
  每一步的 LLM 输入/输出与工具调用都记录到 `logs/trace-YYYY-MM-DD.json`，可供 UI 回放。
- **新闻引擎**（`news_engine.py`）：多源聚合（OpenAI / Verge / Ars / MIT Tech Review /
  Google / Microsoft Research 等 8 个 RSS/Atom 源），清洗后按日期落到
  `outbox/today/YYYY-MM-DD.json`。
- **编排**（`orchestrator.py`）：确定性抓取 + 让模型自主完成筛选/摘要/写简报/
  写推送信封，跑完后把路径与工具调用统计返回。
- **调度**（`scheduler.py`）：独立进程，每天 `delivery.time` 自动触发一次
  `orchestrator.run_daily()`。
- **API + 前端**（`app.py` + `static/index.html`）：FastAPI 单页应用，三个标签页：
  ① 订阅偏好（身份 + 话题/关键词/排除词/语言/每份条数/推送时间），
  ② 历史简报（列表 + 正文查看），③ 生成 & 推送（手动触发 + 推送信封）。

## 运行

```bat
cd outputs\ai-news-agent
pip install -r requirements.txt
python app.py         # Web 服务: http://127.0.0.1:8000
python scheduler.py   # 终端里当常驻调度器（每天按 delivery.time 自动生成并推送）
```

- 简报正文：`briefings/YYYY-MM-DD.md`
- 推送信封：`outbox/YYYY-MM-DD.json`
- 工具调用轨迹：`logs/trace-YYYY-MM-DD.json`

## 前置条件

- Python 3.10+，`fastapi`、`uvicorn`（见 `requirements.txt`；`requests` 已在系统里）
- 环境变量：`ANTHROPIC_BASE_URL`、`AGNES_API_KEY`（默认 `OPENAI_API_KEY`），
  可选 `ANTHROPIC_MODEL`（默认 `agnes-3.0-flash`）

## 设计要点

- **LLM 自主**：抓取是确定性步骤（快而稳），但"读哪些文件、按什么关键词搜、
  写哪几份文件、何时停止"全部由模型在 `react_loop` 里自行决定，`MAX_ROUNDS=12`
  只是安全上限。
- **沙箱**：`safe_path` 把相对路径约束在三个沙箱根内；`bash` 工具用正则拒绝
  `curl/wget`，并限制 `cwd=briefings/`，防止模型破坏环境。
- **容错**：源不可达时跳过并在简报的"数据说明"中如实标注；全部不可达时仍生成
  一份"数据受限"简报。
- **可扩展**：推送渠道在 `profile.delivery.channel` 中预留，当前默认 `outbox`
  （本地文件），后续可加 email / webhook。

## 实测

- 工具调用：`read_file(outbox/today/…)` → `write_file(briefings/…)` →
  `write_file(outbox/…)` → `bash(echo pushed …)`，共 4 次调用，模型自行决定顺序。
- 简报质量：Top 3 + 按话题分组 + 关键词命中 + 数据说明，4 个区块，中文。
- 源可达性：8 个源中 6 个可达，2 个（Hugging Face Blog / Anthropic News）
  本轮不可达，已在简报中如实标注。
