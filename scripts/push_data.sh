#!/usr/bin/env bash
# Copy one file from data/ onto the Maritime agent's /data volume, at the same path under /data.
#
#   scripts/push_data.sh base_rates.sqlite [agent-id]    # the engine (scripts/push_rates.sh)
#   scripts/push_data.sh watcher.sqlite [agent-id]       # confirmed news, stories and insights
#   scripts/push_data.sh sim/returns.csv [agent-id]      # the plan range table (/range, /plan-range)
#   scripts/push_data.sh sim/sources.json [agent-id]     # where that table's series came from
#
# data/ is gitignored, so the image Maritime builds from GitHub has none of these. /data survives
# sleep and redeploys. A database is snapshotted with sqlite's backup API, so a copy never
# catches a half-written database; the sim files are copied as they are. Maritime's file upload refuses bodies above about 80 KB (measured
# 2026-10-25: 80,000 bytes upload, 100,000 bytes return "Write failed"), so the snapshot goes up
# gzipped in 80 KB chunks and is joined, unzipped and checksummed inside the VM. The swap is a
# rename, so a reader never sees a half-written file.
set -euo pipefail

NAME="${1:?usage: scripts/push_data.sh <file in data/> [agent-id]}"
AGENT="${2:-eeaab0d3-f621-4548-b8c8-6a5fe0e8f0ea}"
SRC="data/$NAME"
CHUNK_BYTES=80000
MARITIME=(npx --no-install maritime)

[[ "$NAME" =~ ^([a-z_]+\.sqlite|sim/returns\.csv|sim/sources\.json)$ ]] \
  || { echo "expected watcher.sqlite, sim/returns.csv or sim/sources.json" >&2; exit 1; }
[[ -f "$SRC" ]] || { echo "no $SRC" >&2; exit 1; }
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

if [[ "$NAME" == *.sqlite ]]; then
  python3 -c 'import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close()' \
    "$SRC" "$work/snap"
else
  cp "$SRC" "$work/snap"
fi
want="$(shasum -a 256 "$work/snap" | cut -d' ' -f1)"
gzip -9 -c "$work/snap" > "$work/data.gz"
split -b "$CHUNK_BYTES" -a 3 "$work/data.gz" "$work/data.part."
parts=("$work"/data.part.*)
inbox="/data/inbox/${NAME//[\/.]/_}"
echo "uploading ${#parts[@]} chunks of $(wc -c < "$work/data.gz") gzipped bytes"

"${MARITIME[@]}" exec "$AGENT" --json \
  --body-json "{\"command\":\"rm -rf $inbox && mkdir -p $inbox\"}" > /dev/null
for part in "${parts[@]}"; do
  "${MARITIME[@]}" files upload "$AGENT" "$part" --dest-dir "$inbox" --json > /dev/null
done

join="mkdir -p $(dirname "/data/$NAME") && cat $inbox/data.part.* | gunzip > /data/$NAME.new"
check="test \"\$(sha256sum /data/$NAME.new | cut -d' ' -f1)\" = $want"
swap="mv /data/$NAME.new /data/$NAME && rm -rf $inbox"
"${MARITIME[@]}" exec "$AGENT" --json \
  --body-json "$(python3 -c 'import json,sys; print(json.dumps({"command": sys.argv[1]}))' \
    "$join && $check && $swap && echo ok")" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin)["results"]; print(r["stdout"].strip() or r["stderr"]); sys.exit(r["exitCode"])'
echo "$NAME on $AGENT matches sha256 $want"
