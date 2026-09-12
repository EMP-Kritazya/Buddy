# watch/ — ESP32-S3 Firmware

**Board:** LilyGO T-Display-S3 (ESP32-S3, 170×320, 8 MB PSRAM, 16 MB flash)

## Before flashing

1. Open `buddy.ino` and set your Wi-Fi credentials and laptop IP:
   ```cpp
   const char* WIFI_SSID = "your_network";
   const char* WIFI_PASS = "your_password";
   const char* SERVER    = "http://192.168.x.x:8000";
   ```

2. Arduino IDE board settings:
   - Board: **ESP32S3 Dev Module**
   - USB CDC On Boot: **Enabled**
   - PSRAM: **OPI PSRAM**
   - Flash Size: **16 MB**
   - Partition Scheme: **16M Flash (3MB APP / 9.9MB FATFS)**

3. Libraries needed:
   - TFT_eSPI (configure for LilyGO T-Display-S3)
   - ESP32 Arduino core ≥ 2.0

## Uploading canned WAVs (offline fallback)

Run `python voice/eleven.py` first — it writes `audio/goals_ok.wav` and `audio/off_task.wav`.

Then copy both files into `watch/data/`:
```
watch/data/goals_ok.wav
watch/data/off_task.wav
```

Upload to LittleFS using the [Arduino LittleFS Upload plugin](https://github.com/earlephilhower/arduino-littlefs-upload)
or with PlatformIO: `pio run --target uploadfs`.

## Loopback test (no cloud)

With no backend running, hold the button and speak. Release — the watch plays
the canned `goals_ok.wav` from LittleFS through the speaker.

## Pin map

| Signal | GPIO |
|---|---|
| Power enable | 15 |
| Mic BCLK | 1 |
| Mic WS | 2 |
| Mic DATA | 3 |
| Amp BCLK | 10 |
| Amp LRCLK | 11 |
| Amp DIN | 12 |
| Amp SD/EN | 13 |
| Talk button | 16 |
| Fallback button | 14 |
