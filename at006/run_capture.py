from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

def request(method: str, url: str, *, username: str, password: str, payload: dict | None = None) -> bytes:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    headers["Authorization"] = f"Basic {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()

def main() -> None:
    work = Path(sys.argv[1] if len(sys.argv) > 1 else "work").resolve()
    rec = work / "fixtures/miniflux/recorded"
    rec.mkdir(parents=True, exist_ok=True)
    base = os.environ.get("MINIFLUX_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
    username = os.environ.get("MINIFLUX_USERNAME", "admin")
    password = os.environ.get("MINIFLUX_PASSWORD", "test123")
    feed_url = os.environ.get("AT006_FEED_URL", "http://127.0.0.1:18080/synthetic_local_test_feed.xml")
    create_bytes = request("POST", f"{base}/v1/feeds", username=username, password=password, payload={"feed_url": feed_url})
    (rec / "create_feed_response.json").write_bytes(create_bytes)
    feeds_bytes = request("GET", f"{base}/v1/feeds", username=username, password=password)
    (rec / "feeds_response.json").write_bytes(feeds_bytes)
    feeds = json.loads(feeds_bytes)
    if not feeds:
        raise SystemExit("No feeds returned by Miniflux API")
    feed_id = feeds[0]["id"]
    (rec / "feed_id.txt").write_text(str(feed_id) + "\n", encoding="utf-8")
    refresh_bytes = request("PUT", f"{base}/v1/feeds/{feed_id}/refresh", username=username, password=password)
    (rec / "refresh_response.txt").write_bytes(refresh_bytes)
    raw = request("GET", f"{base}/v1/feeds/{feed_id}/entries", username=username, password=password)
    (rec / "entries_api_response.json").write_bytes(raw)
    response = json.loads(raw)
    entries = response.get("entries", []) if isinstance(response, dict) else []
    if not entries:
        raise SystemExit("Miniflux API returned no entries")
    entry = entries[0]
    entry_bytes = json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    (rec / "entry_canonical.json").write_bytes(entry_bytes)
    feed_bytes = (work / "fixtures/miniflux/synthetic_local_test_feed.xml").read_bytes()
    miniflux_sha = hashlib.sha256(Path("/tmp/miniflux").read_bytes()).hexdigest()
    provenance = {
        "capture_class": "RECORDED_NON_PRODUCTION_MINIFLUX_API",
        "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "miniflux_version_basis": "2.3.3",
        "miniflux_commit_basis": "c4d54f8",
        "miniflux_binary_sha256": miniflux_sha,
        "expected_miniflux_binary_sha256": "237bf0aed05e86c235b6bcfbad843bfc7bcdd6a628ece672eae3d1e013ddd244",
        "origin_feed_url": feed_url,
        "origin_feed_sha256": hashlib.sha256(feed_bytes).hexdigest(),
        "api_endpoint": f"{base}/v1/feeds/{feed_id}/entries",
        "api_response_sha256": hashlib.sha256(raw).hexdigest(),
        "canonical_entry_sha256": hashlib.sha256(entry_bytes).hexdigest(),
        "entry_id": entry.get("id"),
        "entry_published_at": entry.get("published_at"),
        "entry_changed_at": entry.get("changed_at"),
        "github_repository": os.environ.get("GITHUB_REPOSITORY"),
        "github_ref": os.environ.get("GITHUB_REF"),
        "github_sha": os.environ.get("GITHUB_SHA"),
    }
    (rec / "provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(provenance, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
