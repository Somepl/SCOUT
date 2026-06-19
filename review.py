import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from storage import ScoutStorage
from config import DATA_DIR


def show_stats(storage):
    stats = storage.get_stats()
    if not stats:
        print("  暂无复盘数据", flush=True)
        return
    total = sum(stats.values())
    correct = stats.get("正确", 0)
    partial = stats.get("部分正确", 0)
    wrong = stats.get("错误", 0)
    print(f"  总复盘次数: {total}", flush=True)
    print(f"  判断正确: {correct} ({correct/total*100:.0f}%)" if total else "  判断正确: 0", flush=True)
    print(f"  部分正确: {partial} ({partial/total*100:.0f}%)" if total else "  部分正确: 0", flush=True)
    print(f"  判断错误: {wrong} ({wrong/total*100:.0f}%)" if total else "  判断错误: 0", flush=True)
    if correct + partial > 0:
        print(f"  有效准确率: {(correct+partial)/total*100:.0f}%", flush=True)
    print(flush=True)


def main():
    print(flush=True)
    print("=" * 58, flush=True)
    print("   [SCOUT] 预判复盘系统", flush=True)
    print("=" * 58, flush=True)
    print(flush=True)

    storage = ScoutStorage(DATA_DIR)

    print("【当前统计】", flush=True)
    show_stats(storage)

    unreviewed = storage.get_unreviewed(days=30)
    if not unreviewed:
        print("  ✅ 最近30天的预判已全部复盘", flush=True)
        print(flush=True)
        return

    total = len(unreviewed)
    print(f"  有待复盘: {total} 条", flush=True)
    print(flush=True)

    for idx, row in enumerate(unreviewed):
        aid, rdate, title, source, etype, conf, sentiment, advice, advice_reason, reason = row
        print("-" * 58, flush=True)
        print(f"  [{idx+1}/{total}] {rdate} | {source}", flush=True)
        print(f"  标题: {title[:60]}", flush=True)
        print(f"  判断: {etype} | 可信度:{conf} | 情绪:{sentiment} | 建议:{advice}", flush=True)
        if reason:
            print(f"  理由: {reason}", flush=True)
        print(flush=True)

        while True:
            print("  实际结果如何？ (1=正确  2=部分正确  3=错误  0=跳过)", flush=True)
            try:
                inp = input("  > ").strip()
            except (EOFError, KeyboardInterrupt):
                print(flush=True)
                print("  复盘已中断", flush=True)
                return

            if inp == "0":
                break
            elif inp in ("1", "2", "3"):
                mapping = {"1": "正确", "2": "部分正确", "3": "错误"}
                outcome = mapping[inp]
                detail = input("  备注（可选，直接回车跳过）: ").strip()
                storage.save_review(aid, outcome, detail)
                print(f"  ✅ 已记录: {outcome}", flush=True)
                print(flush=True)
                break
            else:
                print("  请输入 1/2/3/0", flush=True)

    print(flush=True)
    print("【复盘完成，最新统计】", flush=True)
    show_stats(storage)
    print("=" * 58, flush=True)
    print(flush=True)


if __name__ == "__main__":
    main()
