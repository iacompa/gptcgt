const defaults = require("../../config/endpoints.defaults.json");

function normalize(value) {
    if (typeof value !== "string") {
        return "";
    }
    return value.trim().replace(/\/+$/, "");
}

const DEFAULT_BACKEND_URL = normalize(defaults.DEFAULT_BACKEND_API_URL) || "https://gptcgt-api.fly.dev";
const DEFAULT_API_URL = normalize(defaults.DEFAULT_API_URL) || "http://127.0.0.1:8000";
const DEFAULT_SANDBOX_API_URL = normalize(defaults.DEFAULT_SANDBOX_API_URL) || "https://gptcgt.ai/api";
const DEFAULT_BASE_URL = normalize(defaults.DEFAULT_BASE_URL) || "https://gptcgt.ai";
const DEFAULT_WEB_ORIGIN = normalize(defaults.DEFAULT_WEB_ORIGIN) || DEFAULT_BASE_URL;
const DEFAULT_PROXY_PATH = normalize(defaults.DEFAULT_PROXY_PATH || "proxy/v1").replace(/^\/+/, "");

function resolveBackendApiUrl(env = process.env) {
    return (
        normalize(env.GPTCGT_API_BASE_URL) ||
        normalize(env.API_URL) ||
        normalize(env.GPTCGT_BACKEND_API_URL) ||
        normalize(env.BACKEND_API_URL) ||
        normalize(env.NEXT_PUBLIC_API_URL) ||
        normalize(env.PUBLIC_API_URL) ||
        normalize(env.API_BASE_URL) ||
        DEFAULT_BACKEND_URL
    );
}

function resolvePublicApiUrl(env = process.env) {
    return (
        normalize(env.NEXT_PUBLIC_API_URL) ||
        normalize(env.GPTCGT_API_BASE_URL) ||
        normalize(env.API_URL) ||
        normalize(env.PUBLIC_API_URL) ||
        normalize(env.API_BASE_URL) ||
        resolveBackendApiUrl(env)
    );
}

function resolveBaseUrl(env = process.env) {
    return (
        normalize(env.NEXT_PUBLIC_BASE_URL) ||
        normalize(env.PUBLIC_BASE_URL) ||
        normalize(env.GPTCGT_BASE_URL) ||
        normalize(env.BASE_URL) ||
        DEFAULT_BASE_URL
    );
}

function resolveAuthCallbackOrigin(env = process.env) {
    return (
        normalize(env.AUTH_CALLBACK_ORIGIN) ||
        resolveBaseUrl(env) ||
        DEFAULT_BASE_URL
    );
}

function resolveProxyPath(env = process.env) {
    const value = normalize(env.PROXY_PATH) || normalize(env.GPTCGT_PROXY_PATH) || DEFAULT_PROXY_PATH;
    return value.startsWith("/") ? value : `/${value}`;
}

function resolveProxyApiUrl(env = process.env) {
    return `${resolveBackendApiUrl(env)}${resolveProxyPath(env)}`;
}

function resolveChatCompletionUrl(env = process.env) {
    return `${resolveProxyApiUrl(env)}/chat/completions`;
}

module.exports = {
    DEFAULT_BACKEND_URL,
    DEFAULT_API_URL,
    DEFAULT_SANDBOX_API_URL,
    DEFAULT_BASE_URL,
    DEFAULT_WEB_ORIGIN,
    resolveBackendApiUrl,
    resolvePublicApiUrl,
    resolveProxyApiUrl,
    resolveProxyPath,
    resolveChatCompletionUrl,
    resolveBaseUrl,
    resolveAuthCallbackOrigin,
};
