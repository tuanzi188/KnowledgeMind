import json
import logging
import math
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

from app.config import DATA_DIR, TOKENIZER_CONFIG
from app.services.filter_utils import match_filters

logger = logging.getLogger(__name__)

bm25_searcher: Optional["BM25Searcher"] = None
BM25_INDEX_DIR = DATA_DIR / "indexes"
BM25_INDEX_DIR.mkdir(parents=True, exist_ok=True)
BM25_INDEX_FILE = BM25_INDEX_DIR / "bm25_index.json"

TOKENIZER_DIR = DATA_DIR / "tokenizer"
TOKENIZER_DIR.mkdir(parents=True, exist_ok=True)
USER_DICT_FILE = Path(TOKENIZER_CONFIG.get("user_dict_path", str(TOKENIZER_DIR / "user_dict.txt")))
USER_DICT_FILE.parent.mkdir(parents=True, exist_ok=True)


def get_bm25_searcher() -> "BM25Searcher":
    global bm25_searcher
    if bm25_searcher is None:
        bm25_searcher = BM25Searcher()
    return bm25_searcher


DEFAULT_SYNONYMS: Dict[str, list[str]] = {
    "销售额": ["营收", "收入", "销售收入"],
    "公司": ["企业", "集团", "组织"],
    "员工": ["职员", "雇员", "同事", "人员"],
    "制度": ["规定", "规章", "规范", "政策"],
    "项目": ["工程", "计划", "任务"],
    "预算": ["经费", "资金", "费用"],
    "考核": ["评估", "评价", "考评"],
    "培训": ["学习", "教育", "研修"],
}

STOPWORDS = {
    "的", "了", "和", "与", "及", "或", "在", "对", "按", "把", "将", "是", "为",
    "并", "中", "上", "下", "个", "各", "后", "前", "及其", "进行", "有关", "关于",
}


class ChineseTokenizer:
    def __init__(self, user_dict_path: Path):
        self.user_dict_path = user_dict_path
        self._jieba_module = None
        self._loaded_user_dict_words: set[str] = set()
        self._initialize_tokenizer()

    def _initialize_tokenizer(self):
        if not TOKENIZER_CONFIG.get("enable_jieba", True):
            logger.info("Jieba tokenizer disabled by configuration, fallback tokenizer will be used")
            return

        try:
            import jieba

            self._jieba_module = jieba
            if self.user_dict_path.exists():
                jieba.load_userdict(str(self.user_dict_path))
                self._loaded_user_dict_words = self._read_user_dict_words()
            logger.info("Chinese tokenizer initialized with jieba, user_dict=%s", self.user_dict_path)
        except Exception as tokenizer_init_error:
            self._jieba_module = None
            logger.warning(
                "Failed to initialize jieba tokenizer: %s. Fallback tokenizer will be used.",
                tokenizer_init_error,
            )

    def _read_user_dict_words(self) -> set[str]:
        if not self.user_dict_path.exists():
            return set()

        loaded_words: set[str] = set()
        with open(self.user_dict_path, "r", encoding="utf-8") as user_dict_input_file:
            for current_line in user_dict_input_file:
                normalized_line = current_line.strip()
                if not normalized_line:
                    continue
                loaded_words.add(normalized_line.split()[0])
        return loaded_words

    def ensure_terms(self, custom_terms: list[str]):
        normalized_terms = [current_term.strip() for current_term in custom_terms if current_term and current_term.strip()]
        if not normalized_terms:
            return

        appended_terms = sorted(set(normalized_terms) - self._loaded_user_dict_words)
        if not appended_terms:
            return

        with open(self.user_dict_path, "a", encoding="utf-8") as user_dict_output_file:
            for custom_term in appended_terms:
                user_dict_output_file.write(f"{custom_term} 100000 nz\n")

        if self._jieba_module is not None:
            for custom_term in appended_terms:
                self._jieba_module.add_word(custom_term, freq=100000, tag="nz")
        self._loaded_user_dict_words.update(appended_terms)

    def tokenize(self, text: str) -> list[str]:
        normalized_text = text.lower().strip()
        if not normalized_text:
            return []

        alphanumeric_tokens = re.findall(r"[a-z0-9]+(?:[._/-][a-z0-9]+)*", normalized_text)
        protected_text = normalized_text
        for alphanumeric_token in alphanumeric_tokens:
            protected_text = protected_text.replace(alphanumeric_token, f" {alphanumeric_token} ")

        if self._jieba_module is not None:
            raw_tokens = self._jieba_module.lcut(protected_text, cut_all=False)
        else:
            raw_tokens = re.findall(r"[a-z0-9]+(?:[._/-][a-z0-9]+)*|[\u4e00-\u9fff]{2,}|[\u4e00-\u9fff]", protected_text)

        cleaned_tokens: list[str] = []
        for raw_token in raw_tokens:
            normalized_token = raw_token.strip().lower()
            if not normalized_token:
                continue
            if normalized_token in STOPWORDS:
                continue
            if re.fullmatch(r"[\W_]+", normalized_token):
                continue
            cleaned_tokens.append(normalized_token)

        return cleaned_tokens


class BM25Searcher:
    def __init__(self, k1: float = 1.5, b: float = 0.75, synonyms: Dict[str, list[str]] | None = None):
        self.k1 = k1
        self.b = b
        self._documents: list[dict] = []
        self._doc_freq: Counter = Counter()
        self._total_docs = 0
        self._avg_doc_len = 0.0
        self._built = False
        self.synonyms = synonyms or DEFAULT_SYNONYMS
        self._doc_lengths: list[int] = []
        self._doc_counters: list[Counter] = []
        self._vocab_by_len: dict[int, list[str]] = {}
        self._tokenizer = ChineseTokenizer(user_dict_path=USER_DICT_FILE)

    def _tokenize(self, text: str) -> list[str]:
        return self._tokenizer.tokenize(text)

    def _collect_custom_terms(self, metadata: Optional[dict] = None) -> list[str]:
        candidate_terms: set[str] = set()
        if metadata:
            for metadata_key in ("title", "department", "filename"):
                metadata_value = str(metadata.get(metadata_key, "")).strip()
                if metadata_value:
                    extracted_terms = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9][A-Za-z0-9._/-]{1,}", metadata_value)
                    candidate_terms.update(extracted_terms)

        return [current_term for current_term in candidate_terms if len(current_term) >= 2]

    def _expand_with_synonyms(self, tokens: list[str]) -> list[str]:
        expanded_tokens = list(tokens)
        for current_token in tokens:
            synonym_group = self.synonyms.get(current_token, [])
            expanded_tokens.extend(synonym_group)
        for current_token in tokens:
            for root_term, synonym_values in self.synonyms.items():
                if current_token in synonym_values and root_term not in expanded_tokens:
                    expanded_tokens.append(root_term)
        return expanded_tokens

    def _fuzzy_match(self, token: str, max_distance: int = 1) -> list[str]:
        token_length = len(token)
        matched_candidates = []
        for candidate_length in range(max(token_length - 2, 1), token_length + 3):
            for candidate_token in self._vocab_by_len.get(candidate_length, []):
                if abs(token_length - len(candidate_token)) > max_distance * 2:
                    continue
                if self._edit_distance(token, candidate_token) <= max_distance:
                    matched_candidates.append(candidate_token)
        return matched_candidates

    def _rebuild_vocab_index(self):
        length_buckets: dict[int, list[str]] = {}
        for token in self._doc_freq:
            length_buckets.setdefault(len(token), []).append(token)
        self._vocab_by_len = length_buckets

    def _edit_distance(self, source_text: str, target_text: str) -> int:
        if len(source_text) < len(target_text):
            return self._edit_distance(target_text, source_text)
        if len(target_text) == 0:
            return len(source_text)
        previous_row = list(range(len(target_text) + 1))
        for source_index, source_char in enumerate(source_text, 1):
            current_row = [source_index]
            for target_index, target_char in enumerate(target_text, 1):
                substitution_cost = 0 if source_char == target_char else 1
                current_row.append(
                    min(
                        current_row[-1] + 1,
                        previous_row[target_index] + 1,
                        previous_row[target_index - 1] + substitution_cost,
                    )
                )
            previous_row = current_row
        return previous_row[-1]

    def build_index(self, documents: list[dict]):
        self._documents = documents
        self._doc_freq.clear()
        self._total_docs = len(documents)
        total_doc_length = 0
        rebuilt_doc_lengths = []
        rebuilt_doc_counters = []

        custom_terms: list[str] = []
        for current_doc in documents:
            custom_terms.extend(
                self._collect_custom_terms(metadata=current_doc.get("metadata", {}))
            )
        self._tokenizer.ensure_terms(custom_terms)

        for current_doc in documents:
            tokenized_doc = self._tokenize(current_doc.get("content", ""))
            doc_counter = Counter(tokenized_doc)
            rebuilt_doc_lengths.append(len(tokenized_doc))
            rebuilt_doc_counters.append(doc_counter)
            total_doc_length += len(tokenized_doc)
            for unique_token in doc_counter:
                self._doc_freq[unique_token] += 1

        self._avg_doc_len = total_doc_length / max(self._total_docs, 1)
        self._doc_lengths = rebuilt_doc_lengths
        self._doc_counters = rebuilt_doc_counters
        self._rebuild_vocab_index()
        self._built = True

    def reset_index(self):
        self._documents = []
        self._doc_freq.clear()
        self._total_docs = 0
        self._avg_doc_len = 0.0
        self._doc_lengths = []
        self._doc_counters = []
        self._vocab_by_len = {}
        self._built = False

    def add_document(self, document: dict):
        self._documents.append(document)
        self._tokenizer.ensure_terms(
            self._collect_custom_terms(metadata=document.get("metadata", {}))
        )
        tokenized_doc = self._tokenize(document.get("content", ""))
        doc_counter = Counter(tokenized_doc)
        self._doc_counters.append(doc_counter)
        for unique_token in doc_counter:
            self._doc_freq[unique_token] += 1
        self._total_docs = len(self._documents)
        self._doc_lengths.append(len(tokenized_doc))
        self._avg_doc_len = sum(self._doc_lengths) / max(self._total_docs, 1)
        self._rebuild_vocab_index()
        self._built = True

    def search(
        self,
        query: str,
        top_k: int = 10,
        synonym_expansion: bool = True,
        fuzzy_match: bool = True,
        filters: Optional[dict] = None,
    ) -> List[dict]:
        if not self._built or not self._documents:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        if synonym_expansion:
            query_tokens = self._expand_with_synonyms(query_tokens)

        scored_documents = []
        for document_index, current_doc in enumerate(self._documents):
            if filters and not match_filters(current_doc.get("metadata", {}), filters):
                continue

            doc_token_counter = self._doc_counters[document_index]
            doc_length = self._doc_lengths[document_index]
            if doc_length == 0:
                continue

            bm25_score_value = 0.0
            for query_token in query_tokens:
                if query_token in doc_token_counter and query_token in self._doc_freq:
                    bm25_score_value += self._bm25_score(query_token, doc_token_counter[query_token], doc_length)
                elif fuzzy_match and 2 <= len(query_token) <= 16:
                    fuzzy_matches = self._fuzzy_match(query_token, max_distance=1)
                    for fuzzy_token in fuzzy_matches:
                        if fuzzy_token in doc_token_counter and fuzzy_token in self._doc_freq:
                            bm25_score_value += self._bm25_score(fuzzy_token, doc_token_counter[fuzzy_token], doc_length) * 0.6
                            break

            if bm25_score_value > 0:
                scored_documents.append({
                    "chunk_id": current_doc.get("chunk_id", str(document_index)),
                    "doc_id": current_doc.get("metadata", {}).get("document_id", ""),
                    "content": current_doc.get("content", ""),
                    "metadata": current_doc.get("metadata", {}),
                    "score": bm25_score_value,
                    "source": "keyword",
                })

        scored_documents.sort(key=lambda current_item: current_item["score"], reverse=True)
        return scored_documents[:top_k]

    def _bm25_score(self, token: str, tf: int, doc_len: int) -> float:
        doc_frequency = self._doc_freq.get(token, 0)
        if doc_frequency == 0:
            return 0.0
        inverse_document_frequency = math.log((self._total_docs - doc_frequency + 0.5) / (doc_frequency + 0.5) + 1.0)
        numerator = tf * (self.k1 + 1)
        denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / max(self._avg_doc_len, 1.0))
        return inverse_document_frequency * numerator / denominator

    def generate_sparse_embedding(self, text: str) -> Dict[str, float]:
        tokenized_text = self._tokenize(text)
        token_counter = Counter(tokenized_text)
        total_token_count = sum(token_counter.values()) or 1
        sparse_vector: Dict[str, float] = {}
        for current_token, current_count in token_counter.items():
            doc_frequency = self._doc_freq.get(current_token, 1)
            inverse_document_frequency = math.log((max(self._total_docs, 1) + 1) / (doc_frequency + 1)) + 1
            sparse_vector[current_token] = (current_count / total_token_count) * inverse_document_frequency
        return sparse_vector

    def delete_document(self, document_id: str):
        original_doc_count = len(self._documents)
        self._documents = [
            current_doc
            for current_doc in self._documents
            if current_doc.get("metadata", {}).get("document_id") != document_id
        ]
        if len(self._documents) == original_doc_count:
            return

        self._doc_freq.clear()
        self._doc_lengths = []
        self._doc_counters = []
        self._total_docs = len(self._documents)
        total_doc_length = 0
        for current_doc in self._documents:
            tokenized_doc = self._tokenize(current_doc.get("content", ""))
            doc_counter = Counter(tokenized_doc)
            self._doc_lengths.append(len(tokenized_doc))
            self._doc_counters.append(doc_counter)
            total_doc_length += len(tokenized_doc)
            for unique_token in doc_counter:
                self._doc_freq[unique_token] += 1
        self._avg_doc_len = total_doc_length / max(self._total_docs, 1)
        self._rebuild_vocab_index()
        self._built = bool(self._documents)

    def save_to_disk(self, file_path: Path = BM25_INDEX_FILE):
        payload = {
            "version": 2,
            "k1": self.k1,
            "b": self.b,
            "documents": self._documents,
            "synonyms": self.synonyms,
            "tokenizer_user_dict_path": str(self._tokenizer.user_dict_path),
        }
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as output_file:
            json.dump(payload, output_file, ensure_ascii=False)

    def load_from_disk(self, file_path: Path = BM25_INDEX_FILE) -> bool:
        if not file_path.exists():
            return False

        with open(file_path, "r", encoding="utf-8") as input_file:
            payload = json.load(input_file)

        self.k1 = float(payload.get("k1", self.k1))
        self.b = float(payload.get("b", self.b))
        self.synonyms = payload.get("synonyms", DEFAULT_SYNONYMS)
        persisted_documents = payload.get("documents", [])
        if not isinstance(persisted_documents, list):
            raise ValueError("BM25 persisted documents payload is invalid")
        self.build_index(persisted_documents)
        return True


__all__ = ["BM25Searcher", "get_bm25_searcher"]
