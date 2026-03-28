import { expect, test } from "@playwright/test";

import {
    expectGithubConnected,
    installStagingSession,
} from "./helpers/live";

test("live staging redirects unauthenticated dashboard access to auth", async ({ page }) => {
    await page.goto("/dashboard/chat");

    await expect(page).toHaveURL(/\/auth/);
    await expect(page.getByRole("heading", { name: /Sign in to your account/i })).toBeVisible();
});

test("live staging chat loads the authenticated workspace surface", async ({ page, baseURL }) => {
    test.skip(!baseURL, "STAGING_WEB_BASE_URL is required");

    await installStagingSession(page.context(), baseURL!);
    await page.goto("/dashboard/chat");

    await expect(page.getByRole("heading", { name: /Fast model routing, without leaving the workspace/i })).toBeVisible();
    await expect(page.getByTestId("chat-model-select")).toBeVisible();
    await expect(page.getByTestId("chat-message-list")).toBeVisible();
    await expect(page.getByTestId("chat-composer")).toHaveAttribute(
        "placeholder",
        /architecture feedback, a migration plan, or a model recommendation/i
    );
    await page.reload();
    await expect(page.getByTestId("chat-model-select")).toBeVisible();
});

test("live staging hub reflects the real GitHub connection state", async ({ page, baseURL }) => {
    test.skip(!baseURL, "STAGING_WEB_BASE_URL is required");

    await installStagingSession(page.context(), baseURL!);
    await page.goto("/dashboard/hub");

    if (expectGithubConnected()) {
        await expect(page.getByRole("heading", { name: /Repo browsing, task setup, and live run logs/i })).toBeVisible();
        await expect(page.getByTestId("hub-repo-search")).toBeVisible();
        await expect(page.getByTestId("hub-disconnect")).toBeVisible();
        return;
    }

    await expect(page.getByRole("heading", { name: /Connect GitHub to unlock repo-aware runs/i })).toBeVisible();
    await expect(page.getByTestId("hub-connect")).toBeVisible();
});
