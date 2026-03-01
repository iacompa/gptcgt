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

const JWT_SECRET = process.env.JWT_SECRET || "dev-secret-change-in-production";

export async function getSession(): Promise<Session | null> {
    try {
        const cookieStore = await cookies();
        const token = cookieStore.get("gptcgt_session")?.value;

        if (!token) return null;

        const payload = jwt.verify(token, JWT_SECRET) as any;

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

export function createSessionToken(email: string, name?: string): string {
    return jwt.sign(
        {
            sub: email,
            email,
            name: name || email.split("@")[0],
        },
        JWT_SECRET,
        { expiresIn: "7d", algorithm: "HS256" }
    );
}
