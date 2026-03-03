// Client component for interacting with the backend
"use client";

import { useState, useEffect } from "react";
import { Plus, Trash2, Copy, Check } from "lucide-react";
import { fetchAPI } from "@/lib/api";

export default function KeysPage() {
    const [keys, setKeys] = useState<any[]>([]);
    const [newKey, setNewKey] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [generating, setGenerating] = useState(false);
    const [selectedProvider, setSelectedProvider] = useState("anthropic");
    const [apiKeyInput, setApiKeyInput] = useState("");

    useEffect(() => {
        loadKeys();
    }, []);

    const loadKeys = async () => {
        try {
            const data = await fetchAPI("/api_keys/");
            setKeys(data);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const createKey = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!selectedProvider || !apiKeyInput) return;

        setGenerating(true);
        try {
            const data = await fetchAPI("/api_keys/", {
                method: "POST",
                body: JSON.stringify({ provider: selectedProvider, key: apiKeyInput })
            });
            setNewKey({ ...data, raw: apiKeyInput });
            setApiKeyInput("");
            setSelectedProvider("anthropic");
            loadKeys();
        } catch (e: any) {
            console.error(e);
            alert(e.message || "Failed to store key");
        } finally {
            setGenerating(false);
        }
    };

    const deleteKey = async (id: string) => {
        if (!confirm("Are you sure you want to revoke this key?")) return;
        try {
            await fetchAPI(`/api_keys/${id}`, { method: "DELETE" });
            loadKeys();
        } catch (e) {
            console.error(e);
        }
    };

    const [copied, setCopied] = useState(false);
    const copyKey = () => {
        if (newKey) {
            navigator.clipboard.writeText(newKey.raw);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    };

    return (
        <div>
            <div className="flex justify-between items-end mb-6">
                <div>
                    <h1 className="text-2xl font-bold">API Key Vault</h1>
                    <p className="text-gray-400 mt-1">Store your provider API keys securely. They are encrypted with AES-256-GCM and used to proxy requests through GPTCGT.</p>
                </div>
            </div>

            {newKey && (
                <div className="mb-8 p-6 bg-emerald-900/20 border border-emerald-500/50 rounded-xl">
                    <h3 className="text-emerald-400 font-bold mb-2">Key stored successfully!</h3>
                    <p className="text-sm text-gray-300 mb-4">Your <span className="capitalize font-medium">{newKey.provider}</span> key has been encrypted and stored. Prefix: <code className="text-emerald-300">{newKey.key_prefix}</code></p>
                    <button
                        onClick={() => setNewKey(null)}
                        className="mt-2 text-sm text-gray-400 hover:text-white underline"
                    >
                        Dismiss
                    </button>
                </div>
            )}

            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-8">
                <h3 className="font-bold mb-2">Add Provider API Key</h3>
                <p className="text-sm text-gray-400 mb-4">Paste your API key from Anthropic, OpenAI, Google, or xAI. It will be encrypted before storage — we never see your raw key.</p>
                <form onSubmit={createKey} className="flex flex-col gap-4 sm:flex-row sm:items-end">
                    <select
                        value={selectedProvider}
                        onChange={(e) => setSelectedProvider(e.target.value)}
                        className="bg-gray-950 border border-gray-700 rounded-md px-4 py-2 text-white focus:outline-none focus:border-indigo-500"
                        required
                    >
                        <option value="anthropic">Anthropic</option>
                        <option value="openai">OpenAI</option>
                        <option value="google">Google AI</option>
                        <option value="xai">xAI</option>
                        <option value="deepseek">DeepSeek</option>
                    </select>
                    <input
                        type="password"
                        value={apiKeyInput}
                        onChange={(e) => setApiKeyInput(e.target.value)}
                        placeholder="sk-ant-... or sk-... or AIza..."
                        required
                        minLength={10}
                        className="flex-1 bg-gray-950 border border-gray-700 rounded-md px-4 py-2 text-white placeholder:text-gray-600 focus:outline-none focus:border-indigo-500 font-mono text-sm"
                    />
                    <button
                        type="submit"
                        disabled={generating || !apiKeyInput}
                        className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-md font-medium flex items-center gap-2 disabled:opacity-50 whitespace-nowrap"
                    >
                        <Plus size={18} /> {generating ? "Encrypting..." : "Store Key"}
                    </button>
                </form>
            </div>

            <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                <table className="w-full text-left text-sm">
                    <thead className="bg-gray-800 text-gray-400">
                        <tr>
                            <th className="px-6 py-3 font-medium">PROVIDER</th>
                            <th className="px-6 py-3 font-medium">KEY PREFIX</th>
                            <th className="px-6 py-3 font-medium">CREATED</th>
                            <th className="px-6 py-3 font-medium text-right">ACTIONS</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800">
                        {loading ? (
                            <tr><td colSpan={4} className="px-6 py-8 text-center text-gray-500">Loading keys...</td></tr>
                        ) : keys.length === 0 ? (
                            <tr><td colSpan={4} className="px-6 py-8 text-center text-gray-500">No API keys stored. Add your first provider key above.</td></tr>
                        ) : keys.map((key) => (
                            <tr key={key.id} className="hover:bg-gray-800/50">
                                <td className="px-6 py-4 font-medium capitalize">{key.provider}</td>
                                <td className="px-6 py-4 font-mono text-xs text-gray-400">{key.key_prefix}</td>
                                <td className="px-6 py-4 text-gray-400">{new Date(key.created_at).toLocaleDateString()}</td>
                                <td className="px-6 py-4 text-right">
                                    <button onClick={() => deleteKey(key.id)} className="text-red-400 hover:text-red-300">
                                        <Trash2 size={16} />
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
