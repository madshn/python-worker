#!/usr/bin/env bash
# SessionStart hook: register local Claude Code session in team_sessions.
# Fire-and-forget — failures are OK, LocalPush will catch up.
set -uo pipefail

INPUT="$(cat)"
SESSION_ID="$(printf '%s' "$INPUT" | jq -r '.session_id // empty')"
CWD="$(printf '%s' "$INPUT" | jq -r '.cwd // empty')"

[ -n "$SESSION_ID" ] || exit 0
[ -n "$CWD" ] || exit 0

# All actors — must match rightaim.team actor names
ACTOR="unknown"
case "$CWD" in
  # team
  /Users/madsnissen/team/principal*)       ACTOR="mads" ;;
  /Users/madsnissen/team/bob*)             ACTOR="bob" ;;
  /Users/madsnissen/team/mira*)            ACTOR="mira" ;;
  /Users/madsnissen/team/aston*)           ACTOR="aston" ;;
  /Users/madsnissen/team/rex*)             ACTOR="rex" ;;
  /Users/madsnissen/team/metrick*)         ACTOR="metrick" ;;
  /Users/madsnissen/team/leah*)            ACTOR="leah" ;;
  # ops
  /Users/madsnissen/ops/cloud-agent-host*) ACTOR="cah" ;;
  /Users/madsnissen/ops/file-kiosk*)       ACTOR="kiosk" ;;
  /Users/madsnissen/ops/python-worker*)    ACTOR="pyworker" ;;
  /Users/madsnissen/ops/rightaim-ai*)      ACTOR="raw" ;;
  /Users/madsnissen/ops/walkietalkieweb*)  ACTOR="wtw" ;;
  # builds
  /Users/madsnissen/builds/localpush*)       ACTOR="lpush" ;;
  /Users/madsnissen/builds/preloadedyear*)   ACTOR="ply" ;;
  /Users/madsnissen/builds/spawnby*)         ACTOR="spawn" ;;
  /Users/madsnissen/builds/mdm*)             ACTOR="mdm" ;;
  /Users/madsnissen/builds/yahboom*)         ACTOR="yahboom" ;;
  /Users/madsnissen/builds/pogo*)            ACTOR="pogo" ;;
esac

REPO="unknown"
RELATIVE="${CWD#/Users/madsnissen/}"
if [[ "$RELATIVE" =~ ^(team|ops|builds|crafts|oss)/([^/]+) ]]; then
  REPO="madshn/${BASH_REMATCH[2]}"
fi

SHORT_ID="${SESSION_ID:0:12}"
TS_ID="${ACTOR}.local.${SHORT_ID}"

ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ0cXF1bWxncG9odHFqYXJ6a3VhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njc2OTUxMDksImV4cCI6MjA4MzI3MTEwOX0.x-8QnxdKPVJoyvmAKg-N83t5AIADgQDlicDnzzGeo0I"
SUPABASE_URL="https://btqqumlgpohtqjarzkua.supabase.co"

curl -fsS -X POST "${SUPABASE_URL}/rest/v1/rpc/register_local_session" \
  -H "apikey: ${ANON_KEY}" \
  -H "Authorization: Bearer ${ANON_KEY}" \
  -H "Content-Type: application/json" \
  -d "$(jq -n \
    --arg id "$TS_ID" \
    --arg actor "$ACTOR" \
    --arg repo "$REPO" \
    --arg workdir "$CWD" \
    '{p_id: $id, p_actor: $actor, p_repo: $repo, p_workdir: $workdir}')" \
  >/dev/null 2>&1 || true

exit 0
