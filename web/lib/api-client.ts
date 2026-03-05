import createClient from "openapi-fetch";
import type { paths } from "./api-schema";
import { PUBLIC_API_URL } from "./config";

export const apiClient = createClient<paths>({
    baseUrl: PUBLIC_API_URL,
});

// Add our httpOnly credentials middleware interceptor
apiClient.use({
    onRequest({ request }) {
        return new Request(request, {
            credentials: "include"
        });
    }
});
