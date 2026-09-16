"""Download public sources atomically, with checksums and bounded concurrency."""

import argparse, concurrent.futures, datetime, hashlib, json, time, urllib.request
from pathlib import Path


def fetch(item):
    url, path = item
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "CommandLabResearch/0.1"}
            )
            with urllib.request.urlopen(req, timeout=150) as response:
                content = response.read()
            if len(content) < 100 or content.lstrip().startswith(b"<"):
                raise ValueError("Invalid download")
            if "statcast_search" in url and content.count(b"\n") >= 25001:
                raise ValueError("Statcast row cap reached; reduce batch size")
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_bytes(content)
            tmp.replace(path)
            print(path.name, len(content), flush=True)
            return
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2**attempt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--statcast", action="store_true")
    ap.add_argument("--year", type=int, default=2025)
    ap.add_argument("--start")
    ap.add_argument("--end")
    a = ap.parse_args()
    jobs = []
    if a.statcast:
        start = (
            datetime.date.fromisoformat(a.start)
            if a.start
            else datetime.date(a.year, 3, 18)
        )
        end = (
            datetime.date.fromisoformat(a.end)
            if a.end
            else datetime.date(a.year, 9, 29)
        )
        while start < end:
            stop = min(start + datetime.timedelta(days=2), end)
            url = f"https://baseballsavant.mlb.com/statcast_search/csv?all=true&type=details&game_date_gt={start}&game_date_lt={stop}&group_by=name&min_pitches=0"
            jobs.append((url, a.out / f"statcast-{start}.csv"))
            start = stop + datetime.timedelta(days=1)
    else:
        for table in ["targets", "pbp_info"]:
            jobs.append(
                (
                    f"https://huggingface.co/datasets/tomdoyo/open-command/resolve/main/{a.year}/{table}.csv.gz",
                    a.out / f'{"pbp" if table=="pbp_info" else table}-{a.year}.csv.gz',
                )
            )
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(fetch, jobs))
    manifest = [
        {
            "url": url,
            "file": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
        }
        for url, path in jobs
    ]
    (
        a.out / f'manifest-{a.year}-{"statcast" if a.statcast else "opencommand"}.json'
    ).write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
