# Download and wearable connection flow

## Build
- Replace the download placeholder with the specified step-two install experience, simulated download confirmation, agent details, and navigation.
- Add the `/connect` step-three page with timed searching, elapsed scan status, animated indicators, connected device details, and dashboard navigation.
- Keep both pages on the existing Buddy canvas, typography, tokens, and compact line-based layout.

## Verify
- Check download confirmation and all back/continue links.
- Check searching starts immediately, elapsed time updates, automatic connection completes, and the dashboard action changes state.
- Check desktop and 390px mobile layouts, route metadata, animations, and build health.

## Technical details
- Use local React state and timers only; no real download or Bluetooth integration is added in this phase.
- Add only scoped animation utilities with reduced-motion behavior.
