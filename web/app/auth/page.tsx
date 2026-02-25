"use client";

export default function AuthPage() {
    return (
        <div className="flex min-h-full flex-1 flex-col justify-center px-6 py-12 lg:px-8">
            <div className="sm:mx-auto sm:w-full sm:max-w-sm">
                <h2 className="mt-10 text-center text-2xl font-bold leading-9 tracking-tight text-white">
                    Sign in to your account
                </h2>
            </div>

            <div className="mt-10 sm:mx-auto sm:w-full sm:max-w-sm">
                {/* WorkOS SSO: GET redirect triggers PKCE flow via WorkOS AuthKit.
                    No email/password fields - credentials never touch this server.
                    Session cookie is set by WorkOS in /auth/callback/route.ts via handleAuth(). */}
                <a
                    href="/api/auth/signin"
                    className="flex w-full justify-center rounded-md bg-white px-3 py-1.5 text-sm font-semibold leading-6 text-gray-900 shadow-sm hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                >
                    Continue with WorkOS SSO
                </a>

                <p className="mt-10 text-center text-sm text-gray-400">
                    Not a member?{" "}
                    <a href="/pricing" className="font-semibold leading-6 text-indigo-400 hover:text-indigo-300">
                        View plans and pricing
                    </a>
                </p>
            </div>
        </div>
    );
}
