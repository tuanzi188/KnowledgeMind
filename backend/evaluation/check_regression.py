"""检索评测回归门禁：CI 里跑，指标跌破基线就失败。

设计目标：
  - 不依赖 LLM（不需要 API key，CI 可跑）
  - 不依赖 ChromaDB（走 lightweight 内存索引，秒级完成）
  - 结果确定：同代码同语料同 embedding，指标稳定

用法：
    python -m evaluation.check_regression                  # 对比基线，跌破则 exit 1
    python -m evaluation.check_regression --update-baseline  # 把当前结果写成新基线
    python -m evaluation.check_regression --tol 0.01         # 自定义容差（默认 0.02）

基线文件：backend/evaluation/baseline_retrieval.json
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_BASELINE = Path(__file__).resolve().parent / "baseline_retrieval.json"
_REPORT = _BACKEND_DIR / "eval_report.json"

# 参与门禁的指标（key 对应 eval_report.json 的 summary.final）
METRICS = ["recall@1", "recall@3", "recall@5", "mrr@5", "ndcg@5", "hit@3"]


def _run_eval() -> dict:
    """跑一次 lightweight 评测并读取报告。"""
    cmd = [
        sys.executable, "-m", "evaluation.run_eval",
        "--pipeline", "lightweight",
        "--skip-generation",
        "--rerank-strategy", "none",
    ]
    print(">", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=str(_BACKEND_DIR), capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        print(proc.stdout[-3000:])
        print(proc.stderr[-3000:], file=sys.stderr)
        raise SystemExit(f"评测执行失败，退出码 {proc.returncode}")
    if not _REPORT.exists():
        raise SystemExit("评测未生成 eval_report.json")
    return json.loads(_REPORT.read_text(encoding="utf-8"))


def _current_metrics(report: dict) -> dict:
    final = (report.get("summary") or {}).get("final") or {}
    return {k: float(final[k]) for k in METRICS if k in final}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tol", type=float, default=0.02, help="允许的绝对下降幅度，默认 0.02")
    ap.add_argument("--update-baseline", action="store_true", help="把当前结果写成新基线")
    args = ap.parse_args()

    report = _run_eval()
    current = _current_metrics(report)
    print(f"\n当前 pipeline={report.get('pipeline')} rerank={report.get('rerank_strategy')} "
          f"corpus={report.get('corpus_chunks')} queries={report.get('queries')}")

    if args.update_baseline:
        _BASELINE.write_text(json.dumps({
            "pipeline": report.get("pipeline"),
            "rerank_strategy": report.get("rerank_strategy"),
            "corpus_chunks": report.get("corpus_chunks"),
            "queries": report.get("queries"),
            "metrics": current,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已写入基线：{_BASELINE}")
        return 0

    if not _BASELINE.exists():
        raise SystemExit(f"缺少基线文件 {_BASELINE}，请先运行 --update-baseline")

    baseline = json.loads(_BASELINE.read_text(encoding="utf-8")).get("metrics", {})

    print(f"\n{'指标':<10}{'基线':>10}{'当前':>10}{'变化':>10}  判定")
    failed = []
    for key in METRICS:
        if key not in baseline or key not in current:
            continue
        base, cur = baseline[key], current[key]
        delta = cur - base
        bad = delta < -args.tol
        if bad:
            failed.append((key, base, cur, delta))
        print(f"{key:<10}{base:>10.4f}{cur:>10.4f}{delta:>+10.4f}  {'✗ 回退' if bad else '✓'}")

    if failed:
        print(f"\n回归门禁未通过：{len(failed)} 项跌破容差 {args.tol}")
        for key, base, cur, delta in failed:
            print(f"  - {key}: {base:.4f} → {cur:.4f} ({delta:+.4f})")
        return 1

    print(f"\n回归门禁通过（容差 {args.tol}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
