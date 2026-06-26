# dokan-liveness (host-launchd watchdog)

The ONE monitor that **cannot live in dokan** — it watches dokan. Every other watchdog
(infra-watch, hand-raiser-heartbeat) is a dokan script, so when dokan itself dies, nothing
alerts (proven by the 2026-06-26 colima-forwarding outage). CTO-authorized exception to the
zero-local rule (host-launchd).

- **Runnable:** `~/.config/trovex-growth/dokan-liveness.sh` (this dir = the review mirror + canonical source).
- **Schedule:** launchd `com.tsukumo.dokan-liveness`, `StartInterval` 300s (5 min), `RunAtLoad`.
- **Behavior:** pings dokan `/api/runs`; on a healthy→down edge → relay P0 to cto; recovery → P3. Edge-deduped via `/tmp/dokan-liveness.state`. Alerts the RELAY (host process, stays up when dokan dies).
- **Install:** `cp dokan-liveness.sh ~/.config/trovex-growth/ && cp com.tsukumo.dokan-liveness.plist ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/com.tsukumo.dokan-liveness.plist`
- **Test:** `DOKAN_LIVENESS_URL=http://localhost:9999/dead DOKAN_LIVENESS_ALERT_TO=fullstack-lead bash dokan-liveness.sh` (forces a down alert to yourself).
