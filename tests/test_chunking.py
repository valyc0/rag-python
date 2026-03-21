from app.chunking import Chunker


def test_chunker_respects_overlap_and_minimum_size() -> None:
    chunker = Chunker(chunk_size_tokens=30, overlap_tokens=10, min_chunk_tokens=5)
    text = " ".join(f"token{i}" for i in range(120))
    chunks = chunker._chunk_text(text)
    assert len(chunks) >= 2
    assert all(chunk.strip() for chunk in chunks)
