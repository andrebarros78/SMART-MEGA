"""Official-source metadata catalog. Does not download videos or assert learning."""
import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs

SCHEMA = "SMART_VISUAL_OFFICIAL_CATALOG_V1"
CONTEST = re.compile(r"(?i)mega\\s*[- ]?\\s*sena\\s*[-:–]?\\s*(?:concurso\\s*(?:n[ºo.]*)?\\s*)?(\\d{3,5})\\b")

def video_id(url):
    p = urlparse(str(url))
    if p.scheme != "https" or p.hostname not in ("youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"):
        raise ValueError("untrusted URL")
    v = p.path.strip("/") if p.hostname == "youtu.be" else parse_qs(p.query).get("v", [""])[0]
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", v):
        raise ValueError("invalid video ID")
    return v

def ingest(rows, destination, *, channel_id):
    if not re.fullmatch(r"UC[A-Za-z0-9_-]{22}", channel_id):
        raise ValueError("verified channel ID required")
    p = Path(destination)
    state = json.loads(p.read_text("utf-8")) if p.is_file() else {"schema": SCHEMA, "channel_id": channel_id, "records": {}}
    if state.get("schema") != SCHEMA or state.get("channel_id") != channel_id:
        raise ValueError("catalog mismatch")
    records = state["records"].copy()
    accepted = rejected = 0
    for row in rows:
        try:
            if row["channel_id"] != channel_id:
                raise ValueError("foreign channel")
            vid = video_id(row["url"])
            matches = set(int(n) for n in CONTEST.findall(str(row.get("title", "")) + "\n" + str(row.get("description", ""))))
            if len(matches) != 1:
                raise ValueError("ambiguous contest")
            contest = str(matches.pop())
            published = datetime.fromisoformat(row["published_at"].replace("Z", "+00:00"))
            if published.tzinfo is None:
                raise ValueError("naive timestamp")
            if contest in records and records[contest]["video_id"] != vid:
                raise ValueError("video collision")
            old = records.get(contest, {})
            records[contest] = {"contest_id": contest, "video_id": vid,
                                "source_url": "https://www.youtube.com/watch?v=" + vid,
                                "published_at": published.astimezone(timezone.utc).isoformat(),
                                "status": old.get("status", "DISCOVERED"),
                                "checkpoint_sha256": old.get("checkpoint_sha256")}
            accepted += 1
        except (KeyError, TypeError, ValueError):
            rejected += 1
    state["records"] = dict(sorted(records.items(), key=lambda x: int(x[0])))
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=p.parent, prefix=".catalog-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(state, out, sort_keys=True, ensure_ascii=False, indent=2)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, p)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return {"accepted": accepted, "rejected": rejected, "total": len(records),
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}

def pending(destination, limit=500):
    if not isinstance(limit, int) or not 1 <= limit <= 500:
        raise ValueError("limit must be 1..500")
    state = json.loads(Path(destination).read_text("utf-8"))
    if state.get("schema") != SCHEMA:
        raise ValueError("invalid catalog")
    return [{"contest_id": contest, "source_url": item["source_url"]}
            for contest, item in state["records"].items() if item["status"] == "DISCOVERED"][:limit]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata-json", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--verified-channel-id", required=True)
    args = parser.parse_args()
    rows = json.loads(Path(args.metadata_json).read_text("utf-8"))
    print(json.dumps(ingest(rows, args.catalog, channel_id=args.verified_channel_id)))

if __name__ == "__main__":
    main()
