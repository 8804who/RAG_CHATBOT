from services.ingestion.chunker import chunk_text


def test_chunk_text_success_with_short_text():
    # 단일 윈도우보다 짧은 텍스트는 청크 하나로 반환된다.
    result = chunk_text("hello world", chunk_size=400, overlap=80)

    assert result == ["hello world"]


def test_chunk_text_success_with_overlap():
    # chunk_size/overlap에 맞춰 슬라이딩 윈도우로 나누고 단어가 겹친다.
    words = [str(i) for i in range(10)]
    result = chunk_text(" ".join(words), chunk_size=4, overlap=2)

    # step = 4 - 2 = 2 → 시작 인덱스 0,2,4,6 (마지막 윈도우가 끝에 도달하면 종료)
    assert result[0] == "0 1 2 3"
    assert result[1] == "2 3 4 5"
    assert result[-1].split()[-1] == "9"


def test_chunk_text_success_with_blank_input():
    # 공백만 있는 입력은 빈 목록을 반환한다(인제스트 시 EmptyDocumentError로 이어짐).
    assert chunk_text("   \n  ") == []
