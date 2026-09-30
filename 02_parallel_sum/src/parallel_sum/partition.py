"""Split 1..n into contiguous chunks, the same way all my 2025 versions did."""


def chunk_bounds(n: int, parts: int) -> list[tuple[int, int]]:
    """Inclusive (start, end) bounds for `parts` chunks of 1..n; the last chunk takes the remainder.

    Chunks are empty (start > end) when parts > n, and sum(range(start, end + 1)) is then 0.
    """
    if parts < 1:
        raise ValueError("parts must be >= 1")
    if n < 0:
        raise ValueError("n must be >= 0")
    step = n // parts
    bounds = []
    for i in range(parts):
        start = i * step + 1
        end = (i + 1) * step if i != parts - 1 else n
        bounds.append((start, end))
    return bounds
