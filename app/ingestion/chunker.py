import re
from typing import Callable
from app.config import settings


# ─────────────────────────────────────────────────────────────────────────
# Token-aware chunking (preferred)
#
# all-MiniLM-L6-v2 has a hard limit of 256 tokens — anything longer is
# silently truncated, so the tail of an over-long chunk never gets embedded.
# We therefore size chunks in TOKENS (not characters), packing whole sentences
# up to a budget that leaves headroom under the model's limit.
# ─────────────────────────────────────────────────────────────────────────

def _split_into_units(text: str) -> list[str]:
    """Break text into atomic units: sentences, falling back to lines."""
    units: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        # Sentence split that keeps the terminator with the sentence
        for sent in re.split(r"(?<=[.!?])\s+", para):
            sent = sent.strip()
            if sent:
                units.append(sent)
    return units


def _hard_split_unit(unit: str, count_tokens: Callable[[str], int], max_tokens: int) -> list[str]:
    """Split a single over-long unit (e.g. a giant line) by words within budget."""
    words = unit.split()
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        if count_tokens(" ".join(cur)) > max_tokens:
            cur.pop()
            if cur:
                chunks.append(" ".join(cur))
            cur = [w]
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def chunk_text_by_tokens(
    text: str,
    count_tokens: Callable[[str], int],
    max_tokens: int | None = None,
    overlap_tokens: int | None = None,
) -> list[str]:
    max_tokens = max_tokens or settings.chunk_tokens
    overlap_tokens = overlap_tokens or settings.chunk_overlap_tokens

    text = text.strip()
    if not text:
        return []
    if count_tokens(text) <= max_tokens:
        return [text]

    units = _split_into_units(text)
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for unit in units:
        ut = count_tokens(unit)

        # A single unit bigger than the budget gets hard-split on its own.
        if ut > max_tokens:
            if current:
                chunks.append(" ".join(current))
                current, current_tokens = [], 0
            chunks.extend(_hard_split_unit(unit, count_tokens, max_tokens))
            continue

        if current_tokens + ut > max_tokens and current:
            chunks.append(" ".join(current))
            # Carry trailing sentences forward for overlap/context continuity
            overlap_units, ot = [], 0
            for u in reversed(current):
                t = count_tokens(u)
                if ot + t > overlap_tokens:
                    break
                overlap_units.insert(0, u)
                ot += t
            current = overlap_units + [unit]
            current_tokens = sum(count_tokens(u) for u in current)
        else:
            current.append(unit)
            current_tokens += ut

    if current:
        chunks.append(" ".join(current))

    return chunks


# ─────────────────────────────────────────────────────────────────────────
# Character-based fallback (legacy) — only used when no tokenizer is available.
# ─────────────────────────────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
    chunk_size = chunk_size or settings.chunk_size
    overlap = overlap or settings.chunk_overlap

    if len(text) <= chunk_size:
        return [text]

    separators = ["\n\n", "\n", ". ", " "]
    return _recursive_split(text, separators, chunk_size, overlap)


def _recursive_split(text: str, separators: list[str], chunk_size: int, overlap: int) -> list[str]:
    chunks = []
    separator = separators[0] if separators else ""

    parts = text.split(separator) if separator else [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

    current = ""
    for part in parts:
        candidate = f"{current}{separator}{part}" if current else part
        if len(candidate) > chunk_size and current:
            chunks.append(current.strip())
            overlap_text = current[-overlap:] if overlap and len(current) > overlap else ""
            current = f"{overlap_text}{separator}{part}" if overlap_text else part
        else:
            current = candidate

    if current.strip():
        chunks.append(current.strip())

    final = []
    for chunk in chunks:
        if len(chunk) > chunk_size and len(separators) > 1:
            final.extend(_recursive_split(chunk, separators[1:], chunk_size, overlap))
        else:
            final.append(chunk)

    return final
