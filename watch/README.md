# watch/ — ESP32-S3 Firmware

**Board:** LilyGO T-Display-S3 (ESP32-S3, 170×320, 8 MB PSRAM, 16 MB flash)  
**Branch:** `Suyog`

## Bare board (no breadboard / no soldering yet)

You can still prove Wi-Fi + LCD over USB before mic/amp are wired:

1. Plug T-Display-S3 via USB-C.
2. Arduino IDE → Board **ESP32S3 Dev Module**, USB CDC On Boot **Enabled**, PSRAM **OPI**, Flash **16 MB**.
3. Confirm in `watch.ino`:
   - `WIFI_SSID` = `Rice Visitor` (or your hotspot)
   - `SERVER` = your laptop LAN IP (currently `http://168.5.130.8:8000`)
4. Flash `watch.ino`. Onboard button **GPIO 14** is the talk fallback — no external button needed.
5. Expect LCD states: `BUDDY` → (hold btn) `LISTENING` → `THINKING` / canned play.
6. Mic/amp silence is OK until soldering — focus on Wi-Fi join + screen + LittleFS playback.

## Canned WAVs (LittleFS)

Already generated into `watch/data/`:

- `goals_ok.wav`
- `off_task.wav`

Upload LittleFS (Arduino LittleFS upload plugin or PlatformIO `uploadfs`) so offline speech works.

Regenerate anytime:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" D:\Buddy\voice\eleven.py
```

## Full pin map (after soldering)

| Signal | GPIO |
|---|---|
| Power enable | 15 |
| Mic BCLK / WS / DATA | 1 / 2 / 3 |
| Amp BCLK / LRCLK / DIN / EN | 10 / 11 / 12 / 13 |
| Talk button | 16 |
| Fallback button | 14 |

## Loopback later

With mic+amp wired: hold button, speak, release — hear yourself or API reply on the 3W speaker.
