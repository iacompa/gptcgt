// Client component for interacting with the backend
"use client";

import { useState, useEffect } from "react";
import { Plus, Trash2, Copy, Check, Eye, EyeOff } from "lucide-react";
import { fetchAPI } from "@/lib/api";

export default function KeysPage() {
    const [keys, setKeys] = useState<any[]>([]);
    const [newKey, setNewKey] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [generating, setGenerating] = useState(false);
    const [newName, setNewName] = useState("anthropic"); // Added proper provider

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
        if (!newName) return;

        // In a real flow the key would be requested or generated
        const dummyKeyRaw = "sk-gptcgt-" + Math.random().toString(36).substring(2, 15);

        setGenerating(true);
        try {
            const data = await fetchAPI("/api_keys/", {
                method: "POST",
                body: JSON.stringify({ provider: newName, key: dummyKeyRaw })
            });
            setNewKey({ ...data, raw: dummyKeyRaw });
            setNewName("anthropic");
            loadKeys();
        } catch (e) {
            console.error(e);
            alert("Failed to create key");
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
                    <h1 className="text-2xl font-bold">API Keys</h1>
                    <p className="text-gray-400 mt-1">Manage keys used to authenticate your agent pipelines.</p>
                </div>
            </div>

            {newKey && (
                <div className="mb-8 p-6 bg-emerald-900/20 border border-emerald-500/50 rounded-xl">
                    <h3 className="text-emerald-400 font-bold mb-2">New key generated!</h3>
                    <p className="text-sm text-gray-300 mb-4">Please copy this key now. For your security, it will not be shown again.</p>
                    <div className="flex items-center gap-2">
                        <code className="flex-1 bg-black p-3 rounded text-emerald-300 font-mono text-sm break-all">
                            {newKey.raw}
                        </code>
                        <button
                            onClick={copyKey}
                            className="p-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded transition"
                        >
                            {copied ? <Check size={20} /> : <Copy size={20} />}
                        </button>
                    </div>
                    <button
                        onClick={() => setNewKey(null)}
                        className="mt-4 text-sm text-gray-400 hover:text-white underline"
                    >
                        I have copied the key
                    </button>
                </div>
            )}

            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-8">
                <h3 className="font-bold mb-4">Create New Key</h3>
                <form onSubmit={createKey} className="flex gap-4">
                    <select
                        value={newName}
                        onChange={(e) => setNewName(e.target.value)}
                        className="bg-gray-950 border border-gray-700 rounded-md px-4 py-2 text-white focus:outline-none focus:border-indigo-500"
                        required
                    >
                        <option value="anthropic">Anthropic</option>
                        <option value="openai">OpenAI</option>
                        <option value="google">Google</option>
                    </select>
                    <button
                        type="submit"
                        disabled={generating || !newName}
                        className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-md font-medium flex items-center gap-2 disabled:opacity-50"
                    >
                        <Plus size={18} /> {generating ? "Generating..." : "Generate Access Key"}
                    </button>
                </form>
            </div>

            <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                <table className="w-full text-left text-sm">
                    <thead className="bg-gray-800 text-gray-400">
                        <tr>
                            <th className="px-6 py-3 font-medium">PROVIDER</th>
                            <th className="px-6 py-3 font-medium">PREFIX</th>
                            <th className="px-6 py-3 font-medium">CREATED</th>
                            <th className="px-6 py-3 font-medium text-right">ACTIONS</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800">
                        {loading ? (
                            <tr><td colSpan={4} className="px-6 py-8 text-center text-gray-500">Loading keys...</td></tr>
                        ) : keys.length === 0 ? (
                            <tr><td colSpan={4} className="px-6 py-8 text-center text-gray-500">No active API keys found.</td></tr>
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
