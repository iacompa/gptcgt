const {
    resolveBackendApiUrl,
    resolveProxyApiUrl,
} = require("./lib/endpoints.config.js");

const backendApiUrl = resolveBackendApiUrl(process.env);
const publicApiUrl = backendApiUrl;
const proxyApiUrl = resolveProxyApiUrl(process.env);

const addDistinct = (...values) => [...new Set(values.filter(Boolean))].join(" ");

/** @type {import('next').NextConfig} */
const nextConfig = {
    reactStrictMode: true,
    eslint: {
        // F14: Do NOT ignore lint during builds — catch issues at build time
        ignoreDuringBuilds: false,
    },
    typescript: {
        // F14: Do NOT ignore TS errors during builds
        ignoreBuildErrors: false,
        tsconfigPath: "./tsconfig.next.json",
    },
    async headers() {
        return [
            {
                source: "/(.*)",
                headers: [
                    {
                        key: "Content-Security-Policy",
                        value: [
                            "default-src 'self'",
                            "script-src 'self' 'unsafe-inline'",
                            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
                            "font-src 'self' https://fonts.gstatic.com",
                            "img-src 'self' data: blob: https:",
                            `connect-src 'self' ${addDistinct(publicApiUrl, backendApiUrl, proxyApiUrl)} https://*.workos.com https://*.stripe.com`,
                            "frame-ancestors 'none'",
                            "base-uri 'self'",
                            "form-action 'self'",
                        ].join("; "),
                    },
                    {
                        key: "X-Content-Type-Options",
                        value: "nosniff",
                    },
                    {
                        key: "X-Frame-Options",
                        value: "DENY",
                    },
                    {
                        key: "Referrer-Policy",
                        value: "strict-origin-when-cross-origin",
                    },
                    {
                        key: "Permissions-Policy",
                        value: "camera=(), microphone=(), geolocation=()",
                    },
                    {
                        key: "X-DNS-Prefetch-Control",
                        value: "on",
                    },
                    {
                        key: "Strict-Transport-Security",
                        value: "max-age=63072000; includeSubDomains; preload",
                    },
                ],
            },
        ];
    },
}

module.exports = nextConfig
