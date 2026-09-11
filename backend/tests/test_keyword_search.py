from app.services.keyword_search import BM25Searcher


def _searcher(tmp_path):
    searcher = BM25Searcher()
    searcher._tokenizer.user_dict_path = tmp_path / "user_dict.txt"
    return searcher


def test_bm25_exact_and_fuzzy(tmp_path):
    searcher = _searcher(tmp_path)
    searcher.build_index([
        {"chunk_id": "e1", "doc_id": "d1", "content": "hello world foo bar", "metadata": {"document_id": "d1"}},
        {"chunk_id": "e2", "doc_id": "d1", "content": "foo baz qux", "metadata": {"document_id": "d1"}},
        {"chunk_id": "e3", "doc_id": "d2", "content": "hello nothing", "metadata": {"document_id": "d2"}},
    ])

    exact = searcher.search("foo", top_k=10, fuzzy_match=False)
    assert {r["chunk_id"] for r in exact} == {"e1", "e2"}

    fuzzy = searcher.search("helo", top_k=10, fuzzy_match=True)
    assert {r["chunk_id"] for r in fuzzy} == {"e3", "e1"}


def test_bm25_chinese_granularity(tmp_path):
    searcher = _searcher(tmp_path)
    searcher.build_index([
        {
            "chunk_id": "c1",
            "doc_id": "d1",
            "content": "公司内部管理制度规定员工试用期为三个月",
            "metadata": {"document_id": "d1", "title": "员工手册"},
        }
    ])
    results = searcher.search("试用期", top_k=10, fuzzy_match=False)
    assert [r["chunk_id"] for r in results] == ["c1"]


def test_bm25_add_and_delete(tmp_path):
    searcher = _searcher(tmp_path)
    searcher.build_index([
        {"chunk_id": "c1", "doc_id": "d1", "content": "training eval score", "metadata": {"document_id": "d1"}},
    ])
    searcher.add_document({"chunk_id": "c2", "doc_id": "d2", "content": "training plan", "metadata": {"document_id": "d2"}})
    assert {r["chunk_id"] for r in searcher.search("training", top_k=10, fuzzy_match=False)} == {"c1", "c2"}

    searcher.delete_document("d2")
    assert [r["chunk_id"] for r in searcher.search("training", top_k=10, fuzzy_match=False)] == ["c1"]