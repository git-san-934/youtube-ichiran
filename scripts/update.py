"""登録チャンネルの公開RSSから動画一覧を取得し data/videos.json に蓄積する。

APIキー不要。YouTube のチャンネルフィード
    https://www.youtube.com/feeds/videos.xml?channel_id=UC...
から 各動画の タイトル / 公開日時 / サムネイル / 再生回数 / 評価数 を読み取り、
既存の data/videos.json にマージする。

  * 既存の動画レコードは消さず、再生回数などを最新値で更新する
  * フィードには各チャンネル最新15件しか出ないが、過去に取得した動画は残るため
    実行を重ねるほど履歴が蓄積される（チャンネルごとに KEEP_PER_CHANNEL 件まで）
  * channels.json から外したチャンネルの動画は次回実行時に落ちる

標準ライブラリのみ。ネットワークが必要。
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANNELS_PATH = ROOT / "data" / "channels.json"
VIDEOS_PATH = ROOT / "data" / "videos.json"

JST = timezone(timedelta(hours=9))
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
REQUEST_INTERVAL_SEC = 1.0   # フィード取得の間隔（連続アクセスを避ける）
KEEP_PER_CHANNEL = 300       # 1チャンネルあたり保持する最大件数（古いものから削除）

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}


def now_iso() -> str:
    return datetime.now(JST).isoformat(timespec="seconds")


def fetch(url: str) -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept-Language": "ja,en;q=0.8"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def _int_attr(el, name):
    if el is None:
        return None
    v = el.get(name, "")
    return int(v) if v.isdigit() else None


def parse_feed(xml_bytes: bytes) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    out: list[dict] = []
    for entry in root.findall("atom:entry", NS):
        vid = (entry.findtext("yt:videoId", "", NS) or "").strip()
        if not vid:
            continue

        thumb_el = entry.find(".//media:thumbnail", NS)
        stat_el = entry.find(".//media:statistics", NS)
        rate_el = entry.find(".//media:starRating", NS)

        rating_avg = None
        if rate_el is not None and rate_el.get("average"):
            try:
                rating_avg = float(rate_el.get("average"))
            except ValueError:
                rating_avg = None

        out.append(
            {
                "video_id": vid,
                "title": (entry.findtext("atom:title", "", NS) or "").strip(),
                "published_at": (entry.findtext("atom:published", "", NS) or "").strip(),
                "channel_id": (entry.findtext("yt:channelId", "", NS) or "").strip(),
                "thumbnail": thumb_el.get("url", "") if thumb_el is not None else "",
                "views": _int_attr(stat_el, "views"),
                "rating_count": _int_attr(rate_el, "count"),
                "rating_avg": rating_avg,
            }
        )
    return out


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def main() -> int:
    channels = load_json(CHANNELS_PATH, [])
    resolved = [c for c in channels if c.get("channel_id")]
    name_by_cid = {
        c["channel_id"]: (c.get("name") or c.get("handle", "").lstrip("@"))
        for c in resolved
    }

    prev = load_json(VIDEOS_PATH, {})
    merged: dict[str, dict] = {
        v["video_id"]: v for v in prev.get("videos", []) if v.get("video_id")
    }

    ts = now_iso()
    errors: list[str] = []

    for i, ch in enumerate(resolved):
        cid = ch["channel_id"]
        if i:
            time.sleep(REQUEST_INTERVAL_SEC)
        try:
            entries = parse_feed(fetch(FEED_URL.format(cid=cid)))
        except (urllib.error.URLError, ET.ParseError, TimeoutError, ValueError) as exc:
            errors.append(f"{name_by_cid.get(cid, cid)}: {exc}")
            continue

        for e in entries:
            vid = e["video_id"]
            old = merged.get(vid, {})
            has_views = e["views"] is not None
            merged[vid] = {
                "video_id": vid,
                "url": f"https://www.youtube.com/watch?v={vid}",
                "title": e["title"] or old.get("title", ""),
                "channel_id": cid,
                "channel": name_by_cid.get(cid, old.get("channel", "")),
                "published_at": e["published_at"] or old.get("published_at", ""),
                "thumbnail": e["thumbnail"]
                or old.get("thumbnail")
                or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                "views": e["views"] if has_views else old.get("views"),
                "views_updated_at": ts if has_views else old.get("views_updated_at"),
                "rating_count": e["rating_count"]
                if e["rating_count"] is not None
                else old.get("rating_count"),
                "rating_avg": e["rating_avg"]
                if e["rating_avg"] is not None
                else old.get("rating_avg"),
                "first_seen_at": old.get("first_seen_at", ts),
            }

    # いま登録されているチャンネルの動画だけを残す
    valid_cids = set(name_by_cid)
    by_cid: dict[str, list[dict]] = {}
    for v in merged.values():
        if v.get("channel_id") in valid_cids:
            by_cid.setdefault(v["channel_id"], []).append(v)

    kept: list[dict] = []
    for lst in by_cid.values():
        lst.sort(key=lambda v: v.get("published_at", ""), reverse=True)
        kept.extend(lst[:KEEP_PER_CHANNEL])
    kept.sort(key=lambda v: v.get("published_at", ""), reverse=True)

    payload = {
        "updated_at": ts,
        "channels": [
            {"channel_id": cid, "name": name_by_cid[cid]} for cid in name_by_cid
        ],
        "videos": kept,
    }
    VIDEOS_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"{len(kept)} 本の動画を書き出しました（{len(resolved)} チャンネル）。")

    if errors:
        print("\n--- 取得できなかったチャンネル（次回再試行）---", file=sys.stderr)
        for line in errors:
            print(f"  {line}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
