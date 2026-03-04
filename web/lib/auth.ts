import { cookies } from "next/headers";
import * as jwt from "jsonwebtoken";

export interface Session {
    user: {
        id: string;
        email: string;
        name?: string;
    };
    accessToken: string;
}

// SECURITY: No fallback secret. JWT_SECRET MUST be set in environment.
function getJwtSecret(): string {
    const secret = process.env.JWT_SECRET;
    if (!secret) {
        throw new Error(
            "FATAL: JWT_SECRET environment variable is not set. " +
            "Generate one with: openssl rand -base64 48"
        );
    }
    if (secret.length < 32) {
        throw new Error(
            "FATAL: JWT_SECRET must be at least 32 characters. " +
            "Generate one with: openssl rand -base64 48"
        );
    }
    return secret;
}

export async function getSession(): Promise<Session | null> {
    try {
        const cookieStore = await cookies();
        const token = cookieStore.get("gptcgt_session")?.value;

        if (!token) return null;

        const secret = getJwtSecret();
        const payload = jwt.verify(token, secret, {
            algorithms: ["HS256"],
        }) as any;

        if (!payload.sub || !payload.email) {
            return null;
        }

        return {
            user: {
                id: payload.sub || payload.email,
                email: payload.email,
                name: payload.name || payload.email.split("@")[0],
            },
            accessToken: token,
        };
    } catch (e) {
        return null;
    }
}

export function createSessionToken(subject: string, email: string, name?: string): string {
    const secret = getJwtSecret();
    return jwt.sign(
        {
            sub: subject,
            email,
            name: name || email.split("@")[0],
            iss: "gptcgt",
            aud: "gptcgt-api",
        },
        secret,
        { expiresIn: "7d", algorithm: "HS256" }
    );
}
