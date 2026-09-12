/*
  Buddy Watch firmware — LilyGO T-Display-S3 (ESP32-S3)
  I2S0 = mic (RX), I2S1 = amp (TX)
  Button GPIO 16 (pull-up, LOW = pressed), fallback GPIO 14
  Display: TFT_eSPI with LilyGO T-Display-S3 user setup

  Canned WAVs stored in LittleFS under /goals_ok.wav and /off_task.wav.
  Upload them once with the Arduino LittleFS upload tool or PlatformIO
  after running: python voice/eleven.py  (generates audio/*.wav).
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <driver/i2s.h>
#include "TFT_eSPI.h"
#include <FS.h>
#include <LittleFS.h>

// ---------------------------------------------------------------------------
// Wi-Fi / server  — edit before flashing
// ---------------------------------------------------------------------------
const char* WIFI_SSID   = "Rice Visitor";
const char* WIFI_PASS   = "";
const char* SERVER      = "http://192.168.1.100:8000";  // laptop LAN IP
const char* VOICE_URL   = "/voice";
const char* PENDING_URL = "/pending-speech";

// ---------------------------------------------------------------------------
// Pin map
// ---------------------------------------------------------------------------
#define PWR_EN      15   // must be HIGH at boot — powers LCD + header rails
#define BTN_PIN     16   // push-to-talk (external)
#define BTN_FALLBK  14   // onboard button 2

// I2S0 — mic (RX)
#define MIC_SCK   1
#define MIC_WS    2
#define MIC_SD    3

// I2S1 — amp (TX)
#define AMP_BCLK  10
#define AMP_LRCK  11
#define AMP_DIN   12
#define AMP_SD    13   // HIGH = amp enabled

// ---------------------------------------------------------------------------
// Audio config
// ---------------------------------------------------------------------------
#define SAMPLE_RATE     16000
#define BIT_DEPTH       16
#define MAX_REC_S       8
#define MAX_REC_BYTES   (SAMPLE_RATE * (BIT_DEPTH / 8) * MAX_REC_S)  // 256 kB
#define PLAY_CHUNK      2048   // I2S write chunk for streaming playback

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

// ---------------------------------------------------------------------------
// Forward declarations
// ---------------------------------------------------------------------------
void showState(BuddyState s);
void recordAndSend();
void pollPendingSpeech();
void streamAndPlay(WiFiClient& stream, int contentLen);
void playPCM(const uint8_t* data, size_t len);
void playFile(const char* path);

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);

  // Power rail — must be first
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

  // LittleFS — canned WAV fallbacks
  if (!LittleFS.begin(false)) {
    Serial.println("[warn] LittleFS mount failed — offline canned WAVs unavailable");
  } else {
    Serial.println("[ok] LittleFS mounted");
  }

  // I2S0 — mic
  i2s_config_t mic_cfg = {
    .mode                 = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate          = SAMPLE_RATE,
    .bits_per_sample      = I2S_BITS_PER_SAMPLE_16BIT,
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

  // I2S1 — amp
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
    showState(S_IDLE);
  } else {
    Serial.println("[warn] Wi-Fi failed — offline mode");
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
  bool btnPressed = (digitalRead(BTN_PIN) == LOW) || (digitalRead(BTN_FALLBK) == LOW);

  if (btnPressed) {
    recordAndSend();
  }

  if (millis() - lastPollMs > POLL_INTERVAL) {
    lastPollMs = millis();
    pollPendingSpeech();
  }
}

// ---------------------------------------------------------------------------
// Record while button held → POST raw PCM to /voice → stream reply to speaker
// ---------------------------------------------------------------------------
void recordAndSend() {
  showState(S_LISTENING);
  i2s_zero_dma_buffer(I2S_NUM_0);
  recBytes = 0;

  size_t bytesRead = 0;
  while ((digitalRead(BTN_PIN) == LOW || digitalRead(BTN_FALLBK) == LOW)
         && recBytes < MAX_REC_BYTES) {
    i2s_read(I2S_NUM_0, recBuf + recBytes,
             min((size_t)512, MAX_REC_BYTES - recBytes),
             &bytesRead, portMAX_DELAY);
    recBytes += bytesRead;
  }

  if (recBytes < 3200) {   // < 0.1 s — ignore tap
    showState(S_IDLE);
    return;
  }

  showState(S_THINKING);

  if (WiFi.status() != WL_CONNECTED) {
    playFile("/goals_ok.wav");
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
    Serial.printf("[warn] POST /voice → HTTP %d\n", code);
    playFile("/goals_ok.wav");
  }

  http.end();
  showState(S_IDLE);
}

// ---------------------------------------------------------------------------
// Poll /pending-speech every 2 s — plays proactive coaching with no button press
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
// Stream HTTP body directly to I2S — no heap alloc, handles chunked transfer
// ---------------------------------------------------------------------------
void streamAndPlay(WiFiClient& stream, int contentLen) {
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

    size_t written = 0;
    i2s_write(I2S_NUM_1, ptr, len, &written, portMAX_DELAY);

    if (remaining > 0) {
      remaining -= got;
      if (remaining <= 0) break;
    }
  }
}

// ---------------------------------------------------------------------------
// Play raw PCM or WAV already in RAM
// ---------------------------------------------------------------------------
void playPCM(const uint8_t* data, size_t len) {
  size_t offset = 0;
  if (len > 44 && data[0] == 'R' && data[1] == 'I' && data[2] == 'F' && data[3] == 'F') {
    offset = 44;
  }

  size_t written  = 0;
  size_t remaining = len - offset;
  const uint8_t* ptr = data + offset;

  while (remaining > 0) {
    size_t n = min(remaining, (size_t)PLAY_CHUNK);
    i2s_write(I2S_NUM_1, ptr, n, &written, portMAX_DELAY);
    ptr       += written;
    remaining -= written;
  }
}

// ---------------------------------------------------------------------------
// Play a canned WAV from LittleFS (offline fallback)
// Upload audio/goals_ok.wav and audio/off_task.wav to LittleFS as
// /goals_ok.wav and /off_task.wav using the Arduino LittleFS upload tool.
// ---------------------------------------------------------------------------
void playFile(const char* path) {
  if (!LittleFS.exists(path)) {
    Serial.printf("[warn] canned file missing: %s\n", path);
    return;
  }

  fs::File f = LittleFS.open(path, "r");
  if (!f) return;

  showState(S_SPEAKING);

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

    size_t written = 0;
    i2s_write(I2S_NUM_1, ptr, len, &written, portMAX_DELAY);
  }

  f.close();
}

// ---------------------------------------------------------------------------
// Display
// ---------------------------------------------------------------------------
void showState(BuddyState s) {
  curState = s;
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.setTextSize(3);
  tft.setCursor(20, 80);

  switch (s) {
    case S_IDLE:      tft.println("BUDDY");     break;
    case S_LISTENING: tft.println("LISTENING"); break;
    case S_THINKING:  tft.println("THINKING");  break;
    case S_SPEAKING:  tft.println("SPEAKING");  break;
    case S_ON_TASK:   tft.println("ON TASK");   break;
    case S_OFF_TASK:  tft.println("OFF TASK");  break;
  }
}
