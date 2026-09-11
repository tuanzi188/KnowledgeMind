import logging
import re
import json
from pathlib import Path
from typing import List, Optional

from app.config import DATA_DIR

logger = logging.getLogger(__name__)
GRAPH_INDEX_DIR = DATA_DIR / "indexes"
GRAPH_INDEX_DIR.mkdir(parents=True, exist_ok=True)
GRAPH_INDEX_FILE = GRAPH_INDEX_DIR / "graph_index.json"


class GraphSearcher:
    def __init__(self, neo4j_uri: str | None = None, neo4j_user: str | None = None, neo4j_password: str | None = None):
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self._driver = None
        self._connected = False
        self._entity_index: dict[str, set[str]] = {}
        self._relation_index: dict[str, list[dict]] = {}
        self._doc_chunks: dict[str, list[str]] = {}

    def _ensure_connection(self):
        if self._connected or not self.neo4j_uri:
            return
        try:
            from neo4j import GraphDatabase
            self._driver = GraphDatabase.driver(
                self.neo4j_uri,
                auth=(self.neo4j_user, self.neo4j_password) if self.neo4j_user else None,
            )
            self._driver.verify_connectivity()
            self._connected = True
            logger.info("Neo4j connected: %s", self.neo4j_uri)
        except ImportError:
            logger.info("neo4j driver not installed, graph search unavailable")
        except Exception as e:
            logger.warning("Neo4j connection failed: %s", e)

    def add_entity(self, entity_name: str, chunk_ids: list[str], document_id: str = ""):
        for cid in chunk_ids:
            if entity_name not in self._entity_index:
                self._entity_index[entity_name] = set()
            self._entity_index[entity_name].add(cid)
        if document_id and chunk_ids:
            self._doc_chunks.setdefault(document_id, []).extend(chunk_ids)

    def add_relation(self, entity_a: str, entity_b: str, relation_type: str, chunk_ids: list[str]):
        key = f"{entity_a}||{entity_b}"
        if key not in self._relation_index:
            self._relation_index[key] = []
        self._relation_index[key].append({
            "entity_a": entity_a,
            "entity_b": entity_b,
            "relation": relation_type,
            "chunk_ids": chunk_ids,
        })

    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[dict] = None,
    ) -> List[dict]:
        if self._connected and self._driver:
            return await self._neo4j_search(query, top_k, filters)
        return self._memory_search(query, top_k, filters)

    async def _neo4j_search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[dict] = None,
    ) -> List[dict]:
        results = []
        try:
            from neo4j import GraphDatabase

            entities = self._extract_entities(query)
            if not entities:
                return []

            def do_query(tx, entity, limit):
                cypher = (
                    "MATCH (n)-[r]-(m) "
                    "WHERE n.name CONTAINS $entity OR m.name CONTAINS $entity "
                    "RETURN n.name AS node_a, type(r) AS relation, m.name AS node_b, "
                    "n.chunk_id AS chunk_id, n.doc_id AS doc_id "
                    "LIMIT $limit"
                )
                result = tx.run(cypher, entity=entity, limit=limit)
                return [dict(record) for record in result]

            for entity in entities[:3]:
                with self._driver.session() as session:
                    rows = session.execute_read(do_query, entity, top_k // max(len(entities), 1))
                    for row in rows:
                        if row.get("chunk_id"):
                            results.append({
                                "chunk_id": row["chunk_id"],
                                "doc_id": row.get("doc_id", ""),
                                "content": f"{row['node_a']} --[{row['relation']}]--> {row['node_b']}",
                                "metadata": {"entity": entity, "relation": row["relation"]},
                                "score": 0.5,
                                "source": "graph",
                            })
        except Exception as e:
            logger.error("Neo4j query failed: %s", e)
            return self._memory_search(query, top_k, filters)

        return results[:top_k]

    def _memory_search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[dict] = None,
    ) -> List[dict]:
        entities = self._extract_entities(query)
        if not entities:
            return []

        results = []
        seen = set()

        for entity in entities:
            if entity in self._entity_index:
                for chunk_id in self._entity_index[entity]:
                    if chunk_id not in seen:
                        seen.add(chunk_id)
                        results.append({
                            "chunk_id": chunk_id,
                            "doc_id": "",
                            "content": f"[实体关联: {entity}]",
                            "metadata": {"entity": entity, "relation_type": "entity_link"},
                            "score": 0.4,
                            "source": "graph",
                        })

        for key, relations in self._relation_index.items():
            entity_a, entity_b = key.split("||")
            if any(e in entities for e in (entity_a, entity_b)):
                for rel in relations:
                    for chunk_id in rel.get("chunk_ids", []):
                        if chunk_id not in seen:
                            seen.add(chunk_id)
                            results.append({
                                "chunk_id": chunk_id,
                                "doc_id": "",
                                "content": f"[{rel['entity_a']} -{rel['relation']}-> {rel['entity_b']}]",
                                "metadata": {
                                    "entity": entity_a,
                                    "related_entity": entity_b,
                                    "relation_type": rel["relation"],
                                },
                                "score": 0.45,
                                "source": "graph",
                            })

        return results[:top_k]

    def _extract_entities(self, text: str) -> list[str]:
        patterns = [
            r'[\u4e00-\u9fff]{2,6}(?:部门|公司|集团|市场|项目|团队|系统|平台|产品)',
            r'[\u4e00-\u9fff]{2,4}(?:经理|总监|总|主管|员|工)',
            r'(?:华东|华南|华北|华中|西南|西北|东北)[\u4e00-\u9fff]{0,4}',
            r'\d{4}年',
            r'(?:Q[1-4]|第[一二三四]季度)',
        ]
        entities = set()
        for pattern in patterns:
            matches = re.findall(pattern, text)
            entities.update(matches)

        if not entities:
            long_words = re.findall(r'[\u4e00-\u9fff]{3,8}', text)
            for w in long_words:
                if w not in {"根据资料", "参考资料", "无法确定", "用户问题"}:
                    entities.add(w)
            entities = set(list(entities)[:5])

        return list(entities)

    def extract_entities_from_text(self, text: str) -> list[dict]:
        entities = self._extract_entities(text)
        return [{"name": e, "type": "auto"} for e in entities]

    def delete_document(self, document_id: str):
        chunk_ids = set(self._doc_chunks.pop(document_id, []))
        if not chunk_ids:
            return
        for entity_name in list(self._entity_index.keys()):
            self._entity_index[entity_name] -= chunk_ids
            if not self._entity_index[entity_name]:
                del self._entity_index[entity_name]

    def close(self):
        if self._driver:
            self._driver.close()
            self._connected = False

    def reset_memory_index(self):
        self._entity_index = {}
        self._relation_index = {}
        self._doc_chunks = {}

    def save_to_disk(self, file_path: Path = GRAPH_INDEX_FILE):
        payload = {
            "version": 1,
            "entity_index": {entity_name: sorted(chunk_ids) for entity_name, chunk_ids in self._entity_index.items()},
            "relation_index": self._relation_index,
            "doc_chunks": self._doc_chunks,
        }
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as output_file:
            json.dump(payload, output_file, ensure_ascii=False)

    def load_from_disk(self, file_path: Path = GRAPH_INDEX_FILE) -> bool:
        if not file_path.exists():
            return False

        with open(file_path, "r", encoding="utf-8") as input_file:
            payload = json.load(input_file)

        persisted_entity_index = payload.get("entity_index", {})
        persisted_relation_index = payload.get("relation_index", {})
        persisted_doc_chunks = payload.get("doc_chunks", {})

        if not isinstance(persisted_entity_index, dict) or not isinstance(persisted_relation_index, dict):
            raise ValueError("Graph persisted payload is invalid")

        self._entity_index = {
            entity_name: set(chunk_ids)
            for entity_name, chunk_ids in persisted_entity_index.items()
            if isinstance(entity_name, str) and isinstance(chunk_ids, list)
        }
        self._relation_index = {
            relation_key: relation_list
            for relation_key, relation_list in persisted_relation_index.items()
            if isinstance(relation_key, str) and isinstance(relation_list, list)
        }
        self._doc_chunks = {
            document_id: chunk_ids
            for document_id, chunk_ids in persisted_doc_chunks.items()
            if isinstance(document_id, str) and isinstance(chunk_ids, list)
        }
        return True


graph_searcher = GraphSearcher()
