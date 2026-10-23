"""수집 범위 설정 — 여기만 바꾸면 수집 대상이 바뀐다."""

# 분석할 정책 이벤트 (발표일 기준)
EVENTS = [
    {
        "id": "2025-06-27_loan",
        "date": "2025-06-27",
        "type": "demand",  # 수요 억제
        "name": "6.27 대출규제 (수도권 주담대 6억 캡)",
        "query": "대출규제|주담대|6억",
    },
    {
        "id": "2025-09-07_supply",
        "date": "2025-09-07",
        "type": "supply",  # 공급 확대
        "name": "9.7 주택공급 확대방안 (수도권 135만호)",
        "query": "주택공급|공급대책|135만호",
    },
    {
        "id": "2025-10-15_regulation",
        "date": "2025-10-15",
        "type": "demand",
        "name": "10.15 주택시장 안정화 대책 (규제지역·토허구역 확대)",
        "query": "부동산 대책|토지거래허가|규제지역",
    },
]

# 방송사 뉴스 채널 유튜브 핸들 — 실제 채널 페이지 URL(@...)에서 확인 후 수정
CHANNEL_HANDLES = [
    "@KBSnews",
    "@MBCNEWS11",
    "@sbsnews8",
    "@ytnnews24",
    "@jtbc_news",
]

# 영상 선정 규칙: 발표일 기준 [-PRE_DAYS, +POST_DAYS] 사이에 올라온 영상
PRE_DAYS = 7
POST_DAYS = 14

MAX_VIDEOS_PER_SEARCH = 10      # 채널 × 이벤트당 영상 수 (관련도순 상위)
MAX_COMMENTS_PER_VIDEO = 1000   # 영상당 최상위 댓글 상한

DB_PATH = "data/comments.db"
