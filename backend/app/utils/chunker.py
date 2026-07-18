from core.constants import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """텍스트를 단어 기준 슬라이딩 윈도우로 청킹.

    의미 경계(문단/문장) 인지 청킹은 추후 고도화 대상이며, MVP에서는 단어
    수 기준 고정 윈도우 + 중첩으로 단순하게 나눈다. 중첩은 청크 경계에서
    문맥이 잘리는 것을 완화한다.

    Parameters:
        text(str): 원본 문서 텍스트
        chunk_size(int): 청크당 최대 단어 수
        overlap(int): 인접 청크 간 겹칠 단어 수(chunk_size 미만이어야 함)

    Returns:
        list[str]: 청크 텍스트 목록(공백만 있는 입력이면 빈 목록)
    """
    words = text.split()
    if not words:
        return []
    if overlap >= chunk_size:
        overlap = chunk_size - 1

    step = chunk_size - overlap
    chunks: list[str] = []
    for start in range(0, len(words), step):
        window = words[start : start + chunk_size]
        if not window:
            break
        chunks.append(" ".join(window))
        if start + chunk_size >= len(words):
            break
    return chunks
