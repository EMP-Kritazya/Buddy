/*
  Buddy Watch firmware — LilyGO T-Display-S3 (ESP32-S3)
  I2S0 = mic (RX), I2S1 = amp (TX)
  Button GPIO 16 (pull-up, LOW = pressed), fallback GPIO 14
  Display: TFT_eSPI with LilyGO T-Display-S3 user setup
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <driver/i2s.h>
#include <TFT_eSPI.h>

// ---------------------------------------------------------------------------
// Wi-Fi / server
// ---------------------------------------------------------------------------
const char* WIFI_SSID     = "YOUR_WIFI";
const char* WIFI_PASS     = "YOUR_PASS";
const char* SERVER        = "http://192.168.1.100:8000";   // laptop IP
const char* VOICE_URL     = "/voice";
const char* PENDING_URL   = "/pending-speech";

// ---------------------------------------------------------------------------
// Pin map
// ---------------------------------------------------------------------------
#define PWR_EN      15   // must be HIGH at boot
#define BTN_PIN     16   // push-to-talk
#define BTN_FALLBK  14   // onboard button 2

// I2S0 mic
#define MIC_SCK     1
#define MIC_WS      2
#define MIC_SD      3

// I2S1 amp
#define AMP_BCLK    10
#define AMP_LRCK    11
#define AMP_DIN     12
#define AMP_SD      13   // HIGH = amp enabled

// ---------------------------------------------------------------------------
// Audio config
// ---------------------------------------------------------------------------
#define SAMPLE_RATE   16000
#define BIT_DEPTH     16
#define MAX_REC_S     8
#define MAX_REC_BYTES (SAMPLE_RATE * (BIT_DEPTH/8) * MAX_REC_S)

// ---------------------------------------------------------------------------
// Globals
// ---------------------------------------------------------------------------
TFT_eSPI tft = TFT_eSPI();

uint8_t* recBuf    = nullptr;
size_t   recBytes  = 0;

unsigned long lastPollMs = 0;
const unsigned long POLL_INTERVAL = 2000;

// Display state enum
enum BuddyState { S_IDLE, S_LISTENING, S_THINKING, S_SPEAKING, S_ON_TASK, S_OFF_TASK };
BuddyState curState = S_IDLE;

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

  // Button
  pinMode(BTN_PIN,    INPUT_PULLUP);
  pinMode(BTN_FALLBK, INPUT_PULLUP);

  // Display
  tft.init();
  tft.setRotation(1);
  showState(S_IDLE);

  // Allocate PSRAM record buffer
  recBuf = (uint8_t*)ps_malloc(MAX_REC_BYTES);
  if (!recBuf) {
    tft.println("PSRAM alloc fail");
    while (true) delay(1000);
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
    Serial.print("IP: "); Serial.println(WiFi.localIP());
  } else {
    Serial.println("Wi-Fi failed — offline mode");
  }

  showState(S_IDLE);
}

// ---------------------------------------------------------------------------
// Loop
// ---------------------------------------------------------------------------
void loop() {
  bool btnPressed = (digitalRead(BTN_PIN) == LOW) || (digitalRead(BTN_FALLBK) == LOW);

  if (btnPressed) {
    recordAndSend();
  }

  // Poll for proactive coaching
  if (millis() - lastPollMs > POLL_INTERVAL) {
    lastPollMs = millis();
    pollPendingSpeech();
  }
}

// ---------------------------------------------------------------------------
// Record while button held, then POST to /voice
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

  if (recBytes < 3200) {   // < 0.1 s — ignore
    showState(S_IDLE);
    return;
  }

  showState(S_THINKING);

  // Build WAV in-place (prepend 44-byte header by shifting buffer is expensive;
  // instead send PCM with Content-Type audio/l16 and let the server wrap it)
  if (WiFi.status() != WL_CONNECTED) {
    playFile("/audio/goals_ok.wav");
    showState(S_IDLE);
    return;
  }

  HTTPClient http;
  String url = String(SERVER) + VOICE_URL;
  http.begin(url);
  http.addHeader("Content-Type", "audio/l16; rate=16000; channels=1");
  int code = http.POST(recBuf, recBytes);

  if (code == 200) {
    showState(S_SPEAKING);
    int len = http.getSize();
    uint8_t* resp = (uint8_t*)malloc(len);
    if (resp) {
      http.getStream().readBytes(resp, len);
      playPCM(resp, len);
      free(resp);
    }
  } else {
    Serial.printf("POST /voice failed: %d\n", code);
    playFile("/audio/goals_ok.wav");
  }
  http.end();
  showState(S_IDLE);
}

// ---------------------------------------------------------------------------
// Poll /pending-speech
// ---------------------------------------------------------------------------
void pollPendingSpeech() {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  http.begin(String(SERVER) + PENDING_URL);
  int code = http.GET();

  if (code == 200) {
    int len = http.getSize();
    uint8_t* buf = (uint8_t*)malloc(len);
    if (buf) {
      showState(S_SPEAKING);
      http.getStream().readBytes(buf, len);
      playPCM(buf, len);
      free(buf);
      showState(S_IDLE);
    }
  }
  http.end();
}

// ---------------------------------------------------------------------------
// Play raw PCM (16-bit, 16 kHz mono) — skips WAV header if present
// ---------------------------------------------------------------------------
void playPCM(const uint8_t* data, size_t len) {
  // Skip 44-byte WAV header if present
  size_t offset = 0;
  if (len > 44 && data[0] == 'R' && data[1] == 'I' && data[2] == 'F' && data[3] == 'F') {
    offset = 44;
  }

  size_t written = 0;
  size_t remaining = len - offset;
  const uint8_t* ptr = data + offset;

  while (remaining > 0) {
    size_t chunk = min(remaining, (size_t)2048);
    i2s_write(I2S_NUM_1, ptr, chunk, &written, portMAX_DELAY);
    ptr       += written;
    remaining -= written;
  }
}

// ---------------------------------------------------------------------------
// Play a canned file from SPIFFS (not implemented in base build)
// ---------------------------------------------------------------------------
void playFile(const char* /*path*/) {
  // Canned WAVs are served from the laptop in this build.
  // Extend with SPIFFS if the laptop is unreachable.
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
