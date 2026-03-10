"use client";

import { useState } from "react";
import { ArrowRight, LockKeyhole, ShieldCheck, Wallet } from "lucide-react";
import { useToast } from "@/components/toaster";

export default function AuthPage() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);
    const { pushToast } = useToast();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");
        setLoading(true);

        try {
            const res = await fetch("/api/auth/signin", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email, password }),
            });

            const data = await res.json();

            if (!res.ok) {
                setError(data.error || "Sign in failed");
                return;
            }

            // SECURITY: Token is set as httpOnly cookie by the server.
            // No localStorage storage — prevents XSS token theft.

            // Force a hard redirect so the browser sends the new cookie
            window.location.href = "/dashboard";
        } catch (err) {
            setError("Network error. Please try again.");
            pushToast({
                tone: "error",
                title: "Sign-in request failed",
                description: "The browser could not reach the authentication endpoint.",
            });
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="page-shell">
            <div className="grid gap-8 lg:grid-cols-[0.9fr_0.7fr] lg:items-start">
                <div className="hero-panel p-8 sm:p-10">
                    <p className="eyebrow">Welcome back</p>
                    <h1 className="mt-4 text-4xl font-semibold tracking-[-0.04em] text-slate-950 sm:text-5xl">
                        Sign in to open your routing workspace.
                    </h1>
                    <p className="mt-4 max-w-xl copy-lg">
                        Keep GitHub, spend controls, team policy, and model access in one place instead of juggling local scripts and provider dashboards.
                    </p>
                    <div className="mt-8 grid gap-4 sm:grid-cols-3">
                        <div className="panel-muted p-4">
                            <LockKeyhole className="h-5 w-5 text-[var(--accent)]" />
                            <p className="mt-3 text-sm font-medium text-slate-950">Session cookies only</p>
                            <p className="mt-1 text-sm text-[var(--text-muted)]">No browser localStorage token handling.</p>
                        </div>
                        <div className="panel-muted p-4">
                            <Wallet className="h-5 w-5 text-[var(--amber)]" />
                            <p className="mt-3 text-sm font-medium text-slate-950">Spend-aware UX</p>
                            <p className="mt-1 text-sm text-[var(--text-muted)]">Caps, wallet state, and usage stay visible.</p>
                        </div>
                        <div className="panel-muted p-4">
                            <ShieldCheck className="h-5 w-5 text-slate-900" />
                            <p className="mt-3 text-sm font-medium text-slate-950">Proof-ready</p>
                            <p className="mt-1 text-sm text-[var(--text-muted)]">Verification and repo flows stay attached.</p>
                        </div>
                    </div>
                </div>

                <div className="panel p-6 sm:p-8">
                    <div className="mb-6">
                        <p className="eyebrow">Account access</p>
                        <h2 className="mt-3 text-2xl font-semibold tracking-[-0.03em] text-slate-950">
                            Sign in to your account
                        </h2>
                    </div>

                    <form onSubmit={handleSubmit} className="space-y-5">
                        <div>
                            <label htmlFor="email" className="mb-2 block text-sm font-medium text-slate-800">
                                Email address
                            </label>
                            <input
                                id="email"
                                name="email"
                                type="email"
                                autoComplete="email"
                                required
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                className="field"
                                placeholder="you@example.com"
                            />
                        </div>

                        <div>
                            <label htmlFor="password" className="mb-2 block text-sm font-medium text-slate-800">
                                Password
                            </label>
                            <input
                                id="password"
                                name="password"
                                type="password"
                                autoComplete="current-password"
                                required
                                minLength={8}
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="field"
                                placeholder="••••••••"
                            />
                        </div>

                        {error && (
                            <div className="rounded-[22px] border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
                                {error}
                            </div>
                        )}

                        <button type="submit" disabled={loading} className="btn-primary w-full">
                            {loading ? "Signing in..." : "Sign in"}
                            {!loading && <ArrowRight className="h-4 w-4" />}
                        </button>
                    </form>

                    <p className="mt-6 text-sm text-[var(--text-muted)]">
                        Not a member yet?{" "}
                        <a href="/pricing" className="font-medium text-[var(--accent)] hover:text-[var(--accent-strong)]">
                            View plans and pricing
                        </a>
                    </p>
                </div>
            </div>
        </div>
    );
}
