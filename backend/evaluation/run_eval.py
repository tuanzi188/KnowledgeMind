import argparse
import asyncio
import json
import re
import sys
import tempfile
from pathlib import Path

import numpy as np

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.config import MODEL_MODE, MODEL_PROVIDER
from app.services.embedding import get_embedding
from app.services.keyword_search import BM25Searcher
from app.services.hybrid_search import HybridRetriever
from app.services.model_provider import rag_query as model_rag_query
from app.services.model_provider import simple_query as model_simple_query

from evaluation.metrics import mrr_at_k, ndcg_at_k, recall_at_k
from evaluation.sample_data import CORPUS, QA_PAIRS

_JUDGE_SYSTEM = "你是知识库回答质量评估员，只输出 JSON，不要输出其他内容。"

_JUDGE_TEMPLATE = (
    "请评估下面问答的质量，输出 JSON 对象，包含两个 0 到 1 之间的小数：\n"
    "1. faithfulness：回答是否完全基于『参考资料』、没有编造资料外的事实（1=完全基于资料，0=完全编造）。\n"
    "2. relevancy：回答是否直接切题、回答了用户问题（1=完全切题，0=无关）。\n\n"
    "用户问题：{query}\n\n"
    "参考资料：\n{context}\n\n"
    "回答：\n{answer}\n\n"
    '只输出：{{"faithfulness": 0.0, "relevancy": 0.0}}'
)


def _dense_search(query_vec, corpus_vecs, corpus, top_k):
    q = np.asarray(query_vec, dtype=np.float32)
    matrix = np.asarray(corpus_vecs, dtype=np.float32)
    query_norm = np.linalg.norm(q)
    doc_norms = np.linalg.norm(matrix, axis=1)
    similarities = (matrix @ q) / (doc_norms * query_norm + 1e-9)

    results = []
    for index in np.argsort(-similarities)[:top_k]:
        item = dict(corpus[index])
        item["score"] = float(similarities[index])
        item["source"] = "vector"
        results.append(item)
    return results


def _bm25_search(bm25, query, top_k):
    return bm25.search(query, top_k=top_k, fuzzy_match=False)


def _fuse(vector_results, keyword_results, top_k, query_type="综合分析"):
    hybrid = HybridRetriever()
    weights = hybrid.weight_profiles.get(query_type, hybrid.weight_profiles["综合分析"])
    return hybrid.rrf_fuse(
        [vector_results, keyword_results],
        weights=[weights.get("vector", 0.4), weights.get("keyword", 0.3)],
        top_k=top_k,
    )


def _has_llm():
    mode = (MODEL_MODE or "").strip().lower()
    if mode in {"ollama", "local"}:
        return True
    try:
        if MODEL_PROVIDER == "qwen":
            from app.services.qwen_client import qwen_client
            return bool(getattr(qwen_client, "clients", {}))
        from app.services.deepseek import deepseek_client
        return bool(getattr(deepseek_client, "clients", {}))
    except Exception:
        return False


def _item_title(item):
    meta = item.get("metadata") or {}
    return item.get("title") or meta.get("title") or item.get("doc_id") or "未知文档"


def _format_context(items):
    parts = []
    for index, item in enumerate(items, 1):
        title = _item_title(item)
        parts.append(f"[{index}] {title}:\n{item.get('content', '')}")
    return "\n\n".join(parts)


async def _generate_answer(query, context):
    answer, _reasoning, _usage = await model_rag_query(query, context, reasoning_mode="flash")
    return answer


def _parse_judge_json(content):
    cleaned = content.strip()
    cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)
    return json.loads(cleaned)


async def _judge(query, answer, context):
    prompt = _JUDGE_TEMPLATE.format(query=query, context=context, answer=answer)
    content, _reasoning, _usage = await model_simple_query(prompt, _JUDGE_SYSTEM)
    data = _parse_judge_json(content)
    faith = min(max(float(data.get("faithfulness", 0.0)), 0.0), 1.0)
    relev = min(max(float(data.get("relevancy", 0.0)), 0.0), 1.0)
    return faith, relev


def _avg(rows, key):
    values = [row[key] for row in rows if key in row]
    return sum(values) / len(values) if values else float("nan")


def _print_report(rows, top_k, use_generation, embedding):
    print(f"\n=== 效果评测报告 (top_k={top_k}) ===")
    print(f"语料 {len(CORPUS)} 个 chunk，问答 {len(rows)} 条，embedding={embedding.version_tag}")

    header = ["query_type", "query", "recall@1", "recall@3", "recall@5", "mrr@5", "ndcg@5"]
    if use_generation:
        header += ["faithfulness", "relevancy"]
    print(" | ".join(header))

    for row in rows:
        cells = [
            row.get("query_type", "-"),
            row["query"],
            f"{row['recall@1']:.2f}",
            f"{row['recall@3']:.2f}",
            f"{row['recall@5']:.2f}",
            f"{row['mrr@5']:.2f}",
            f"{row['ndcg@5']:.2f}",
        ]
        if use_generation:
            cells += [f"{row['faithfulness']:.2f}", f"{row['relevancy']:.2f}"]
        print(" | ".join(cells))

    print("\n--- 总体平均 ---")
    print(f"recall@1 = {_avg(rows, 'recall@1'):.3f}")
    print(f"recall@3 = {_avg(rows, 'recall@3'):.3f}")
    print(f"recall@5 = {_avg(rows, 'recall@5'):.3f}")
    print(f"mrr@5    = {_avg(rows, 'mrr@5'):.3f}")
    print(f"ndcg@5   = {_avg(rows, 'ndcg@5'):.3f}")

    print("\n--- 分场景统计 ---")
    by_type = {}
    for row in rows:
        by_type.setdefault(row.get("query_type", "-"), []).append(row)
    print(f"{'场景':<8} {'条数':>4} {'recall@5':>10} {'mrr@5':>8} {'ndcg@5':>8}")
    for qtype, group in by_type.items():
        print(f"{qtype:<8} {len(group):>4} {_avg(group, 'recall@5'):>10.3f} {_avg(group, 'mrr@5'):>8.3f} {_avg(group, 'ndcg@5'):>8.3f}")

    if use_generation:
        print(f"\nfaithfulness = {_avg(rows, 'faithfulness'):.3f}")
        print(f"relevancy    = {_avg(rows, 'relevancy'):.3f}")
    else:
        print("\n生成指标未跑（未配置 LLM API key 或已跳过）")

    report_path = _BACKEND_DIR / "eval_report.json"
    with open(report_path, "w", encoding="utf-8") as report_file:
        json.dump({
            "embedding": embedding.version_tag,
            "summary": {
                "recall@5": _avg(rows, "recall@5"),
                "mrr@5": _avg(rows, "mrr@5"),
                "ndcg@5": _avg(rows, "ndcg@5"),
            },
            "rows": rows,
        }, report_file, ensure_ascii=False, indent=2)
    print(f"\n报告已写入：{report_path}")


async def run(top_k, skip_generation):
    embedding = get_embedding()
    corpus_vecs = embedding.embed([item["content"] for item in CORPUS])
    query_vecs = embedding.embed([qa["query"] for qa in QA_PAIRS])

    bm25 = BM25Searcher()
    bm25._tokenizer.user_dict_path = Path(tempfile.mkdtemp(prefix="km_eval_")) / "user_dict.txt"
    bm25.build_index([
        {
            "chunk_id": item["chunk_id"],
            "doc_id": item["doc_id"],
            "content": item["content"],
            "metadata": {"document_id": item["doc_id"], "title": item["title"]},
        }
        for item in CORPUS
    ])

    use_generation = (not skip_generation) and _has_llm()
    if skip_generation:
        print("已跳过生成评测（--skip-generation）")

    rows = []
    for index, qa in enumerate(QA_PAIRS):
        vector_results = _dense_search(query_vecs[index], corpus_vecs, CORPUS, top_k)
        keyword_results = _bm25_search(bm25, qa["query"], top_k)
        fused = _fuse(vector_results, keyword_results, top_k, query_type=qa.get("query_type", "综合分析"))
        retrieved_ids = [item["chunk_id"] for item in fused]

        row = {
            "query_type": qa.get("query_type", "综合分析"),
            "query": qa["query"],
            "relevant": qa["relevant_chunk_ids"],
            "retrieved": retrieved_ids,
            "recall@1": recall_at_k(retrieved_ids, qa["relevant_chunk_ids"], 1),
            "recall@3": recall_at_k(retrieved_ids, qa["relevant_chunk_ids"], 3),
            "recall@5": recall_at_k(retrieved_ids, qa["relevant_chunk_ids"], 5),
            "mrr@5": mrr_at_k(retrieved_ids, qa["relevant_chunk_ids"], 5),
            "ndcg@5": ndcg_at_k(retrieved_ids, qa["relevant_chunk_ids"], 5),
        }

        if use_generation:
            context = _format_context(fused)
            answer = await _generate_answer(qa["query"], context)
            faith, relev = await _judge(qa["query"], answer, context)
            row["faithfulness"] = faith
            row["relevancy"] = relev
            row["answer"] = answer[:120]
        rows.append(row)

    _print_report(rows, top_k, use_generation, embedding)


def main():
    parser = argparse.ArgumentParser(description="KnowledgeMind 效果评测（轻量自建）")
    parser.add_argument("--top-k", type=int, default=5, help="检索返回的 top-k 数量")
    parser.add_argument("--skip-generation", action="store_true", help="跳过生成评测，只跑检索指标")
    args = parser.parse_args()
    asyncio.run(run(args.top_k, args.skip_generation))


if __name__ == "__main__":
    main()