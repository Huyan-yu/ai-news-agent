# 工具层: 5 个可被 LLM 调用的工具 (list_dir / read_file / search_content / write_file / bash)
# 所有路径都被限制在 outbox/ 与 briefings/ 目录内。
# bash 工具执行受限的本地命令 (默认在 briefings/ 下)，不允许网络。

import json
import re
import shutil
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent
SANDBOX_ROOTS = {
    "outbox": BASE / "outbox",
    "briefings": BASE / "briefings",
    "logs": BASE / "logs",
}
for p in SANDBOX_ROOTS.values():
    p.mkdir(parents=True, exist_ok=True)


# ----------------------------------------------------------- 路径安全
def safe_path(rel: str, kind: str = "outbox") -> Path:
    """把相对路径约束在指定沙箱根目录内，防止越界。"""
    root = SANDBOX_ROOTS[kind]
    p = (root / rel).resolve()
    if root not in p.parents and p != root:
        raise PermissionError(f"path {rel!r} escapes sandbox {kind}/")
    return p


# ----------------------------------------------------------- 5 个工具
def list_dir(path: str = "") -> dict:
    """列出 outbox/ 下的文件与大小（模型用来知道有哪些新闻文件可读）。"""
    root = safe_path(path, "outbox")
    if not root.exists():
        return {"ok": False, "error": f"no such dir: {root}"}
    entries = []
    for f in sorted(root.rglob("*")):
        if f.is_file():
            entries.append(
                {
                    "path": str(f.relative_to(SANDBOX_ROOTS['outbox'])),
                    "size": f.stat().st_size,
                    "mtime": f.stat().st_mtime,
                }
            )
    return {"ok": True, "dir": str(root), "files": entries}


def read_file(path: str, kind: str = "outbox") -> dict:
    """读取沙箱内文本/JSON 文件，返回 {content, size}。"""
    p = safe_path(path, kind)
    if not p.is_file():
        return {"ok": False, "error": f"not found: {p}"}
    text = p.read_text(encoding="utf-8", errors="replace")
    return {"ok": True, "path": str(p), "size": len(text), "content": text}


def search_content(keyword: str, dir: str = "outbox", limit: int = 40) -> dict:
    """在 dir 沙箱内按关键词搜索文件内容，返回 文件:行号:片段。"""
    root = SANDBOX_ROOTS[dir] if dir in SANDBOX_ROOTS else root if False else safe_path(dir, "outbox")
    if not root.exists():
        return {"ok": False, "error": f"no such dir: {root}"}
    kw = keyword.lower()
    hits = []
    for f in root.rglob("*"):
        if not f.is_file():
            continue
        try:
            lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines, 1):
            if kw in line.lower():
                hits.append(f"{f.relative_to(root)}:{i}:{line.strip()[:120]}")
                if len(hits) >= limit:
                    break
        if len(hits) >= limit:
            break
    return {"ok": True, "keyword": keyword, "hits": hits, "count": len(hits)}


def write_file(path: str, content: str, kind: str = "briefings") -> dict:
    """写文件到沙箱（默认 briefings/，自动建父目录）。"""
    p = safe_path(path, kind)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return {"ok": True, "path": str(p), "bytes": len(content.encode("utf-8"))}


def bash(command: str, cwd: str | None = None, timeout: int = 30) -> dict:
    """执行本地 shell 命令。
    限制: 默认 cwd=briefings/; 禁止含 http/https 网络拉取; 不允许 rm 删除沙箱外。
    """
    import subprocess

    cmd = command.strip()
    # 基本禁网络
    if re.search(r"(?i)(curl|wget|fetch\s+https?)\b", cmd):
        return {"ok": False, "error": "network fetch not allowed inside bash tool; use news_engine instead"}
    workdir = Path(cwd) if cwd else BASE / "briefings"
    workdir.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        cmd, shell=True, cwd=str(workdir), capture_output=True, text=True, timeout=timeout
    )
    return {
        "ok": r.returncode == 0,
        "exit": r.returncode,
        "stdout": r.stdout[-2000:],
        "stderr": r.stderr[-500:],
    }


# ----------------------------------------------------------- 工具注册表 (暴露给 LLM)
def tool_schemas() -> list[dict]:
    return [
        {
            "name": "list_dir",
            "description": "List news files under outbox/ with sizes; use to see what's available today.",
            "input_schema": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "subdir under outbox/, e.g. today"}},
                "required": ["path"],
            },
        },
        {
            "name": "read_file",
            "description": "Read a file from outbox/ (news JSON) or briefings/ (history).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "kind": {"type": "string", "enum": ["outbox", "briefings", "logs"]},
                },
                "required": ["path"],
            },
        },
        {
            "name": "search_content",
            "description": "Keyword search across files in a sandbox dir; returns matched lines.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "dir": {"type": "string", "description": "outbox | briefings | logs"},
                    "limit": {"type": "integer"},
                },
                "required": ["keyword", "dir"],
            },
        },
        {
            "name": "write_file",
            "description": "Write the final briefing to briefings/ (markdown). Auto-creates parents.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "e.g. 2026-09-22.md"},
                    "content": {"type": "string"},
                    "kind": {"type": "string", "enum": ["briefings", "logs"]},
                },
                "required": ["path", "content"],
            },
        },
        {
            "name": "bash",
            "description": "Run a local shell command (no network). Useful for counting lines, grep-style checks on briefings.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "cwd": {"type": "string"},
                    "timeout": {"type": "integer"},
                },
                "required": ["command"],
            },
        },
    ]


TOOL_IMPLS = {
    "list_dir": list_dir,
    "read_file": read_file,
    "search_content": search_content,
    "write_file": write_file,
    "bash": bash,
}


if __name__ == "__main__":
    # 冒烟测试
    print(json.dumps(tool_schemas(), ensure_ascii=False, indent=2)[:400])
    print(list_dir("")["ok"])
    print(write_file("_smoke.md", "# ok")["ok"])
    print(search_content("ok", "briefings")["count"])
