# 核心 ReAct / function-calling 循环: 模型决定调哪个工具、调几次、何时停。
# 流程: 系统提示+用户偏好 -> 模型输出(文本 or tool_use) -> 执行工具 -> 回填结果 -> 再模型 ... 直到 stop_reason != tool_use。

import json
import time
from datetime import datetime

from agent_tools import TOOL_IMPLS, tool_schemas
import llm_client

MAX_ROUNDS = 12  # 安全上限, 防死循环


def _log(trace: list, event: dict):
    event["ts"] = datetime.now().isoformat(timespec="seconds")
    trace.append(event)


def react_loop(
    user_prompt: str,
    system: str,
    trace_path: str | None = None,
) -> dict:
    """运行工具调用循环, 返回 {final_text, trace, rounds, tool_calls}。
    trace 里记录每一步(思考/工具/结果), 供 UI 回放。"""
    trace: list[dict] = []
    messages: list[dict] = [{"role": "user", "content": user_prompt}]
    final_text = ""
    rounds = 0
    tool_calls: list[dict] = []

    for _ in range(MAX_ROUNDS):
        rounds += 1
        _log(trace, {"round": rounds, "event": "llm_call"})
        data = llm_client.messages_call(system, messages, tools=tool_schemas())
        content = data.get("content", [])
        stop = data.get("stop_reason", "end_turn")

        # assistant 消息回填
        assistant_msg = {"role": "assistant", "content": content}
        messages.append(assistant_msg)
        _log(trace, {"round": rounds, "event": "assistant", "stop_reason": stop, "content": content})

        tool_uses = llm_client.extract_tool_uses(content)
        if stop != "tool_use" or not tool_uses:
            final_text = llm_client.extract_text(content) or final_text
            break

        # 逐个执行工具
        results: list[str] = []
        for tu in tool_uses:
            name, args = tu["name"], tu["input"]
            _log(trace, {"round": rounds, "event": "tool_call", "tool": name, "args": args})
            impl = TOOL_IMPLS.get(name)
            if impl is None:
                res_str = json.dumps({"ok": False, "error": f"unknown tool {name}"})
            else:
                try:
                    out = impl(**args)
                    res_str = json.dumps(out, ensure_ascii=False, default=str)
                except Exception as e:  # 工具异常不能让循环崩掉
                    res_str = json.dumps({"ok": False, "error": str(e)})
            results.append(res_str)
            tool_calls.append({"tool": name, "args": args, "result_head": res_str[:200]})
            _log(trace, {"round": rounds, "event": "tool_result", "tool": name, "head": res_str[:200]})

        # 把 tool_result 作为 user 消息回填
        messages.append(
            {"role": "user", "content": llm_client.tool_result_blocks(tool_uses, results)}
        )

    if trace_path:
        with open(trace_path, "w", encoding="utf-8") as f:
            json.dump(trace, f, ensure_ascii=False, indent=1)

    return {"final_text": final_text, "trace": trace, "rounds": rounds, "tool_calls": tool_calls}


if __name__ == "__main__":
    r = react_loop(
        "列出 outbox/today 下有什么新闻文件。",
        system="你是新闻 Agent, 请用工具完成, 最后用一句话总结。",
    )
    print(r["final_text"], "| rounds:", r["rounds"], "| calls:", len(r["tool_calls"]))
