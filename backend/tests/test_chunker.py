from app.services.chunker import FixedChunker, SemanticChunker, StructuralChunker


def test_fixed_chunker_respects_size():
    chunker = FixedChunker(chunk_size=30, chunk_overlap=0.2)
    chunks = chunker.split("A" * 100)
    assert chunks
    assert all(len(chunk) <= 30 for chunk in chunks)


def test_semantic_chunker_falls_back_to_size():
    chunker = SemanticChunker(chunk_size=20, similarity_threshold=0.6)
    chunks = chunker.split("这是第一句话。这是第二句话。这是第三句话。")
    assert chunks
    assert all(len(chunk) <= 20 for chunk in chunks)


def test_structural_chunker_detects_headings():
    chunker = StructuralChunker(max_chunk_size=200)
    chunks = chunker.split("# 标题一\n内容A\n\n# 标题二\n内容B\n")
    assert any("标题一" in chunk for chunk in chunks)
    assert any("标题二" in chunk for chunk in chunks)