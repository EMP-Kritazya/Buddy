# watch/ — ESP32-S3 Firmware

**Owner:** Suyog (P1)  
**Hardware:** LilyGO T-Display-S3 (ESP32-S3, 170×320, 8 MB PSRAM)

## What lives here

| File | Purpose |
|---|---|
| `buddy.ino` | Main Arduino sketch — mic, amp, button, display, Wi-Fi |

## Responsibilities

- GPIO 15 HIGH at boot (LCD + header rail power)
- I2S0 (RX) — INMP441/SPH0645 mic at 16 kHz 16-bit mono
- I2S1 (TX) — MAX98357A amp at 16 kHz 16-bit mono
- Button GPIO 16 (INPUT_PULLUP, LOW = pressed), fallback GPIO 14
- TFT_eSPI display — screens: `BUDDY / LISTENING / THINKING / SPEAKING / ON TASK / OFF TASK`
- Record to PSRAM (max 8 s), POST raw PCM to `http://LAPTOP:8000/voice`
- Play WAV/PCM response on I2S1
- Poll `GET /pending-speech` every 2 s for proactive coaching audio

## Pin map

| Signal | GPIO |
|---|---|
| LCD power enable | 15 |
| Mic BCLK | 1 |
| Mic LRCLK | 2 |
| Mic DATA | 3 |
| Amp BCLK | 10 |
| Amp LRCLK | 11 |
| Amp DIN | 12 |
| Amp SD/SHDN | 13 |
| Talk button | 16 (14 fallback) |

## Arduino / PlatformIO settings

- Board: `ESP32S3 Dev Module`
- USB CDC On Boot: Enabled
- PSRAM: OPI PSRAM
- Flash: 16 MB

## Before you flash

1. Edit `WIFI_SSID`, `WIFI_PASS`, and `SERVER` (laptop IP) in `buddy.ino`
2. Confirm mic wiring with a 2-second loopback test before any cloud call

## Tonight exit

- [ ] LCD shows `BUDDY` at boot
- [ ] Button held → `LISTENING` → release → audio plays back on 3 W speaker (loopback — no cloud needed yet)
- [ ] Watch POSTs to `/voice` over Wi-Fi and plays the response WAV
