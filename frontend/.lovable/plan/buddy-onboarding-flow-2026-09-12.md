# Buddy onboarding flow

## Build
- Replace the onboarding placeholder with a six-step conversational flow on the existing cream canvas.
- Add underline-only text inputs, compact single-select choices, multi-select rows, goal textarea, progress line, step navigation, and personalized summary.
- Validate each step before advancing, with coral guidance and a subtle shake on incomplete answers.
- Add the `/download` destination referenced by the final action as a minimal placeholder using existing Buddy styling.

## Verify
- Check all six steps, back/continue behavior, selected states, character limit, personalized summary, and final navigation.
- Check desktop, tablet, and 390px mobile layouts for wrapping, spacing, and overflow.
- Confirm page transitions, validation animation, route metadata, and build health.

## Technical details
- Keep all answers in local React state, ready for the documented Phase 2 API handoff.
- Use semantic HTML, accessible labels and controls, existing design tokens, and the existing shared Button component.
- Add only local CSS keyframes needed for the requested step entrance and invalid-field shake, including reduced-motion handling.
