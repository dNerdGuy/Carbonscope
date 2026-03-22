/**
 * Client-side environment variables.
 *
 * In Vite, client-side vars must be prefixed with VITE_ and are accessed
 * via import.meta.env. Hardcoded fallbacks ensure the app works in
 * development without a .env.local file.
 */

/** Validated client-side environment variables. */
export const env = {
  BACKEND_URL: import.meta.env.VITE_BACKEND_URL || "http://localhost:8000",
  NODE_ENV: import.meta.env.MODE || "development",
  SITE_URL: import.meta.env.VITE_SITE_URL || "https://carbonscope.io",
  GOOGLE_CLIENT_ID:
    import.meta.env.VITE_GOOGLE_CLIENT_ID ||
    "323040716512-7maggb3e8djdg1bfhonnr8jol42lk04e.apps.googleusercontent.com",
} as const;

/** No-op in SPA/CSR mode — kept for backward compatibility. */
export function validateEnv(): void {}
