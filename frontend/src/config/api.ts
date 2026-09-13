export const API_BASE = import.meta.env['VITE_API_URL'] || "http://localhost:8000";

// Phase 1: false (use preview data)
// Phase 2: true (use real API)
export const USE_REAL_API = import.meta.env['VITE_USE_REAL_API'] === "true";
