# 每日定时任务: 在指定时刻自动跑一次 orchestrator.run_daily()。
# 用 Python 原生调度 (不依赖 APScheduler), 每天 delivery.time 触发一次。

import datetime as dt
import time
import orchestrator
import profile_store


def next_run(time_str: str) -> float:
    """返回下次运行的 Unix 时间戳。"""
    h, m = map(int, time_str.split(":"))
    now = dt.datetime.now()
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if target <= now:
        target += dt.timedelta(days=1)
    return target.timestamp()


def main():
    print("[scheduler] start, daily run...")
    while True:
        t = profile_store.load().get("delivery", {}).get("time", "08:00")
        ts = next_run(t)
        wait = ts - time.time()
        print(f"[scheduler] next run in {int(wait/60)} min at {t}")
        time.sleep(max(wait, 60))  # 至少 60s 后才重新评估
        try:
            out = orchestrator.run_daily()
            print("[scheduler] done:", out["llm"])
        except Exception as e:
            print("[scheduler] run failed:", e)


if __name__ == "__main__":
    main()
