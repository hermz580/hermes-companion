# RUNBOOK — Multi-Device Pet Sync (v0.2)

Goal: two machines (desktop = always-on relay host, laptop = remote pet) run
The Alpha And from the SAME event stream and respond the same; grabbing one
moves the other.

## Architecture (one relay per fleet)

```
DESKTOP (192.168.0.174)                    LAPTOP
  Hermes -> plugin -> events.jsonl           Hermes -> plugin -> events.jsonl
                 |                                  |
                 v                                  v
        live --grab --relay 127.0.0.1      live --grab --relay 192.168.0.174:49000
                 |                                  |
                 +-----------> RELAY (49000) <------+
                     token-gated fan-out + grab
```

- The relay is a dumb, token-gated pipe: events are allow-list sanitized at
  the wire, a wrong token is silently rejected (M4 forge gate), renderers
  never influence behavior upstream. **Off by default** — only started when
  the launcher / `--relay` is used.
- Deterministic engine + seed means identical input -> identical behavior on
  every machine; no state sync needed.

## Shared token

Both machines MUST use the same token. The desktop generated one at
`%LOCALAPPDATA%\hermes\secrets\companion-relay-token.txt`.

## Desktop (this box) — DONE, auto-starting

1. `launch/companion-relay.cmd` — starts the relay on 0.0.0.0:49000,
   auto-creates the token file, logs to `%LOCALAPPDATA%\hermes\companion\relay.log`.
2. `launch/Hermes_Companion_Relay.vbs` — installed in the Startup folder,
   launches the relay hidden at boot (same pattern as Hermes_Gateway.vbs).
3. `launch/companion-pet.cmd` — double-click to bring up the pet with grab
   + auto-join to the local relay.

Manual start (if not auto-started):
```bat
C:\Users\HarpStar\hermes_companion\launch\companion-relay.cmd
```

## Laptop — ONE-TIME roll-forward

```bash
cd C:\Users\HarpStar\hermes_companion
git pull origin master
python plugin\install.py
hermes plugins enable hermes-companion
```

Copy the token from the desktop to the laptop (same path):
```bash
# on the laptop, create the file with the SAME 32-hex value as the desktop:
notepad %LOCALAPPDATA%\hermes\secrets\companion-relay-token.txt
```
(Or skip the file and pass `--token <SAME>` on the command line / set
`HERMES_COMPANION_TOKEN`.)

## Joining the relay

Desktop pet (already wired via companion-pet.cmd):
```bash
python -m hermes_companion live --grab --relay 127.0.0.1:49000 --token <SAME>
```

Laptop pet (point at the desktop's LAN IP):
```bash
python -m hermes_companion live --grab --relay 192.168.0.174:49000 --token <SAME>
```

> If the laptop is on a different network (not home Wi-Fi), the relay won't
> be reachable — both machines must be on the same LAN. There is no internet
> relay by design (privacy: a pet never phones home).

## Two-machine acceptance test (do this once)

1. Desktop: relay up (`netstat -ano | findstr 49000` shows LISTENING).
2. Both: pet up, both show `RELAY ... token=set` and `LIVE READY`.
3. On the DESKTOP, run a terminal tool call (e.g. `hermes chat -q "run: sleep 3 && echo hi"`).
   -> BOTH pets should run the terminal category chain (dash -> terminal_work).
4. Drag the desktop pet -> laptop pet should move to the same spot.
5. Drag the laptop pet -> desktop pet moves.

## Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| `WinError 10013` on bind | Port 49000 is in a Windows-excluded range on that box. Run `netsh int ipv4 show excludedportrange protocol=tcp`; pick a free port and change `--port` on relay + all `--relay` args. |
| Pet starts but `RELAY` line missing | Relay not running or token mismatch. Check relay.log; confirm both use the same token. |
| Pet shows `WATCHING ...` but no events | Plugin not installed/enabled on that machine: `python plugin\install.py` then `hermes plugins enable hermes-companion`. |
| One pet moves but the other doesn't | Machines on different networks / relay not reachable. `ping 192.168.0.174` from the laptop. |
| Relay died | `launch/companion-relay.cmd` restarts it (or it auto-starts at next boot). Check `%LOCALAPPDATA%\hermes\companion\relay.log`. |

## Files

- `renderer/relay.py` — relay server + client (token-gated dumb pipe)
- `launch/companion-relay.cmd` / `launch/companion-pet.cmd` / `launch/Hermes_Companion_Relay.vbs`
- `tests/test_relay.py` — 9/9 loopback incl. M4 forge gate
