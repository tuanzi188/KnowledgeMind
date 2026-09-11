from app.models.chat import Citation
from app.services.rag_engine import (
    _compute_confidence,
    _extract_citations_from_answer,
    _parse_answer_segments,
)


def _docs():
    return [
        {
            "chunk_id": "c1",
            "content": "试用期为三个月",
            "metadata": {"title": "员工手册", "chunk_index": 0, "page": 1},
            "rerank_score": 0.9,
        },
        {
            "chunk_id": "c2",
            "content": "华东销售额增长",
            "metadata": {"title": "销售报告", "chunk_index": 1, "page": 2},
            "rerank_score": 0.7,
        },
    ]


def test_index_citation_extraction():
    citations = _extract_citations_from_answer("试用期三个月。[引用: 1]", _docs())
    assert [c.document_id for c in citations] == ["c1"]
    assert citations[0].document_title == "员工手册"


def test_multi_index_citation():
    citations = _extract_citations_from_answer("[引用: 1] 试用期；[引用: 2] 华东。", _docs())
    assert [c.document_id for c in citations] == ["c1", "c2"]


def test_title_fallback_citation():
    citations = _extract_citations_from_answer("试用期三个月。[引用: 员工手册, 1]", _docs())
    assert [c.document_id for c in citations] == ["c1"]


def test_parse_segments_with_index():
    docs = _docs()
    citations = _extract_citations_from_answer("[引用: 1] 试用期", docs)
    segments = _parse_answer_segments("[引用: 1] 试用期\n\n无引用段落", citations, docs)
    assert [c.document_id for c in segments[0].citations] == ["c1"]
    assert segments[1].citations == []


def test_compute_confidence():
    citations = [Citation(document_id="c1", document_title="员工手册", content="x", score=0.8)]
    reranked = [{"rerank_score": 0.9}, {"rerank_score": 0.7}]
    assert _compute_confidence(citations, reranked) == 0.8
    assert _compute_confidence([], []) == 0.0