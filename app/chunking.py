from __future__ import annotations

import re
from pathlib import Path

from app.models import DocumentChunk
from app.utils import approximate_token_count, normalize_text, sha256_text


class Chunker:
    def __init__(self, chunk_size_tokens: int, overlap_tokens: int, min_chunk_tokens: int) -> None:
        self.chunk_size_tokens = chunk_size_tokens
        self.overlap_tokens = overlap_tokens
        self.min_chunk_tokens = min_chunk_tokens

    def chunk_pages(self, source_path: Path, pages: list[tuple[int, str]]) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        seen_hashes: set[str] = set()
        for page_number, page_text in pages:
            for chunk_text in self._chunk_text(page_text):
                content_hash = sha256_text(normalize_text(chunk_text))
                if content_hash in seen_hashes:
                    continue
                seen_hashes.add(content_hash)
                chunk_index = len(chunks)
                chunk_id = sha256_text(f"{source_path}:{page_number}:{chunk_index}:{content_hash}")[:24]
                chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        text=chunk_text,
                        source_path=str(source_path),
                        file_name=source_path.name,
                        page_number=page_number,
                        chunk_index=chunk_index,
                        content_hash=content_hash,
                    )
                )
        return chunks

    def _chunk_text(self, text: str) -> list[str]:
        paragraphs = [normalize_text(part) for part in re.split(r"\n{2,}", text) if normalize_text(part)]
        if not paragraphs:
            return []

        units: list[str] = []
        for paragraph in paragraphs:
            if approximate_token_count(paragraph) <= self.chunk_size_tokens:
                units.append(paragraph)
                continue
            sentences = re.split(r"(?<=[.!?])\s+", paragraph)
            for sentence in sentences:
                normalized_sentence = normalize_text(sentence)
                if not normalized_sentence:
                    continue
                if approximate_token_count(normalized_sentence) <= self.chunk_size_tokens:
                    units.append(normalized_sentence)
                else:
                    units.extend(self._split_large_unit(normalized_sentence))

        chunks: list[str] = []
        current: list[str] = []
        current_tokens = 0
        for unit in units:
            unit_tokens = approximate_token_count(unit)
            if current and current_tokens + unit_tokens > self.chunk_size_tokens:
                chunk_text = "\n\n".join(current).strip()
                if approximate_token_count(chunk_text) >= self.min_chunk_tokens:
                    chunks.append(chunk_text)
                current = self._build_overlap(current)
                current_tokens = sum(approximate_token_count(item) for item in current)
            current.append(unit)
            current_tokens += unit_tokens

        if current:
            chunk_text = "\n\n".join(current).strip()
            if approximate_token_count(chunk_text) >= self.min_chunk_tokens or not chunks:
                chunks.append(chunk_text)
        return chunks

    def _build_overlap(self, units: list[str]) -> list[str]:
        overlap: list[str] = []
        total_tokens = 0
        for unit in reversed(units):
            total_tokens += approximate_token_count(unit)
            overlap.insert(0, unit)
            if total_tokens >= self.overlap_tokens:
                break
        return overlap

    def _split_large_unit(self, text: str) -> list[str]:
        words = text.split()
        if not words:
            return []
        words_per_chunk = max(1, self.chunk_size_tokens * 4 // 8)
        overlap_words = max(1, self.overlap_tokens * 4 // 8)
        step = max(1, words_per_chunk - overlap_words)
        chunks: list[str] = []
        for start in range(0, len(words), step):
            chunk_words = words[start : start + words_per_chunk]
            if not chunk_words:
                continue
            chunks.append(" ".join(chunk_words))
            if start + words_per_chunk >= len(words):
                break
        return chunks
