/**
 * Centralized configuration for the web app.
 * All environment variables should be accessed through this module
 * to avoid inconsistent fallback logic across files.
 */
/* eslint-disable @typescript-eslint/no-var-requires */

const endpoints = require("./endpoints.config.js");

const backendApiUrl = endpoints.resolveBackendApiUrl(process.env);
const publicApiUrl = endpoints.resolvePublicApiUrl(process.env);
const proxyApiUrl = endpoints.resolveProxyApiUrl(process.env);
const chatCompletionsUrl = endpoints.resolveChatCompletionUrl(process.env);
const baseUrl = endpoints.resolveBaseUrl(process.env);
const authCallbackOrigin = endpoints.resolveAuthCallbackOrigin(process.env);

/** Backend API URL — used in server-side API route handlers. */
export const API_URL = backendApiUrl;

/** Public API URL — safe to expose to the browser. */
export const PUBLIC_API_URL = publicApiUrl;

/** Proxy API URL — used by Next.js API routes forwarding to managed mode. */
export const CHAT_PROXY_URL = proxyApiUrl;

/** Chat completion endpoint with proxy path applied. */
export const CHAT_COMPLETIONS_URL = chatCompletionsUrl;

/** Base URL of this web app. */
export const BASE_URL = baseUrl;

/** Production web origin used for environment checks. */
export const DEFAULT_WEB_ORIGIN = endpoints.DEFAULT_WEB_ORIGIN || BASE_URL;

/** Origin used for auth callback redirects (defaults to BASE_URL). */
export const AUTH_CALLBACK_ORIGIN = authCallbackOrigin || BASE_URL;

/** Whether we are running in production. */
export const IS_PRODUCTION = process.env.NODE_ENV === "production";
