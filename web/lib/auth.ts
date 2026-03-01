import { withAuth } from "@workos-inc/authkit-nextjs";
import * as jwt from "jsonwebtoken";

export interface Session {
    user: {
        id: string;
        email: string;
        name?: string;
    };
    accessToken: string;
}

export async function getSession(): Promise<Session | null> {
    try {
        const { user } = await withAuth();

        if (!user) {
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
    } catch (e) {
        // If WorkOS is not configured or session is invalid, return null
        console.error("Auth session error:", e);
        return null;
    }
}
