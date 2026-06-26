#!/bin/bash
# dokan-liveness — host-launchd watchdog for the dokan platform.
# The ONE monitor that CANNOT live in dokan (it watches dokan): every other watchdog is a dokan
# script, so when dokan itself dies nothing alerts (proven by the 2026-06-26 colima outage).
# CTO-authorized exception to zero-local (host-launchd). Pings dokan /api/runs; alerts the RELAY
# (host process, stays up when dokan dies) → cto, edge-deduped (down once, recovery once).
# Git review mirror: trovex growth/ops/dokan-liveness.sh.
set -u
TOKEN=$(cat "$HOME/.config/dokan/token" 2>/dev/null)
STATE="/tmp/dokan-liveness.state"
DOKAN="http://localhost:8088/api/runs?limit=1"
RELAY="http://localhost:8090/mcp"
ALERT_TO="${DOKAN_LIVENESS_ALERT_TO:-cto}"
DOKAN_URL="${DOKAN_LIVENESS_URL:-$DOKAN}"

code=$(curl -s -m 8 -o /dev/null -w '%{http_code}' -H "authorization: Bearer $TOKEN" "$DOKAN_URL" 2>/dev/null)
now="UP"; [ "$code" = "200" ] || now="DOWN"
prev=$(cat "$STATE" 2>/dev/null || echo "UP")
echo "$now" > "$STATE"

notify() { # $1 priority $2 subject $3 content
  ALERT_TO="$ALERT_TO" python3 - "$1" "$2" "$3" <<'PY'
import sys,os,json,urllib.request
p,s,c=sys.argv[1],sys.argv[2],sys.argv[3]
rpc={"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"call_tool","arguments":{"tool":"send_message","args":{
  "project":"trovex-growth","as":"fullstack-lead","to":os.environ.get("ALERT_TO","cto"),"priority":p,"type":"notification","subject":s,"content":c}}}}
try: urllib.request.urlopen(urllib.request.Request("http://localhost:8090/mcp",data=json.dumps(rpc).encode(),headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"},method="POST"),timeout=8)
except Exception: pass
PY
}

if [ "$now" = "DOWN" ] && [ "$prev" = "UP" ]; then
  notify "P0" "🔴 dokan DOWN — /api/runs unreachable (host-liveness)" "dokan-liveness (host-launchd, runs OUTSIDE dokan by design): dokan /api/runs returned '$code' (not 200). The dokan platform is likely down → monitors + the lead-machine 395 offline. Check colima/containers/forwarding (2026-06-26 playbook: colima restart + docker start dokan-db)."
elif [ "$now" = "UP" ] && [ "$prev" = "DOWN" ]; then
  notify "P3" "🟢 dokan recovered (host-liveness)" "dokan-liveness: dokan /api/runs = 200 again."
fi
echo "$(date -u +%FT%TZ) dokan-liveness: code=$code state=$now (prev=$prev)"
