/*
  Buddy Watch firmware â€” LilyGO T-Display-S3 (ESP32-S3)
  I2S0 = mic (RX), I2S1 = amp (TX)
  Button GPIO 16 (pull-up, LOW = pressed), fallback GPIO 14
  Display: TFT_eSPI with LilyGO T-Display-S3 user setup

  Canned WAVs in FFat: /goals_ok.wav, /off_task.wav, /network_issue.wav.
  Upload them once with the Arduino FFat upload tool or PlatformIO
  after running: python voice/eleven.py  (generates audio/*.wav).
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <driver/i2s.h>
#include "TFT_eSPI.h"
#include "FS.h"
#include "FFat.h"
#include <string.h>

// ---------------------------------------------------------------------------
// Wi-Fi / server  â€” edit before flashing
// ---------------------------------------------------------------------------
const char* WIFI_SSID   = "Rice Visitor";
const char* WIFI_PASS   = "";
const char* SERVER      = "http://168.5.148.43:8000";  // laptop LAN IP
const char* VOICE_URL   = "/voice";
const char* PENDING_URL = "/pending-speech";

// ---------------------------------------------------------------------------
// Pin map
// ---------------------------------------------------------------------------
#define PWR_EN      15   // must be HIGH at boot â€” powers LCD + header rails
#define BTN_PIN     16   // push-to-talk (external)
#define BTN_FALLBK  14   // onboard button 2

// I2S0 â€” mic (RX)
#define MIC_SCK   1
#define MIC_WS    2
#define MIC_SD    3

// I2S1 â€” amp (TX)
#define AMP_BCLK  10
#define AMP_LRCK  11
#define AMP_DIN   12
#define AMP_SD    13   // HIGH = amp enabled

// ---------------------------------------------------------------------------
// Audio config
// ---------------------------------------------------------------------------
#define SAMPLE_RATE     16000
#define BIT_DEPTH       16
#define MAX_REC_S       45  // hold-to-talk; hard ceiling so PSRAM can't be exhausted
#define MAX_REC_BYTES   (SAMPLE_RATE * 4 * MAX_REC_S)  // 32-bit I2S words while holding

// Tap-to-talk + end-on-silence (VAD). True "Hey Buddy" wake word is not on-device yet.
#define VAD_SPEECH_THRESH  1200   // abs PCM peak to count as speech (after >>15)
#define VAD_SILENCE_MS     1200   // stop after this much quiet once user has spoken
#define VAD_MIN_SPEECH_MS   400   // need at least this much speech before silence can end
#define VAD_MAX_WAIT_MS   12000   // if no speech after tap, give up
#define PLAY_CHUNK      2048   // I2S write chunk for streaming playback

// Set to 1 to test mic: hold button, speak, release — hear yourself on the speaker (no cloud).
// Set back to 0 when mic is verified and you want POST /voice again.
#define MIC_LOOPBACK_TEST 0

// Digital playback boost (1=unity, 2= +6dB-ish, 3=louder). Soft-clips to avoid harsh square waves.
#define SPEAKER_GAIN 4

// ---------------------------------------------------------------------------
// Globals
// ---------------------------------------------------------------------------
TFT_eSPI tft = TFT_eSPI();

uint8_t* recBuf   = nullptr;
size_t   recBytes = 0;

unsigned long lastPollMs = 0;
const unsigned long POLL_INTERVAL = 2000;

enum BuddyState { S_IDLE, S_LISTENING, S_THINKING, S_SPEAKING, S_ON_TASK, S_OFF_TASK };
BuddyState curState = S_IDLE;
uint8_t animFrame = 0;
unsigned long lastAnimMs = 0;
bool wifiOk = false;

// ---------------------------------------------------------------------------
// Forward declarations
// ---------------------------------------------------------------------------
void showState(BuddyState s);
void animateUI();
void drawChrome(uint16_t accent, const char* title, const char* subtitle);
void recordAndSend();
void pollPendingSpeech();
void streamAndPlay(WiFiClient& stream, int contentLen);
void playPCM(const uint8_t* data, size_t len);
void stopSpeaker();
void startSpeaker();
void i2sWriteGained(const uint8_t* data, size_t len);
void playFile(const char* path);
void ensureCannedWavs();
bool downloadToFFat(const char* urlPath, const char* destPath);

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);

  // Power rail â€” must be first
  pinMode(PWR_EN, OUTPUT);
  digitalWrite(PWR_EN, HIGH);
  delay(100);

  // Amp enable
  pinMode(AMP_SD, OUTPUT);
  digitalWrite(AMP_SD, HIGH);

  // Buttons
  pinMode(BTN_PIN,    INPUT_PULLUP);
  pinMode(BTN_FALLBK, INPUT_PULLUP);

  // Display
  tft.init();
  tft.setRotation(1);
  showState(S_IDLE);

  // PSRAM record buffer
  recBuf = (uint8_t*)ps_malloc(MAX_REC_BYTES);
  if (!recBuf) {
    tft.println("PSRAM alloc fail");
    while (true) delay(1000);
  }

    // FFat — canned WAV fallbacks (format once if empty / wrong partition)
  if (!FFat.begin(false)) {
    Serial.println("[warn] FFat mount failed — formatting...");
    if (!FFat.begin(true)) {
      Serial.println("[err] FFat format failed. In Arduino: Tools → Partition Scheme → 16M Flash (3MB APP / 9.9MB FATFS) then re-flash + Upload FFat.");
    } else {
      Serial.println("[ok] FFat formatted (empty). Upload watch/data/*.wav via FFat uploader.");
    }
  } else {
    Serial.println("[ok] FFat mounted");
    Serial.printf("[fs] goals_ok=%d off_task=%d network_issue=%d\n",
                  FFat.exists("/goals_ok.wav"),
                  FFat.exists("/off_task.wav"),
                  FFat.exists("/network_issue.wav"));
  }

  // I2S0 â€” mic
  // Many I2S MEMS mics (INMP441 / SPH0645) need 32-bit slots; audio sits in the top bits.
  i2s_config_t mic_cfg = {
    .mode                 = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate          = SAMPLE_RATE,
    .bits_per_sample      = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format       = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags     = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count        = 8,
    .dma_buf_len          = 256,
    .use_apll             = false,
  };
  i2s_pin_config_t mic_pins = {
    .bck_io_num   = MIC_SCK,
    .ws_io_num    = MIC_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num  = MIC_SD,
  };
  i2s_driver_install(I2S_NUM_0, &mic_cfg, 0, nullptr);
  i2s_set_pin(I2S_NUM_0, &mic_pins);

  // I2S1 â€” amp
  i2s_config_t amp_cfg = {
    .mode                 = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate          = SAMPLE_RATE,
    .bits_per_sample      = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format       = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags     = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count        = 8,
    .dma_buf_len          = 256,
    .use_apll             = false,
  };
  i2s_pin_config_t amp_pins = {
    .bck_io_num   = AMP_BCLK,
    .ws_io_num    = AMP_LRCK,
    .data_out_num = AMP_DIN,
    .data_in_num  = I2S_PIN_NO_CHANGE,
  };
  i2s_driver_install(I2S_NUM_1, &amp_cfg, 0, nullptr);
  i2s_set_pin(I2S_NUM_1, &amp_pins);
  digitalWrite(AMP_SD, LOW);  // Mute amp until we actually play

  // Wi-Fi
  showState(S_THINKING);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("[ok] Wi-Fi IP: ");
    Serial.println(WiFi.localIP());
    wifiOk = true;
    ensureCannedWavs();
    showState(S_IDLE);
  } else {
    wifiOk = false;
    Serial.println("[warn] Wi-Fi failed â€” offline mode");
    tft.fillScreen(TFT_BLACK);
    tft.setTextColor(TFT_RED, TFT_BLACK);
    tft.setTextSize(3);
    tft.setCursor(20, 70);
    tft.println("BUDDY");
    tft.setTextSize(2);
    tft.setCursor(20, 120);
    tft.println("(offline)");
  }
}

// ---------------------------------------------------------------------------
// Loop
// ---------------------------------------------------------------------------
void loop() {
  static bool prevBtn = false;
  bool btnPressed = (digitalRead(BTN_PIN) == LOW) || (digitalRead(BTN_FALLBK) == LOW);

  // Tap edge (press) starts a listen session — no need to hold
  if (btnPressed && !prevBtn) {
    // wait for release so the tap doesn't immediately cancel
    delay(30);
    while ((digitalRead(BTN_PIN) == LOW) || (digitalRead(BTN_FALLBK) == LOW)) {
      delay(10);
    }
    recordAndSend();
    prevBtn = false;
  } else {
    prevBtn = btnPressed;
  }

  if (millis() - lastPollMs > POLL_INTERVAL) {
    lastPollMs = millis();
    pollPendingSpeech();
  }

  // ~12 fps UI animation for listening / thinking / speaking / idle pulse
  if (millis() - lastAnimMs > 80) {
    lastAnimMs = millis();
    animFrame++;
    animateUI();
  }
}

// ---------------------------------------------------------------------------
// Record while button held â†’ POST raw PCM to /voice â†’ stream reply to speaker
// ---------------------------------------------------------------------------
void recordAndSend() {
  // Tap-to-talk: listen until silence (or max), then POST /voice
  showState(S_LISTENING);
  i2s_zero_dma_buffer(I2S_NUM_0);
  recBytes = 0;

  bool heardSpeech = false;
  unsigned long t0 = millis();
  unsigned long lastVoiceMs = 0;
  unsigned long speechMs = 0;
  size_t bytesRead = 0;

  Serial.println("[mic] listening — speak; auto-stops on silence (max 45s)");

  while (recBytes + 512 <= MAX_REC_BYTES) {
    // Second tap cancels / finishes early
    if ((digitalRead(BTN_PIN) == LOW) || (digitalRead(BTN_FALLBK) == LOW)) {
      delay(20);
      if ((digitalRead(BTN_PIN) == LOW) || (digitalRead(BTN_FALLBK) == LOW)) {
        Serial.println("[mic] button — end listen");
        while ((digitalRead(BTN_PIN) == LOW) || (digitalRead(BTN_FALLBK) == LOW)) delay(10);
        break;
      }
    }

    i2s_read(I2S_NUM_0, recBuf + recBytes, 512, &bytesRead, portMAX_DELAY);
    if (bytesRead < 4) continue;

    // Quick peak on this 32-bit chunk (same >>15 as final convert)
    int16_t chunkPeak = 0;
    size_t words = bytesRead / 4;
    const int32_t* w = (const int32_t*)(recBuf + recBytes);
    for (size_t i = 0; i < words; i++) {
      int32_t sample = w[i] >> 15;
      if (sample > 32767) sample = 32767;
      if (sample < -32768) sample = -32768;
      int16_t a = (int16_t)sample;
      if (a < 0) a = -a;
      if (a > chunkPeak) chunkPeak = a;
    }
    recBytes += bytesRead;

    unsigned long now = millis();
    if (chunkPeak >= VAD_SPEECH_THRESH) {
      if (!heardSpeech) {
        heardSpeech = true;
        Serial.printf("[mic] speech detected (peak=%d)\n", (int)chunkPeak);
      }
      lastVoiceMs = now;
      speechMs += (words * 1000) / SAMPLE_RATE;
    }

    if (!heardSpeech) {
      if (now - t0 > VAD_MAX_WAIT_MS) {
        Serial.println("[mic] no speech — cancel");
        showState(S_IDLE);
        return;
      }
      continue;
    }

    if (speechMs >= VAD_MIN_SPEECH_MS && (now - lastVoiceMs) >= VAD_SILENCE_MS) {
      Serial.println("[mic] end of utterance (silence)");
      break;
    }

    if (recBytes + 512 > MAX_REC_BYTES) {
      Serial.printf("[mic] hit max listen length (%d s)\n", MAX_REC_S);
      break;
    }
  }

  if (recBytes < 3200) {   // too short — ignore
    showState(S_IDLE);
    return;
  }

  // 32-bit I2S words -> 16-bit PCM (take upper bits)
  {
    size_t words = recBytes / 4;
    const int32_t* w = (const int32_t*)recBuf;
    int16_t* mono = (int16_t*)recBuf;
    int16_t peak = 0;
    uint32_t nonzero = 0;
    for (size_t i = 0; i < words; i++) {
      // INMP441: 24-bit left-justified in 32-bit slot; >> 14 is a common scale
      int32_t sample = w[i] >> 15;  // balance loudness vs clip for SPH0645
      if (sample > 32767) sample = 32767;
      if (sample < -32768) sample = -32768;
      int16_t s16 = (int16_t)sample;
      mono[i] = s16;
      int16_t a = s16 < 0 ? -s16 : s16;
      if (a > peak) peak = a;
      if (s16 != 0) nonzero++;
    }
    recBytes = words * 2;
    Serial.printf("[mic] 32bit words=%u peak=%d nonzero=%u (want peak>>500, nonzero>>0)\n",
                  (unsigned)words, (int)peak, (unsigned)nonzero);
    if (peak < 10) {
      Serial.println("[mic] HINT: still dead -> check VDD=3.3V, DOUT->GPIO3, BCLK->1, WS->2, L/R to GND then 3.3V, swap BCLK/WS if unsure");
    }
  }

#if MIC_LOOPBACK_TEST
  // Local mic -> speaker loopback (no Wi-Fi / no /voice)
  showState(S_SPEAKING);
  playPCM(recBuf, recBytes);
  showState(S_IDLE);
  return;
#endif

  showState(S_THINKING);


  if (WiFi.status() != WL_CONNECTED) {
    playFile("/network_issue.wav");
    showState(S_IDLE);
    return;
  }

  HTTPClient http;
  http.begin(String(SERVER) + VOICE_URL);
  http.setTimeout(15000);
  http.addHeader("Content-Type", "audio/l16; rate=16000; channels=1");

  int code = http.POST(recBuf, recBytes);

  if (code == 200) {
    showState(S_SPEAKING);
    streamAndPlay(*http.getStreamPtr(), http.getSize());
  } else {
    Serial.printf("[warn] POST /voice â†’ HTTP %d\n", code);
    playFile("/network_issue.wav");
  }

  http.end();
  showState(S_IDLE);
}

// ---------------------------------------------------------------------------
// Poll /pending-speech every 2 s â€” plays proactive coaching with no button press
// ---------------------------------------------------------------------------
void pollPendingSpeech() {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  http.begin(String(SERVER) + PENDING_URL);
  http.setTimeout(3000);

  int code = http.GET();

  if (code == 200 && http.getSize() != 0) {
    showState(S_SPEAKING);
    streamAndPlay(*http.getStreamPtr(), http.getSize());
    showState(S_IDLE);
  }

  http.end();
}

// ---------------------------------------------------------------------------
// Stream HTTP body directly to I2S â€” no heap alloc, handles chunked transfer
// ---------------------------------------------------------------------------
void streamAndPlay(WiFiClient& stream, int contentLen) {
  startSpeaker();
  static uint8_t chunk[PLAY_CHUNK];
  bool headerSkipped = false;
  int remaining = contentLen;  // -1 when chunked (Content-Length absent)

  while (true) {
    int toRead = (remaining > 0) ? min((int)PLAY_CHUNK, remaining) : PLAY_CHUNK;
    int got = stream.readBytes(chunk, toRead);
    if (got <= 0) break;

    uint8_t* ptr = chunk;
    size_t   len = (size_t)got;

    // Skip 44-byte WAV header on first chunk
    if (!headerSkipped) {
      headerSkipped = true;
      if (len > 44 && chunk[0] == 'R' && chunk[1] == 'I' &&
          chunk[2] == 'F' && chunk[3] == 'F') {
        ptr += 44;
        len -= 44;
      }
    }

    i2sWriteGained(ptr, len);

    if (remaining > 0) {
      remaining -= got;
      if (remaining <= 0) break;
    }
  }
}

// ---------------------------------------------------------------------------
// Play raw PCM or WAV already in RAM
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Mute / unmute amp cleanly so I2S underrun doesn't hiss forever
// ---------------------------------------------------------------------------

// Boost int16 PCM into I2S1 (mono). Soft-clips instead of wrapping.
void i2sWriteGained(const uint8_t* data, size_t len) {
  // Process in small chunks so we don't need a huge temp buffer
  static int16_t out[PLAY_CHUNK / 2];
  size_t offset = 0;
  while (offset + 1 < len) {
    size_t nbytes = len - offset;
    if (nbytes > sizeof(out)) nbytes = sizeof(out);
    nbytes &= ~size_t(1);  // even
    size_t nsamp = nbytes / 2;
    const int16_t* in = (const int16_t*)(data + offset);
    for (size_t i = 0; i < nsamp; i++) {
      int32_t v = (int32_t)in[i] * SPEAKER_GAIN;
      if (v > 32767) v = 32767;
      if (v < -32768) v = -32768;
      out[i] = (int16_t)v;
    }
    size_t written = 0;
    size_t left = nsamp * 2;
    const uint8_t* ptr = (const uint8_t*)out;
    while (left > 0) {
      i2s_write(I2S_NUM_1, ptr, left, &written, portMAX_DELAY);
      ptr += written;
      left -= written;
    }
    offset += nbytes;
  }
}

void startSpeaker() {
  digitalWrite(AMP_SD, HIGH);
  delay(10);
}

void stopSpeaker() {
  static uint8_t silence[PLAY_CHUNK];
  memset(silence, 0, sizeof(silence));
  size_t written = 0;
  // ~100ms of digital silence to drain the TX DMA
  for (int i = 0; i < 8; i++) {
    i2s_write(I2S_NUM_1, silence, sizeof(silence), &written, portMAX_DELAY);
  }
  i2s_zero_dma_buffer(I2S_NUM_1);
  digitalWrite(AMP_SD, LOW);  // shut off MAX98357 class-D
}

void playPCM(const uint8_t* data, size_t len) {
  size_t offset = 0;
  if (len > 44 && data[0] == 'R' && data[1] == 'I' && data[2] == 'F' && data[3] == 'F') {
    offset = 44;
  }

  startSpeaker();
  size_t written  = 0;
  size_t remaining = len - offset;
  const uint8_t* ptr = data + offset;

  while (remaining > 0) {
    size_t n = min(remaining, (size_t)PLAY_CHUNK);
    i2sWriteGained(ptr, n);
    ptr       += n;
    remaining -= n;
  }
  stopSpeaker();
}

// ---------------------------------------------------------------------------
// Play a canned WAV from FFat (offline fallback)
// Upload audio/goals_ok.wav and audio/off_task.wav to FFat as
// /goals_ok.wav and /off_task.wav using the Arduino FFat upload tool.
// ---------------------------------------------------------------------------
void playFile(const char* path) {
  if (!FFat.exists(path)) {
    Serial.printf("[warn] canned file missing: %s\n", path);
    return;
  }

  fs::File f = FFat.open(path, "r");
  if (!f) return;

  showState(S_SPEAKING);
  startSpeaker();

  static uint8_t fileBuf[PLAY_CHUNK];
  bool headerSkipped = false;

  while (f.available()) {
    int got = f.read(fileBuf, sizeof(fileBuf));
    if (got <= 0) break;

    uint8_t* ptr = fileBuf;
    size_t   len = (size_t)got;

    if (!headerSkipped) {
      headerSkipped = true;
      if (len > 44 && fileBuf[0] == 'R' && fileBuf[1] == 'I' &&
          fileBuf[2] == 'F' && fileBuf[3] == 'F') {
        ptr += 44;
        len -= 44;
      }
    }

    i2sWriteGained(ptr, len);
  }

  f.close();
  stopSpeaker();
}

// ---------------------------------------------------------------------------
// Display
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Display — 320x170 landscape (rotation 1)
// ---------------------------------------------------------------------------
static const int SCR_W = 320;
static const int SCR_H = 170;

uint16_t accentFor(BuddyState s) {
  switch (s) {
    case S_IDLE:      return tft.color565(80, 160, 255);   // buddy blue
    case S_LISTENING: return tft.color565(255, 80, 120);   // hot pink
    case S_THINKING:  return tft.color565(180, 120, 255);  // purple
    case S_SPEAKING:  return tft.color565(60, 220, 160);   // mint
    case S_ON_TASK:   return tft.color565(60, 200, 100);   // green
    case S_OFF_TASK:  return tft.color565(255, 160, 40);   // amber
  }
  return TFT_WHITE;
}

void drawChrome(uint16_t accent, const char* title, const char* subtitle) {
  tft.fillScreen(tft.color565(10, 12, 20));

  // Top accent bar
  tft.fillRect(0, 0, SCR_W, 6, accent);
  // Soft header strip
  tft.fillRect(0, 6, SCR_W, 28, tft.color565(18, 22, 36));
  tft.setTextDatum(TL_DATUM);
  tft.setTextColor(accent, tft.color565(18, 22, 36));
  tft.setTextSize(2);
  tft.drawString("BUDDY", 12, 12);

  // Wi-Fi pill
  if (wifiOk) {
    tft.fillRoundRect(SCR_W - 78, 10, 66, 18, 4, tft.color565(30, 50, 40));
    tft.setTextColor(tft.color565(80, 220, 140), tft.color565(30, 50, 40));
    tft.setTextSize(1);
    tft.drawString("Wi-Fi", SCR_W - 60, 15);
  } else {
    tft.fillRoundRect(SCR_W - 78, 10, 66, 18, 4, tft.color565(50, 30, 30));
    tft.setTextColor(tft.color565(255, 120, 120), tft.color565(50, 30, 30));
    tft.setTextSize(1);
    tft.drawString("Offline", SCR_W - 68, 15);
  }

  // Main card
  tft.fillRoundRect(16, 46, SCR_W - 32, 100, 10, tft.color565(22, 26, 42));
  tft.drawRoundRect(16, 46, SCR_W - 32, 100, 10, accent);

  // Title
  tft.setTextDatum(MC_DATUM);
  tft.setTextColor(TFT_WHITE, tft.color565(22, 26, 42));
  tft.setTextSize(3);
  tft.drawString(title, SCR_W / 2, 88);

  // Subtitle
  tft.setTextColor(tft.color565(160, 170, 190), tft.color565(22, 26, 42));
  tft.setTextSize(1);
  tft.drawString(subtitle, SCR_W / 2, 122);

  // Bottom accent dots
  for (int i = 0; i < 5; i++) {
    int x = SCR_W / 2 - 40 + i * 20;
    tft.fillCircle(x, SCR_H - 10, 3, (i == (animFrame / 4) % 5) ? accent : tft.color565(40, 45, 60));
  }
}

void drawIdleOrb() {
  int cx = SCR_W / 2;
  int cy = 72;
  uint16_t accent = accentFor(S_IDLE);
  int pulse = 18 + (animFrame % 16);
  if (animFrame % 32 > 16) pulse = 18 + (32 - (animFrame % 32));
  tft.fillCircle(cx, cy, pulse + 8, tft.color565(20, 40, 70));
  tft.fillCircle(cx, cy, pulse, accent);
  tft.fillCircle(cx - 4, cy - 4, pulse / 3, tft.color565(180, 220, 255));
}

void drawWaveform(uint16_t accent) {
  // Clear wave area inside card
  int baseY = 78;
  int left = 40;
  int width = SCR_W - 80;
  tft.fillRect(left, 55, width, 50, tft.color565(22, 26, 42));
  for (int i = 0; i < 16; i++) {
    int h = 6 + ((animFrame * 3 + i * 5) % 17);
    if ((animFrame + i) % 7 == 0) h += 10;
    int x = left + i * (width / 16) + 4;
    tft.fillRoundRect(x, baseY - h / 2, 8, h, 2, accent);
  }
}

void drawThinkingDots(uint16_t accent) {
  int cy = 78;
  int cx = SCR_W / 2;
  tft.fillRect(cx - 50, 60, 100, 40, tft.color565(22, 26, 42));
  for (int i = 0; i < 3; i++) {
    int phase = (animFrame / 3 + i) % 3;
    int r = 5 + phase * 2;
    int y = cy - phase * 2;
    tft.fillCircle(cx - 24 + i * 24, y, r, accent);
  }
}

void drawSpeakerBars(uint16_t accent) {
  int cx = SCR_W / 2;
  int cy = 78;
  tft.fillRect(cx - 60, 55, 120, 50, tft.color565(22, 26, 42));
  // concentric arcs approximated as circles
  for (int i = 0; i < 3; i++) {
    int r = 12 + i * 10 + ((animFrame + i * 2) % 6);
    tft.drawCircle(cx - 20, cy, r, accent);
  }
  tft.fillCircle(cx - 20, cy, 6, accent);
  // right bars
  for (int i = 0; i < 4; i++) {
    int h = 8 + ((animFrame * 2 + i * 4) % 22);
    tft.fillRoundRect(cx + 20 + i * 12, cy - h / 2, 8, h, 2, accent);
  }
}

void animateUI() {
  uint16_t accent = accentFor(curState);
  switch (curState) {
    case S_IDLE: {
      // soft orb pulse on idle card (keep title)
      tft.fillRoundRect(16, 46, SCR_W - 32, 100, 10, tft.color565(22, 26, 42));
      tft.drawRoundRect(16, 46, SCR_W - 32, 100, 10, accent);
      drawIdleOrb();
      tft.setTextDatum(MC_DATUM);
      tft.setTextColor(TFT_WHITE, tft.color565(22, 26, 42));
      tft.setTextSize(3);
      tft.drawString("hey", SCR_W / 2, 118);
      tft.setTextColor(tft.color565(160, 170, 190), tft.color565(22, 26, 42));
      tft.setTextSize(1);
      tft.drawString("tap to talk", SCR_W / 2, 138);
      break;
    }
    case S_LISTENING:
      drawWaveform(accent);
      tft.setTextDatum(MC_DATUM);
      tft.setTextColor(tft.color565(160, 170, 190), tft.color565(22, 26, 42));
      tft.setTextSize(1);
      tft.drawString("listening", SCR_W / 2, 130);
      break;
    case S_THINKING:
      drawThinkingDots(accent);
      tft.setTextDatum(MC_DATUM);
      tft.setTextColor(tft.color565(160, 170, 190), tft.color565(22, 26, 42));
      tft.setTextSize(1);
      tft.drawString("thinking", SCR_W / 2, 130);
      break;
    case S_SPEAKING:
      drawSpeakerBars(accent);
      tft.setTextDatum(MC_DATUM);
      tft.setTextColor(tft.color565(160, 170, 190), tft.color565(22, 26, 42));
      tft.setTextSize(1);
      tft.drawString("speaking", SCR_W / 2, 130);
      break;
    case S_ON_TASK:
    case S_OFF_TASK:
      // static cards — occasional bottom-dot shimmer only
      break;
  }
  // bottom dots always animate lightly
  for (int i = 0; i < 5; i++) {
    int x = SCR_W / 2 - 40 + i * 20;
    tft.fillCircle(x, SCR_H - 10, 3, (i == (animFrame / 4) % 5) ? accent : tft.color565(40, 45, 60));
  }
}

void showState(BuddyState s) {
  curState = s;
  animFrame = 0;
  uint16_t accent = accentFor(s);
  const char* title = "BUDDY";
  const char* sub = "";
  switch (s) {
    case S_IDLE:
      title = "hey";
      sub = "tap to talk";
      break;
    case S_LISTENING:
      title = "listening";
      sub = "speak — release when done";
      break;
    case S_THINKING:
      title = "thinking";
      sub = "talking to Buddy…";
      break;
    case S_SPEAKING:
      title = "buddy";
      sub = "playing reply";
      break;
    case S_ON_TASK:
      title = "on task";
      sub = "nice — keep going";
      break;
    case S_OFF_TASK:
      title = "off task";
      sub = "nudge incoming";
      break;
  }
  drawChrome(accent, title, sub);
  // first animation paint
  animateUI();
}


// ---------------------------------------------------------------------------
// Download canned WAVs from laptop http.server into FFat (no Arduino uploader)
// From D:\Buddy run:  python -m http.server 8000
// ---------------------------------------------------------------------------
bool downloadToFFat(const char* urlPath, const char* destPath) {
  if (FFat.exists(destPath)) {
    Serial.printf("[fs] already have %s\n", destPath);
    return true;
  }
  HTTPClient http;
  String url = String(SERVER) + urlPath;
  Serial.printf("[fs] GET %s\n", url.c_str());
  http.setTimeout(20000);
  if (!http.begin(url)) {
    Serial.println("[fs] http.begin failed");
    return false;
  }
  int code = http.GET();
  if (code != HTTP_CODE_OK) {
    Serial.printf("[fs] GET failed HTTP %d\n", code);
    http.end();
    return false;
  }
  int len = http.getSize();
  WiFiClient* stream = http.getStreamPtr();
  fs::File f = FFat.open(destPath, FILE_WRITE);
  if (!f) {
    Serial.printf("[fs] open %s for write failed\n", destPath);
    http.end();
    return false;
  }
  uint8_t buf[1024];
  int written = 0;
  while (http.connected() && (len > 0 || len == -1)) {
    size_t avail = stream->available();
    if (!avail) {
      delay(1);
      continue;
    }
    size_t toRead = avail;
    if (toRead > sizeof(buf)) toRead = sizeof(buf);
    int n = stream->readBytes(buf, toRead);
    if (n <= 0) break;
    f.write(buf, n);
    written += n;
    if (len > 0) len -= n;
  }
  f.close();
  http.end();
  Serial.printf("[fs] wrote %s (%d bytes)\n", destPath, written);
  return written > 44;
}

void ensureCannedWavs() {
  bool ok1 = downloadToFFat("/audio/goals_ok.wav", "/goals_ok.wav");
  bool ok2 = downloadToFFat("/audio/off_task.wav", "/off_task.wav");
  bool ok3 = downloadToFFat("/audio/network_issue.wav", "/network_issue.wav");
  Serial.printf("[fs] goals_ok=%d off_task=%d network_issue=%d\n",
                ok1 && FFat.exists("/goals_ok.wav"),
                ok2 && FFat.exists("/off_task.wav"),
                ok3 && FFat.exists("/network_issue.wav"));
}

