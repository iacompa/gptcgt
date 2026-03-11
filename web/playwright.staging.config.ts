import { defineConfig } from "@playwright/test";

const baseURL = process.env.STAGING_WEB_BASE_URL || process.env.NEXT_PUBLIC_BASE_URL || "https://example.invalid";

export default defineConfig({
    testDir: "./tests/staging",
    fullyParallel: false,
    retries: process.env.CI ? 1 : 0,
    workers: 1,
    timeout: 45_000,
    expect: {
        timeout: 15_000,
    },
    reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
    use: {
        baseURL,
        trace: "retain-on-failure",
        screenshot: "only-on-failure",
        video: "retain-on-failure",
        viewport: { width: 1440, height: 980 },
    },
});
