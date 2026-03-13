import createClient from "openapi-fetch";
import type { paths } from "./api-schema";

export const apiClient = createClient<paths>({
    baseUrl: "/api/backend",
    // Force browser cookies onto every same-origin dashboard request.
    // The backend proxy relies on the httpOnly session cookie for auth.
    fetch: (input: Request) =>
        fetch(
            new Request(input, {
                credentials: "include",
            })
        ),
});
