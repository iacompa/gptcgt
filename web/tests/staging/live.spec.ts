import { expect, test } from "@playwright/test";

import {
    expectGithubConnected,
    installStagingSession,
    stagingApiURL,
    stagingAuthToken,
} from "./helpers/live";

interface ConversationResponse {
    id: string;
    summary: string;
}

async function createSmokeConversation(summary: string): Promise<ConversationResponse> {
    const apiURL = stagingApiURL();
    const authToken = stagingAuthToken();
    if (!apiURL || !authToken) {
        throw new Error("Missing STAGING_SMOKE_API_URL or STAGING_SMOKE_AUTH_TOKEN for staging conversation setup.");
    }

    const response = await fetch(`${apiURL.replace(/\/$/, "")}/conversations`, {
        method: "POST",
        headers: {
            Authorization: `Bearer ${authToken}`,
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            summary,
            messages: [
                {
                    role: "user",
                    content: `${summary} seeded by staging browser smoke.`,
                },
                {
                    role: "assistant",
                    content: "Browser smoke continuity seed ready.",
                },
            ],
        }),
    });

    if (!response.ok) {
        throw new Error(`Failed to seed staging conversation: ${response.status} ${await response.text()}`);
    }

    return (await response.json()) as ConversationResponse;
}

async function deleteSmokeConversation(conversationId: string): Promise<void> {
    const apiURL = stagingApiURL();
    const authToken = stagingAuthToken();
    if (!apiURL || !authToken) {
        return;
    }

    await fetch(`${apiURL.replace(/\/$/, "")}/conversations/${conversationId}`, {
        method: "DELETE",
        headers: {
            Authorization: `Bearer ${authToken}`,
        },
    });
}

test("live staging redirects unauthenticated dashboard access to auth", async ({ page }) => {
    await page.goto("/dashboard/chat");

    await expect(page).toHaveURL(/\/auth/);
    await expect(page.getByRole("heading", { name: /Sign in to your account/i })).toBeVisible();
});

test("live staging chat resumes server-backed continuity", async ({ page, baseURL }) => {
    test.skip(!baseURL, "STAGING_WEB_BASE_URL is required");

    const marker = `staging-browser-smoke-${Date.now()}`;
    const seeded = await createSmokeConversation(marker);

    try {
        await installStagingSession(page.context(), baseURL!);
        await page.goto("/dashboard/chat");

        await expect(page.getByRole("heading", { name: /Resume browser conversations/i })).toBeVisible();
        await expect(page.getByText("Cloud sync live")).toBeVisible();
        await expect(page.getByTestId("chat-thread-list")).toContainText(marker);

        await page.getByTestId(`chat-thread-${seeded.id}`).click();
        await expect(page.getByTestId("chat-message-list")).toContainText("Browser smoke continuity seed ready.");

        await page.reload();
        await expect(page.getByText("Cloud sync live")).toBeVisible();
        await expect(page.getByTestId("chat-thread-list")).toContainText(marker);
    } finally {
        await deleteSmokeConversation(seeded.id);
    }
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
