#!/usr/bin/env bash
# Copy one sqlite file from data/ onto the Maritime agent's /data volume.
#
#   scripts/push_data.sh base_rates.sqlite [agent-id]    # the engine (scripts/push_rates.sh)
#   scripts/push_data.sh watcher.sqlite [agent-id]       # confirmed news, stories and insights
#
# data/ is gitignored, so the image Maritime builds from GitHub has neither file. /data survives
# sleep and redeploys. The file is snapshotted with sqlite's backup API, so a copy never catches
# a half-written database. Maritime's file upload refuses bodies above about 80 KB (measured
# 2026-10-25: 80,000 bytes upload, 100,000 bytes return "Write failed"), so the snapshot goes up
# gzipped in 80 KB chunks and is joined, unzipped and checksummed inside the VM. The swap is a
# rename, so a reader never sees a half-written file.
set -euo pipefail

NAME="${1:?usage: scripts/push_data.sh <file in data/> [agent-id]}"
AGENT="${2:-eeaab0d3-f621-4548-b8c8-6a5fe0e8f0ea}"
SRC="data/$NAME"
CHUNK_BYTES=80000
MARITIME=(npx --no-install maritime)

[[ "$NAME" =~ ^[a-z_]+\.sqlite$ ]] || { echo "expected a name like watcher.sqlite" >&2; exit 1; }
[[ -f "$SRC" ]] || { echo "no $SRC" >&2; exit 1; }
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

python3 -c 'import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close()' \
  "$SRC" "$work/snap.sqlite"
want="$(shasum -a 256 "$work/snap.sqlite" | cut -d' ' -f1)"
gzip -9 -c "$work/snap.sqlite" > "$work/data.gz"
split -b "$CHUNK_BYTES" -a 3 "$work/data.gz" "$work/data.part."
parts=("$work"/data.part.*)
inbox="/data/inbox/${NAME%.sqlite}"
echo "uploading ${#parts[@]} chunks of $(wc -c < "$work/data.gz") gzipped bytes"

"${MARITIME[@]}" exec "$AGENT" --json \
  --body-json "{\"command\":\"rm -rf $inbox && mkdir -p $inbox\"}" > /dev/null
for part in "${parts[@]}"; do
  "${MARITIME[@]}" files upload "$AGENT" "$part" --dest-dir "$inbox" --json > /dev/null
done

join="cat $inbox/data.part.* | gunzip > /data/$NAME.new"
check="test \"\$(sha256sum /data/$NAME.new | cut -d' ' -f1)\" = $want"
swap="mv /data/$NAME.new /data/$NAME && rm -rf $inbox"
"${MARITIME[@]}" exec "$AGENT" --json \
  --body-json "$(python3 -c 'import json,sys; print(json.dumps({"command": sys.argv[1]}))' \
    "$join && $check && $swap && echo ok")" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin)["results"]; print(r["stdout"].strip() or r["stderr"]); sys.exit(r["exitCode"])'
echo "$NAME on $AGENT matches sha256 $want"
