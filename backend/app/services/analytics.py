import asyncio
import logging
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import pandas as pd

    _PANDAS_AVAILABLE = True
except ImportError:
    _PANDAS_AVAILABLE = False

logger = logging.getLogger(__name__)


def _is_pandas_available() -> bool:
    return _PANDAS_AVAILABLE


def _parse_iso_timestamp(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _filter_by_time_range(
    records: List[Dict[str, Any]],
    time_field: str,
    time_range: Optional[Dict[str, str]],
) -> List[Dict[str, Any]]:
    if not time_range:
        return records

    start = _parse_iso_timestamp(time_range.get("start"))
    end = _parse_iso_timestamp(time_range.get("end"))
    if start is None and end is None:
        return records

    filtered = []
    for record in records:
        ts = _parse_iso_timestamp(record.get(time_field))
        if ts is None:
            continue
        if start is not None and ts < start:
            continue
        if end is not None and ts > end:
            continue
        filtered.append(record)
    return filtered


class DataAggregator:
    """轻量级数据聚合器：优先使用 pandas，未安装时回退到原生 Python。"""

    def __init__(self):
        self._pandas_available = _is_pandas_available()

    def _to_dataframe(self, records: List[Dict[str, Any]]) -> Any:
        if not self._pandas_available:
            raise RuntimeError("pandas is not available")
        return pd.DataFrame(records)

    def group_by_count(
        self,
        records: List[Dict[str, Any]],
        key: str,
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        if self._pandas_available:
            df = self._to_dataframe(records)
            if key not in df.columns:
                return []
            series = df[key].value_counts()
            if top_k:
                series = series.head(top_k)
            return [{"name": str(k), "value": int(v)} for k, v in series.items()]

        counter = Counter(str(r.get(key, "未知")) for r in records)
        items = counter.most_common(top_k) if top_k else counter.most_common()
        return [{"name": k, "value": v} for k, v in items]

    def numeric_stats(
        self,
        records: List[Dict[str, Any]],
        key: str,
    ) -> Dict[str, Any]:
        values = []
        for record in records:
            try:
                values.append(float(record.get(key, 0)))
            except (TypeError, ValueError):
                continue

        if not values:
            return {"count": 0, "min": 0, "max": 0, "mean": 0, "median": 0, "total": 0}

        values.sort()
        n = len(values)
        total = sum(values)
        mean = total / n
        median = values[n // 2] if n % 2 else (values[n // 2 - 1] + values[n // 2]) / 2

        if self._pandas_available:
            df = self._to_dataframe(records)
            if key in df.columns:
                try:
                    col = pd.to_numeric(df[key], errors="coerce").dropna()
                    return {
                        "count": int(col.count()),
                        "min": float(col.min()),
                        "max": float(col.max()),
                        "mean": float(col.mean()),
                        "median": float(col.median()),
                        "total": float(col.sum()),
                    }
                except Exception as e:
                    logger.debug("Pandas numeric summary failed for key %s: %s", key, e)

        return {
            "count": n,
            "min": values[0],
            "max": values[-1],
            "mean": mean,
            "median": median,
            "total": total,
        }

    def time_series_count(
        self,
        records: List[Dict[str, Any]],
        time_field: str,
        freq: str = "day",
    ) -> List[Dict[str, Any]]:
        if not records:
            return []

        if self._pandas_available:
            df = self._to_dataframe(records)
            if time_field not in df.columns:
                return []
            try:
                df[time_field] = pd.to_datetime(df[time_field], errors="coerce", utc=True)
                df = df.dropna(subset=[time_field])
                if df.empty:
                    return []
                freq_map = {"day": "D", "week": "W-MON", "month": "ME"}
                grouper = pd.Grouper(key=time_field, freq=freq_map.get(freq, "D"))
                series = df.groupby(grouper).size().sort_index()
                return [
                    {"date": str(k.date() if hasattr(k, "date") else k), "value": int(v)}
                    for k, v in series.items()
                ]
            except Exception as e:
                logger.warning("pandas time series aggregation failed: %s", e)

        fmt_map = {
            "day": "%Y-%m-%d",
            "week": "%Y-W%W",
            "month": "%Y-%m",
        }
        fmt = fmt_map.get(freq, "%Y-%m-%d")
        counter: Counter = Counter()
        for record in records:
            ts = _parse_iso_timestamp(record.get(time_field))
            if ts:
                counter[ts.strftime(fmt)] += 1
        return [{"date": k, "value": v} for k, v in sorted(counter.items())]

    def distribution_bins(
        self,
        records: List[Dict[str, Any]],
        key: str,
        bins: int = 5,
    ) -> List[Dict[str, Any]]:
        if not records:
            return []

        values = []
        for record in records:
            try:
                values.append(float(record.get(key, 0)))
            except (TypeError, ValueError):
                continue

        if not values:
            return []

        if self._pandas_available:
            df = self._to_dataframe(records)
            if key in df.columns:
                try:
                    series = pd.to_numeric(df[key], errors="coerce").dropna()
                    if series.empty:
                        return []
                    counts, edges = pd.cut(series, bins=bins, retbins=True)
                    return [
                        {
                            "range": f"{float(edges[i]):.1f}-{float(edges[i + 1]):.1f}",
                            "value": int(counts.value_counts().sort_index().iloc[i]),
                        }
                        for i in range(len(edges) - 1)
                    ]
                except Exception as e:
                    logger.warning("pandas binning failed: %s", e)

        values.sort()
        n = len(values)
        min_v, max_v = values[0], values[-1]
        step = (max_v - min_v) / bins if max_v > min_v else 1
        result = []
        for i in range(bins):
            lo = min_v + i * step
            hi = min_v + (i + 1) * step if i < bins - 1 else max_v + 1
            count = sum(1 for v in values if lo <= v < hi)
            result.append({"range": f"{lo:.1f}-{hi:.1f}", "value": count})
        return result


aggregator = DataAggregator()


class AnalyticsService:
    """RAG 系统数据分析服务。"""

    def __init__(self):
        self._aggregator = aggregator

    async def analyze_documents(
        self,
        chunks: List[Dict[str, Any]],
        request: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        request = request or {}
        time_range = request.get("time_range")
        group_by = request.get("group_by", "file_type")

        records = []
        for chunk in chunks:
            metadata = chunk.get("metadata", {}) or {}
            record = {
                "chunk_id": chunk.get("chunk_id", ""),
                "document_id": metadata.get("document_id", ""),
                "filename": metadata.get("filename", "未知"),
                "file_type": metadata.get("file_type", "unknown"),
                "file_size": metadata.get("file_size", 0),
                "department": metadata.get("department", "未分类"),
                "classification": metadata.get("classification", "internal"),
                "upload_time": metadata.get("upload_time", ""),
            }
            records.append(record)

        records = _filter_by_time_range(records, "upload_time", time_range)
        if not records:
            return {
                "metric": "documents",
                "summary": {"total_documents": 0, "total_chunks": 0},
                "series": [],
            }

        def _build():
            doc_map: Dict[str, Dict[str, Any]] = {}
            for record in records:
                doc_id = record["document_id"]
                if not doc_id:
                    continue
                if doc_id not in doc_map:
                    doc_map[doc_id] = {
                        "document_id": doc_id,
                        "filename": record["filename"],
                        "file_type": record["file_type"],
                        "file_size": record["file_size"],
                        "department": record["department"],
                        "classification": record["classification"],
                        "upload_time": record["upload_time"],
                        "chunks_count": 0,
                    }
                doc_map[doc_id]["chunks_count"] += 1

            documents = list(doc_map.values())
            group_series = self._aggregator.group_by_count(documents, group_by)
            size_stats = self._aggregator.numeric_stats(documents, "file_size")
            chunk_stats = self._aggregator.numeric_stats(documents, "chunks_count")
            upload_trend = self._aggregator.time_series_count(documents, "upload_time", freq="day")
            size_dist = self._aggregator.distribution_bins(documents, "file_size", bins=5)

            return {
                "metric": "documents",
                "summary": {
                    "total_documents": len(documents),
                    "total_chunks": sum(d["chunks_count"] for d in documents),
                    "file_type_count": len(group_series),
                    "avg_file_size_bytes": size_stats["mean"],
                    "avg_chunks_per_document": chunk_stats["mean"],
                },
                "series": group_series,
                "detail": {
                    "file_size_stats": size_stats,
                    "chunks_per_document_stats": chunk_stats,
                    "upload_trend": upload_trend,
                    "file_size_distribution": size_dist,
                },
            }

        return await asyncio.to_thread(_build)

    async def analyze_conversations(
        self,
        conversations: List[Dict[str, Any]],
        request: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        request = request or {}
        time_range = request.get("time_range")
        group_by = request.get("group_by", "day")

        records = []
        for conversation in conversations:
            records.append({
                "conversation_id": conversation.get("conversation_id", ""),
                "created_at": conversation.get("created_at", ""),
                "last_updated": conversation.get("last_updated", ""),
                "turn_count": conversation.get("turn_count", 0),
            })

        records = _filter_by_time_range(records, "created_at", time_range)
        if not records:
            return {
                "metric": "conversations",
                "summary": {"total_conversations": 0, "total_turns": 0},
                "series": [],
            }

        def _build():
            turn_stats = self._aggregator.numeric_stats(records, "turn_count")
            created_trend = self._aggregator.time_series_count(records, "created_at", freq=group_by)
            updated_trend = self._aggregator.time_series_count(records, "last_updated", freq=group_by)
            turn_dist = self._aggregator.distribution_bins(records, "turn_count", bins=5)

            return {
                "metric": "conversations",
                "summary": {
                    "total_conversations": len(records),
                    "total_turns": int(turn_stats["total"]),
                    "avg_turns_per_conversation": turn_stats["mean"],
                    "max_turns": turn_stats["max"],
                },
                "series": created_trend,
                "detail": {
                    "turn_count_stats": turn_stats,
                    "created_trend": created_trend,
                    "last_updated_trend": updated_trend,
                    "turn_distribution": turn_dist,
                },
            }

        return await asyncio.to_thread(_build)

    async def analyze_tasks(
        self,
        tasks: List[Dict[str, Any]],
        request: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        request = request or {}
        time_range = request.get("time_range")
        group_by = request.get("group_by", "status")

        records = []
        for task in tasks:
            created = task.get("created_at", 0)
            finished = task.get("finished_at")
            duration = None
            if created and finished:
                duration = max(0.0, finished - created)
            records.append({
                "task_id": task.get("task_id", ""),
                "name": task.get("name", "unknown"),
                "status": task.get("status", "pending"),
                "created_at": created,
                "finished_at": finished,
                "duration": duration,
                "retry_count": task.get("retry_count", 0),
            })

        records = _filter_by_time_range(records, "created_at", time_range)
        if not records:
            return {
                "metric": "tasks",
                "summary": {"total_tasks": 0},
                "series": [],
            }

        def _build():
            status_series = self._aggregator.group_by_count(records, "status")
            name_series = self._aggregator.group_by_count(records, "name", top_k=10)
            duration_stats = self._aggregator.numeric_stats(records, "duration")
            retry_stats = self._aggregator.numeric_stats(records, "retry_count")
            created_trend = self._aggregator.time_series_count(records, "created_at", freq="day")

            total = len(records)
            completed = sum(1 for r in records if r["status"] == "completed")
            failed = sum(1 for r in records if r["status"] == "failed")

            return {
                "metric": "tasks",
                "summary": {
                    "total_tasks": total,
                    "completed": completed,
                    "failed": failed,
                    "success_rate": round(completed / total, 4) if total else 0,
                    "avg_duration_seconds": duration_stats["mean"],
                    "avg_retry_count": retry_stats["mean"],
                },
                "series": status_series if group_by == "status" else name_series,
                "detail": {
                    "status_distribution": status_series,
                    "top_task_names": name_series,
                    "duration_stats": duration_stats,
                    "retry_stats": retry_stats,
                    "created_trend": created_trend,
                },
            }

        return await asyncio.to_thread(_build)

    async def analyze_graph(
        self,
        graph_searcher: Any,
        request: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        request = request or {}
        top_k = request.get("top_k", 20)

        entity_index = getattr(graph_searcher, "_entity_index", {}) or {}
        relation_index = getattr(graph_searcher, "_relation_index", {}) or {}
        doc_chunks = getattr(graph_searcher, "_doc_chunks", {}) or {}

        records = []
        for entity_name, chunk_ids in entity_index.items():
            records.append({
                "entity": entity_name,
                "chunk_count": len(chunk_ids),
                "document_count": len({cid.split("_")[0] for cid in chunk_ids if "_" in cid}),
            })

        def _build():
            top_entities = self._aggregator.group_by_count(records, "entity", top_k=top_k)
            chunk_count_stats = self._aggregator.numeric_stats(records, "chunk_count")

            relation_count = sum(len(relations) for relations in relation_index.values())

            return {
                "metric": "graph",
                "summary": {
                    "total_entities": len(entity_index),
                    "total_relations": relation_count,
                    "documents_with_graph": len(doc_chunks),
                    "avg_chunks_per_entity": chunk_count_stats["mean"],
                },
                "series": top_entities,
                "detail": {
                    "chunk_count_stats": chunk_count_stats,
                    "entity_index": {
                        entity: len(chunk_ids)
                        for entity, chunk_ids in sorted(
                            entity_index.items(),
                            key=lambda x: len(x[1]),
                            reverse=True,
                        )[:top_k]
                    },
                },
            }

        return await asyncio.to_thread(_build)

    async def get_overview(
        self,
        chunks: List[Dict[str, Any]],
        conversations: List[Dict[str, Any]],
        tasks: List[Dict[str, Any]],
        graph_searcher: Any,
    ) -> Dict[str, Any]:
        doc_result = await self.analyze_documents(chunks)
        conv_result = await self.analyze_conversations(conversations)
        task_result = await self.analyze_tasks(tasks)
        graph_result = await self.analyze_graph(graph_searcher)

        return {
            "metric": "overview",
            "summary": {
                "total_documents": doc_result["summary"]["total_documents"],
                "total_chunks": doc_result["summary"]["total_chunks"],
                "total_conversations": conv_result["summary"]["total_conversations"],
                "total_turns": conv_result["summary"]["total_turns"],
                "total_tasks": task_result["summary"]["total_tasks"],
                "task_success_rate": task_result["summary"]["success_rate"],
                "graph_entities": graph_result["summary"]["total_entities"],
                "graph_relations": graph_result["summary"]["total_relations"],
            },
            "series": [],
            "detail": {
                "documents": doc_result,
                "conversations": conv_result,
                "tasks": task_result,
                "graph": graph_result,
            },
        }


analytics_service = AnalyticsService()
