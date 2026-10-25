#!/usr/bin/env bash
# Copy the engine's data/base_rates.sqlite onto the Maritime agent's /data volume. Every engine
# page answers 500 until this has run once; run it again after each engine rebuild.
#
#   scripts/push_rates.sh [agent-id]
exec "$(dirname "$0")/push_data.sh" base_rates.sqlite "$@"
