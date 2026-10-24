#!/usr/bin/env bash
# Copy the engine's data/base_rates.sqlite onto the Maritime agent's /data volume.
#
#   scripts/push_rates.sh [agent-id]
#
# data/ is gitignored, so the image Maritime builds from GitHub has no engine sqlite, and every
# engine page answers 500 until this runs. /data survives sleep and redeploys, so run it once
# after each engine rebuild. Maritime's file upload refuses bodies above about 80 KB (measured
# 2026-10-25: 80,000 bytes upload, 100,000 bytes return "Write failed"), so the file goes up
# gzipped in 80 KB chunks and is joined, unzipped and checksummed inside the VM. The swap is a
# rename, so a reader never sees a half-written file.
set -euo pipefail

AGENT="${1:-eeaab0d3-f621-4548-b8c8-6a5fe0e8f0ea}"
SRC="data/base_rates.sqlite"
CHUNK_BYTES=80000
MARITIME=(npx --no-install maritime)

[[ -f "$SRC" ]] || { echo "no $SRC; build it with the engine first" >&2; exit 1; }
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

want="$(shasum -a 256 "$SRC" | cut -d' ' -f1)"
gzip -9 -c "$SRC" > "$work/rates.gz"
split -b "$CHUNK_BYTES" -a 3 "$work/rates.gz" "$work/rates.part."
parts=("$work"/rates.part.*)
echo "uploading ${#parts[@]} chunks of $(wc -c < "$work/rates.gz") gzipped bytes"

"${MARITIME[@]}" exec "$AGENT" --json \
  --body-json '{"command":"rm -rf /data/inbox/rates && mkdir -p /data/inbox/rates"}' > /dev/null
for part in "${parts[@]}"; do
  "${MARITIME[@]}" files upload "$AGENT" "$part" --dest-dir /data/inbox/rates --json > /dev/null
done

join="cat /data/inbox/rates/rates.part.* | gunzip > /data/base_rates.sqlite.new"
check="test \"\$(sha256sum /data/base_rates.sqlite.new | cut -d' ' -f1)\" = $want"
swap="mv /data/base_rates.sqlite.new /data/base_rates.sqlite && rm -rf /data/inbox/rates"
"${MARITIME[@]}" exec "$AGENT" --json \
  --body-json "$(python3 -c 'import json,sys; print(json.dumps({"command": sys.argv[1]}))' \
    "$join && $check && $swap && echo ok")" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin)["results"]; print(r["stdout"].strip() or r["stderr"]); sys.exit(r["exitCode"])'
echo "base_rates.sqlite on $AGENT matches sha256 $want"
