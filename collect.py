"""
YouTube 뉴스 댓글 수집기
준비: pip install requests
      export YOUTUBE_API_KEY=발급받은키
실행: python collect.py            # 전체 수집
      python collect.py --dry-run  # 채널 핸들 확인 + 예상 쿼터만 출력
다시 실행해도 이미 받은 영상은 건너뛴다.
"""
import argparse
import os
import sqlite3
from datetime import datetime, timedelta, timezone

import requests

import config

API = "https://www.googleapis.com/youtube/v3"
KEY = os.environ.get("YOUTUBE_API_KEY")
quota_used = 0  # 대략적인 사용량 추적 (하루 기본 10,000)

COST = {"channels": 1, "search": 100, "videos": 1, "commentThreads": 1}


def yt(endpoint: str, **params) -> dict:
    global quota_used
    params["key"] = KEY
    r = requests.get(f"{API}/{endpoint}", params=params, timeout=30)
    quota_used += COST[endpoint]
    if r.status_code != 200:
        raise RuntimeError(f"{endpoint} {r.status_code}: {r.json().get('error', {}).get('message')}")
    return r.json()


def init_db(path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY, date TEXT, type TEXT, name TEXT, query TEXT
        );
        CREATE TABLE IF NOT EXISTS videos (
            video_id TEXT PRIMARY KEY, event_id TEXT, channel_id TEXT, channel_title TEXT,
            title TEXT, published_at TEXT, view_count INTEGER, comment_count INTEGER,
            comments_status TEXT, collected_at TEXT
        );
        CREATE TABLE IF NOT EXISTS comments (
            comment_id TEXT PRIMARY KEY, video_id TEXT, text TEXT, like_count INTEGER,
            reply_count INTEGER, published_at TEXT, updated_at TEXT, collected_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_comments_time ON comments(published_at);
        """
    )
    return con


def resolve_channels(handles: list[str]) -> dict[str, str]:
    """핸들 → channel_id. 못 찾은 핸들은 경고만 출력."""
    found = {}
    for h in handles:
        items = yt("channels", part="snippet", forHandle=h).get("items", [])
        if items:
            found[items[0]["id"]] = items[0]["snippet"]["title"]
            print(f"  ✓ {h} → {items[0]['snippet']['title']}")
        else:
            print(f"  ✗ {h} 채널을 찾지 못함 — config.py의 핸들 확인 필요")
    return found


def window(event: dict) -> tuple[str, str]:
    d = datetime.fromisoformat(event["date"]).replace(tzinfo=timezone.utc)
    start = d - timedelta(days=config.PRE_DAYS)
    end = d + timedelta(days=config.POST_DAYS + 1)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return start.strftime(fmt), end.strftime(fmt)


def search_videos(event: dict, channel_id: str) -> list[str]:
    after, before = window(event)
    res = yt(
        "search", part="id", channelId=channel_id, q=event["query"], type="video",
        publishedAfter=after, publishedBefore=before, order="relevance",
        maxResults=config.MAX_VIDEOS_PER_SEARCH, regionCode="KR", relevanceLanguage="ko",
    )
    return [it["id"]["videoId"] for it in res.get("items", [])]


def fetch_video_meta(video_ids: list[str]) -> list[dict]:
    if not video_ids:
        return []
    res = yt("videos", part="snippet,statistics", id=",".join(video_ids))
    return res.get("items", [])


def fetch_comments(video_id: str) -> tuple[list[dict], str]:
    rows, token = [], None
    while len(rows) < config.MAX_COMMENTS_PER_VIDEO:
        try:
            res = yt(
                "commentThreads", part="snippet", videoId=video_id, maxResults=100,
                order="time", textFormat="plainText", **({"pageToken": token} if token else {}),
            )
        except RuntimeError as e:
            if "disabled comments" in str(e).lower() or "403" in str(e):
                return rows, "disabled"
            raise
        for it in res.get("items", []):
            s = it["snippet"]["topLevelComment"]["snippet"]
            rows.append({
                "comment_id": it["id"], "video_id": video_id, "text": s["textDisplay"],
                "like_count": s.get("likeCount", 0),
                "reply_count": it["snippet"].get("totalReplyCount", 0),
                "published_at": s["publishedAt"], "updated_at": s["updatedAt"],
            })
        token = res.get("nextPageToken")
        if not token:
            break
    return rows, "ok"


def main(dry_run: bool):
    if not KEY:
        raise SystemExit("YOUTUBE_API_KEY 환경변수를 먼저 설정해줘.")

    print("채널 확인:")
    channels = resolve_channels(config.CHANNEL_HANDLES)
    n_search = len(channels) * len(config.EVENTS)
    print(f"\n검색 {n_search}회 예정 → 약 {n_search * 100:,} 유닛 + 댓글 수집 (하루 기본 한도 10,000)")
    if dry_run:
        return

    con = init_db(config.DB_PATH)
    now = datetime.now(timezone.utc).isoformat()
    con.executemany(
        "INSERT OR IGNORE INTO events VALUES (?,?,?,?,?)",
        [(e["id"], e["date"], e["type"], e["name"], e["query"]) for e in config.EVENTS],
    )

    for ev in config.EVENTS:
        print(f"\n[{ev['name']}]")
        for ch_id, ch_title in channels.items():
            ids = search_videos(ev, ch_id)
            known = {r[0] for r in con.execute(
                f"SELECT video_id FROM videos WHERE video_id IN ({','.join('?' * len(ids))})", ids
            )} if ids else set()
            new_ids = [v for v in ids if v not in known]

            for v in fetch_video_meta(new_ids):
                comments, status = fetch_comments(v["id"])
                st = v.get("statistics", {})
                con.execute(
                    "INSERT OR IGNORE INTO videos VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (v["id"], ev["id"], ch_id, ch_title, v["snippet"]["title"],
                     v["snippet"]["publishedAt"], int(st.get("viewCount", 0)),
                     int(st.get("commentCount", 0)), status, now),
                )
                con.executemany(
                    "INSERT OR IGNORE INTO comments VALUES (?,?,?,?,?,?,?,?)",
                    [(c["comment_id"], c["video_id"], c["text"], c["like_count"],
                      c["reply_count"], c["published_at"], c["updated_at"], now) for c in comments],
                )
                con.commit()
            print(f"  {ch_title}: 영상 {len(ids)}개 (신규 {len(new_ids)}) | 누적 쿼터 ≈ {quota_used:,}")

    n_v = con.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
    n_c = con.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
    print(f"\n완료: 영상 {n_v}개, 댓글 {n_c:,}개 | 이번 실행 쿼터 ≈ {quota_used:,}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    main(p.parse_args().dry_run)
