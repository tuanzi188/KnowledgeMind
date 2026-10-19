# 检索链路实验

这里放的是**支撑「按场景选重排档位」这个设计决策的实验**，以及结论的可复现入口。

不是评测（评测在 `evaluation/` 根目录），是**归因实验**：用来回答"为什么这么设计""瓶颈在哪"。

## 四个实验

| 脚本 | 回答的问题 | 需要 LLM | 典型耗时 |
|---|---|---|---|
| `run_coverage_check.py` | 候选池是否已饱和？召回层还有没有优化空间？ | 是（查询改写） | 2–3 分钟 |
| `run_retrieval_matrix.py` | 单路向量 / 纯 BM25 / 三路融合 / 融合+改写，谁更好？ | 是（查询改写） | 3–5 分钟 |
| `run_rerank_matrix.py` | 不重排 / 规则 / Cross-Encoder / LLM 重排，效果、成本、延迟各是多少？ | 是（l3 档） | 8–15 分钟 |
| `run_failure_analysis.py` | 哪些查询答错了？是召回丢了还是排序没救回来？ | 是（查询改写） | 3–5 分钟 |

> 「需要 LLM」是指脚本会走线上链路的查询改写/LLM 重排。若想完全离线，
> 可把 `PROFILE` 对应的改写关掉（`QUERY_REWRITE_ENABLED=false`），但结果与线上不一致。

## 跑法

```bash
cd backend
python -m evaluation.experiments.run_coverage_check
python -m evaluation.experiments.run_retrieval_matrix
python -m evaluation.experiments.run_rerank_matrix
python -m evaluation.experiments.run_failure_analysis
```

结果默认写到 `experiments/out/*.json`。仓库里保留了一份 **2026-10-19 的运行结果**作为
[`RESULTS.md`](RESULTS.md) 与 [`FAILURE_CASES.md`](FAILURE_CASES.md) 的原始证据（含 LLM 非确定性，
重跑数值会有 ±3pt 波动）。

## 结果怎么读

结论汇总见 [`RESULTS.md`](RESULTS.md)。三条关键读法：

1. **看 `recall@候选数`，不只看 top-k**。候选池里已有正确答案却排不进 top-3，说明是排序问题，堆召回没用。
2. **看候选重合度**。重合度高（>90%）说明两种召回在选同一批东西，融合不会有新信息。
3. **看分场景（by_query_type）**。整体指标会被饱和场景稀释，增益通常只集中在 2–3 类查询上。

## 与 CI 的关系

CI 里的 `eval-regression` job 跑的是**轻量确定性评测**（`evaluation.check_regression`），不含本目录的实验——
因为实验需要 LLM，既慢又非确定。这里只用于人读的归因分析。
