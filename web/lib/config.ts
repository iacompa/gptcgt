/**
 * Centralized configuration for the web app.
 * All environment variables should be accessed through this module
 * to avoid inconsistent fallback logic across files.
 */

/** Backend API URL — used in server-side API route handlers. */
export const API_URL =
    process.env.API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://127.0.0.1:8000";

/** Public API URL — safe to expose to the browser. */
export const PUBLIC_API_URL =
    process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

/** Base URL of this web app. */
export const BASE_URL =
    process.env.NEXT_PUBLIC_BASE_URL || "https://gptcgt.ai";

/** Whether we are running in production. */
export const IS_PRODUCTION = process.env.NODE_ENV === "production";
