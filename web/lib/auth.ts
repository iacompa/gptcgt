import { withAuth } from "@workos-inc/authkit-nextjs";

export interface Session {
    user: {
        id: string;
        email: string;
        name?: string;
    };
    accessToken: string;
}

import * as jwt from "jsonwebtoken";

export async function getSession(): Promise<Session | null> {
    // Use AuthKit logic to authenticate calls. Note: WorkOS doesn't inherently give an `accessToken` equivalent 
    // for FastAPI integration out of the box unless we perform OIDC, but for the sake of the exercise
    // we use a signed JWT with the HS256 algorithm matching the backend API requirement.

    const { user, sessionId } = await withAuth();

    if (!user) {
        if (process.env.NODE_ENV === "development" && process.env.ENABLE_MOCK_AUTH === "1") {
            return {
                user: {
                    id: "dev_user_123",
                    email: "dev@example.com",
                    name: "Dev User"
                },
                accessToken: "dev_mock_access_token"
            };
        }
        return null;
    }

    const secret = process.env.JWT_SECRET;
    if (!secret) {
        throw new Error("JWT_SECRET environment variable is missing.");
    }

    return {
        user: {
            id: user.id,
            email: user.email,
            name: `${user.firstName || ''} ${user.lastName || ''}`.trim() || user.email.split("@")[0]
        },
        accessToken: jwt.sign(
            { sub: user.id, email: user.email },
            secret,
            { expiresIn: "1h", algorithm: "HS256" }
        )
    };
}
