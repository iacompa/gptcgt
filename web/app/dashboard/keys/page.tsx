"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, Copy, KeyRound, Plus, ShieldCheck, Trash2 } from "lucide-react";
import { fetchAPI } from "@/lib/api";
import { useToast } from "@/components/toaster";
import { ConfirmDialog } from "@/components/confirm-dialog";

export default function KeysPage() {
    const [keys, setKeys] = useState<any[]>([]);
    const [newKey, setNewKey] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [generating, setGenerating] = useState(false);
    const [selectedProvider, setSelectedProvider] = useState("anthropic");
    const [apiKeyInput, setApiKeyInput] = useState("");
    const [copied, setCopied] = useState(false);
    const [keyToDelete, setKeyToDelete] = useState<string | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);
    const { pushToast } = useToast();

    const describeError = (error: any, fallback: string) => {
        const detail =
            error?.detail ||
            error?.error?.detail ||
            error?.error ||
            error?.data?.detail ||
            error?.response?.data?.detail;

        if (typeof detail === "string" && detail.trim()) {
            return detail;
        }

        if (typeof error?.message === "string" && error.message.trim()) {
            return error.message;
        }

        return fallback;
    };

    const loadKeys = useCallback(async () => {
        try {
            const data = (await fetchAPI("/api_keys/")) as any[];
            setKeys(data || []);
        } catch (error: any) {
            console.error(error);
            pushToast({
                tone: "error",
                title: "Could not load API keys",
                description: describeError(error, "Failed to load the encrypted key vault."),
            });
        } finally {
            setLoading(false);
        }
    }, [pushToast]);

    useEffect(() => {
        void loadKeys();
    }, [loadKeys]);

    const createKey = async (event: React.FormEvent) => {
        event.preventDefault();
        if (!selectedProvider || !apiKeyInput) return;

        setGenerating(true);
        try {
            const data = await fetchAPI("/api_keys/", {
                method: "POST",
                body: JSON.stringify({ provider: selectedProvider, key: apiKeyInput }),
            });
            setNewKey({ ...(data as any), raw: apiKeyInput });
            setApiKeyInput("");
            setSelectedProvider("anthropic");
            await loadKeys();
            pushToast({
                tone: "success",
                title: "Key stored securely",
                description: `Encrypted ${selectedProvider} credentials were added to the vault.`,
            });
        } catch (error: any) {
            console.error(error);
            pushToast({
                tone: "error",
                title: "Failed to store key",
                description: describeError(error, "Please verify the provider and key format."),
            });
        } finally {
            setGenerating(false);
        }
    };

    const deleteKey = async () => {
        if (!keyToDelete) return;
        setIsDeleting(true);
        try {
            await fetchAPI(`/api_keys/${keyToDelete}`, {
                method: "DELETE",
            });
            await loadKeys();
            setKeyToDelete(null);
            pushToast({
                tone: "success",
                title: "Key revoked",
                description: "The provider key was removed from the vault.",
            });
        } catch (error: any) {
            console.error(error);
            pushToast({
                tone: "error",
                title: "Failed to revoke key",
                description: describeError(error, "Failed to revoke the stored provider key."),
            });
        } finally {
            setIsDeleting(false);
        }
    };

    const copyKey = () => {
        if (!newKey) return;
        navigator.clipboard.writeText(newKey.raw);
        setCopied(true);
        window.setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="page-stack">
            <section className="hero-panel p-6 sm:p-8">
                <p className="eyebrow">API key vault</p>
                <h1 className="mt-3 text-3xl font-semibold tracking-[-0.04em] text-slate-950 sm:text-4xl">
                    Store provider credentials without turning the browser into a secret manager.
                </h1>
                <p className="mt-3 max-w-3xl copy-lg">
                    Keys are encrypted before storage and used only for proxy execution. The goal is to keep setup friction low without hiding the security model.
                </p>
            </section>

            {newKey && (
                <section className="panel p-5">
                    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                            <p className="eyebrow">Latest vault update</p>
                            <h2 className="mt-2 text-xl font-semibold tracking-[-0.03em] text-slate-950">
                                {newKey.provider} key stored successfully
                            </h2>
                            <p className="mt-2 text-sm text-[var(--text-muted)]">
                                Prefix <span className="mono font-medium text-slate-950">{newKey.key_prefix}</span>
                            </p>
                        </div>
                        <div className="flex gap-3">
                            <button type="button" onClick={copyKey} className="btn-secondary">
                                {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                                {copied ? "Copied" : "Copy raw key once"}
                            </button>
                            <button type="button" onClick={() => setNewKey(null)} className="btn-ghost">
                                Dismiss
                            </button>
                        </div>
                    </div>
                </section>
            )}

            <section className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
                <div className="panel p-6">
                    <div className="flex items-center gap-2">
                        <Plus className="h-5 w-5 text-[var(--accent)]" />
                        <h2 className="text-xl font-semibold tracking-[-0.03em] text-slate-950">Add provider key</h2>
                    </div>
                    <p className="mt-3 text-sm text-[var(--text-muted)]">
                        Paste a provider key from Anthropic, OpenAI, Google, xAI, or DeepSeek. The raw value is encrypted before it is stored.
                    </p>
                    <form onSubmit={createKey} className="mt-5 space-y-4">
                        <div>
                            <label className="mb-2 block text-sm font-medium text-slate-900">Provider</label>
                            <select
                                value={selectedProvider}
                                onChange={(event) => setSelectedProvider(event.target.value)}
                                className="select-field"
                                required
                            >
                                <option value="anthropic">Anthropic</option>
                                <option value="openai">OpenAI</option>
                                <option value="google">Google AI</option>
                                <option value="xai">xAI</option>
                                <option value="deepseek">DeepSeek</option>
                            </select>
                        </div>
                        <div>
                            <label className="mb-2 block text-sm font-medium text-slate-900">API key</label>
                            <input
                                type="password"
                                value={apiKeyInput}
                                onChange={(event) => setApiKeyInput(event.target.value)}
                                placeholder="sk-ant-... or sk-... or AIza..."
                                required
                                minLength={10}
                                className="field mono"
                            />
                        </div>
                        <button type="submit" disabled={generating || !apiKeyInput} className="btn-primary">
                            {generating ? "Encrypting..." : "Store key"}
                            {!generating && <KeyRound className="h-4 w-4" />}
                        </button>
                    </form>
                </div>

                <div className="panel p-6">
                    <div className="flex items-center gap-2">
                        <ShieldCheck className="h-5 w-5 text-[var(--amber)]" />
                        <h2 className="text-xl font-semibold tracking-[-0.03em] text-slate-950">Vault posture</h2>
                    </div>
                    <div className="mt-5 space-y-4 text-sm text-[var(--text-muted)]">
                        <div className="panel-muted p-4">Keys are encrypted with AES-256-GCM before they hit storage.</div>
                        <div className="panel-muted p-4">The UI only displays provider and key prefix, not the full secret.</div>
                        <div className="panel-muted p-4">Revoking a key removes it from the browser-visible list and backend lookup path.</div>
                    </div>
                </div>
            </section>

            <section className="table-shell">
                <table>
                    <thead>
                        <tr>
                            <th>Provider</th>
                            <th>Key prefix</th>
                            <th>Created</th>
                            <th className="text-right">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {loading ? (
                            <tr>
                                <td colSpan={4} className="px-5 py-8 text-center text-[var(--text-muted)]">
                                    Loading keys...
                                </td>
                            </tr>
                        ) : keys.length === 0 ? (
                            <tr>
                                <td colSpan={4} className="px-5 py-8 text-center text-[var(--text-muted)]">
                                    No API keys stored yet.
                                </td>
                            </tr>
                        ) : (
                            keys.map((key) => (
                                <tr key={key.id}>
                                    <td className="font-medium capitalize text-slate-900">{key.provider}</td>
                                    <td className="mono text-sm text-[var(--text-muted)]">{key.key_prefix}</td>
                                    <td>{new Date(key.created_at).toLocaleDateString()}</td>
                                    <td className="text-right">
                                        <button
                                            type="button"
                                            onClick={() => setKeyToDelete(key.id)}
                                            className="btn-ghost ml-auto text-red-700 hover:bg-red-50"
                                        >
                                            <Trash2 className="h-4 w-4" />
                                            Revoke
                                        </button>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </section>

            <ConfirmDialog
                open={!!keyToDelete}
                title="Revoke provider key?"
                description="This removes the key from the vault. Proxy requests that depend on it will fail until a replacement is stored."
                confirmLabel="Revoke key"
                busy={isDeleting}
                onCancel={() => setKeyToDelete(null)}
                onConfirm={deleteKey}
            />
        </div>
    );
}
