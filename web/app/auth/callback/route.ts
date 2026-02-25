import { handleAuth } from "@workos-inc/authkit-nextjs";

// This automatically handles the OAuth callback from WorkOS and manages the session cookie
export const GET = handleAuth();
