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
- **数据库**（`database.py` + `db.sql`）：SQLite 层，首次连接自动执行 `db.sql` 建表，
  并把已有 `profile.json` 迁移进 `subscriptions` 表；每次 `run_daily` 把 LLM 轮数/工具调用/
  抓取条数落进 `briefings` 表。运行时 `db/news.db` 不进仓库（`.gitignore` 排除）。
- **API + 前端**（`app.py` + `static/index.html`）：FastAPI 单页应用，三个标签页：
  ① 订阅偏好（身份 + 话题/关键词/排除词/语言/每份条数/推送时间），
  ② 历史简报（列表 + 正文查看），③ 生成 & 推送（手动触发 + 推送信封）。
  数据库侧另有 `/api/subscriptions`、`/api/briefings/db`、`/api/db/stats`。

## 运行

```bat
cd ai-news-agent
:: Windows 一键起环境 (建 venv + 装依赖 + 起 Web)
setup.bat
:: 或手动
pip install -r requirements.txt
python app.py        # http://127.0.0.1:8000
python scheduler.py  # 常驻调度器, 每天按 delivery.time 自动生成并推送
```

```bash
# Linux / macOS 一键起环境
./run.sh
# 或手动
pip install -r requirements.txt
python app.py
```

- 简报正文：`briefings/YYYY-MM-DD.md`
- 推送信封：`outbox/YYYY-MM-DD.json`
- 工具调用轨迹：`logs/trace-YYYY-MM-DD.json`
- 数据库：`db/news.db`（运行时生成，不进仓库；建表脚本 `db.sql` 保留在仓库）

## 前置条件

- Python 3.10+，`fastapi`、`uvicorn`、`requests`（见 `requirements.txt`）
- 环境变量（密钥走环境变量，不硬编码）：
  - `AGNES_API_KEY` 或 `OPENAI_API_KEY` —— LLM 密钥
  - `ANTHROPIC_BASE_URL`（默认 `https://apihub.agnes-ai.com`）
  - 可选 `ANTHROPIC_MODEL`（默认 `agnes-3.0-flash`）
- 缺密钥时 LLM 调用会明确报 `LLMError`，不会把密钥写死进代码或日志。

## 设计要点

- **LLM 自主**：抓取是确定性步骤（快而稳），但"读哪些文件、按什么关键词搜、
  写哪几份文件、何时停止"全部由模型在 `react_loop` 里自行决定，`MAX_ROUNDS=12`
  只是安全上限。
- **沙箱**：`safe_path` 把相对路径约束在三个沙箱根内；`bash` 工具用正则拒绝
  `curl/wget`，并限制 `cwd=briefings/`，防止模型破坏环境。
- **容错**：源不可达时跳过并在简报"数据说明"中如实标注；全部不可达时仍生成
  一份"数据受限"简报。
- **可扩展**：推送渠道在 `profile.delivery.channel` 中预留，当前默认 `outbox`
  （本地文件），后续可加 email / webhook。

## 合规约束 · 达标情况

> 本节对应项目交付时"所有选项共同约束"的逐项核对。

| 项 | 要求 | 状态 |
| --- | --- | --- |
| Git | 使用 Git 进行版本管理，保留提交历史 | 本地 git 仓库，完整提交历史（工具层→ReAct→新闻引擎→调度→Web→SQLite/建表/一键脚本），远程 `origin` 已推 `main` |
| 配置 | 密钥走环境变量，不得硬编码 | 全文检索确认代码内无 `ghp_` / `github_pat` / API key / 个人邮箱等硬编码；LLM 密钥仅从 `AGNES_API_KEY`/`OPENAI_API_KEY` 环境变量读取 |
| 依赖 | 提供依赖清单，能一键起环境 | `requirements.txt`（fastapi/uvicorn/requests）+ 一键脚本 `setup.bat`（Windows）/ `run.sh`（Linux/macOS）；等价命令 `pip install -r requirements.txt && python app.py` |
| 数据库 | 提供建表 SQL 或 migration 脚本 | `db.sql`（CREATE TABLE：`subscriptions` / `briefings` / 索引）+ `database.py` 运行时自动 migration；生成的 `db/news.db` 由 `.gitignore` 排除 |

### 补充说明
- 若本地 remote URL 中曾包含个人凭据（GitHub token 等），推送前请 `git remote set-url origin https://github.com/<user>/ai-news-agent.git` 清掉 URL 里的 token。
- 本仓库为 public；如需私有或加入 `profile.json`（用户身份/订阅偏好），在 GitHub 设置仓库可见性即可。

## 实测

- 工具调用：`read_file(outbox/today/…)` → `write_file(briefings/…)` →
  `write_file(outbox/…)` → `bash(echo pushed …)`，模型自行决定顺序。
- 简报质量：Top 3 + 按话题分组 + 关键词命中 + 数据说明，四个区块，中文。
- 源可达性：8 个源中多数可达，个别源不可达时已在简报中如实标注。
- 数据库落表：一次 `run_daily` 后 `briefings` 表新增记录，`/api/db/stats` 返回
  `{"subscriptions":1,"briefings":1}`。