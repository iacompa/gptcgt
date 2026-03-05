"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Loader2, Sparkles, Copy, Check } from "lucide-react";
import { apiClient } from "@/lib/api-client";

interface Message {
    id: string;
    role: "user" | "assistant";
    content: string;
    model?: string;
    timestamp: Date;
}

export default function ChatPage() {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const [selectedModel, setSelectedModel] = useState("gpt-4o-mini");
    const [copiedId, setCopiedId] = useState<string | null>(null);
    const [credits, setCredits] = useState<number | null>(null);
    const scrollRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);

    useEffect(() => {
        apiClient.GET("/user/me")
            .then(({ data, error }) => {
                if (error) throw error;
                const profile = data as any;
                if (profile?.credits_remaining !== undefined) {
                    setCredits(profile.credits_remaining);
                }
            })
            .catch(console.error);
    }, []);

    useEffect(() => {
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }, [messages]);

    const handleCopy = (id: string, content: string) => {
        navigator.clipboard.writeText(content);
        setCopiedId(id);
        setTimeout(() => setCopiedId(null), 2000);
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || loading) return;

        const userMsg: Message = {
            id: `user-${Date.now()}`,
            role: "user",
            content: input.trim(),
            timestamp: new Date(),
        };

        setMessages((prev) => [...prev, userMsg]);
        setInput("");
        setLoading(true);

        const assistantId = `assistant-${Date.now()}`;
        const assistantMsg: Message = {
            id: assistantId,
            role: "assistant",
            content: "",
            timestamp: new Date(),
        };
        setMessages((prev) => [...prev, assistantMsg]);

        try {
            const res = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    model: selectedModel,
                    messages: [...messages, userMsg].map((m) => ({
                        role: m.role,
                        content: m.content,
                    })),
                }),
            });

            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                setMessages((prev) =>
                    prev.map((m) =>
                        m.id === assistantId
                            ? { ...m, content: `Error: ${err.error || res.statusText}` }
                            : m
                    )
                );
                return;
            }

            // Stream response
            const reader = res.body?.getReader();
            const decoder = new TextDecoder();

            if (!reader) {
                setMessages((prev) =>
                    prev.map((m) =>
                        m.id === assistantId ? { ...m, content: "No response received" } : m
                    )
                );
                return;
            }

            let accumulated = "";
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split("\n");

                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        const data = line.slice(6);
                        if (data === "[DONE]") break;
                        try {
                            const parsed = JSON.parse(data);
                            const delta = parsed.choices?.[0]?.delta?.content || "";
                            accumulated += delta;
                            setMessages((prev) =>
                                prev.map((m) =>
                                    m.id === assistantId
                                        ? { ...m, content: accumulated, model: parsed.model }
                                        : m
                                )
                            );
                        } catch {
                            // Non-JSON line — treat as plain text
                            accumulated += data;
                            setMessages((prev) =>
                                prev.map((m) =>
                                    m.id === assistantId ? { ...m, content: accumulated } : m
                                )
                            );
                        }
                    }
                }
            }
        } catch (err: any) {
            setMessages((prev) =>
                prev.map((m) =>
                    m.id === assistantId
                        ? { ...m, content: `Connection error: ${err.message}` }
                        : m
                )
            );
        } finally {
            setLoading(false);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(e);
        }
    };

    return (
        <div className="flex flex-col h-[calc(100vh-4rem)] max-w-4xl mx-auto">
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h1 className="text-2xl font-bold">Chat</h1>
                    <p className="text-gray-400 text-sm mt-1">
                        Send prompts through the gptcgt proxy to any model
                    </p>
                </div>
                <div className="flex items-center gap-4">
                    <select
                        value={selectedModel}
                        onChange={(e) => setSelectedModel(e.target.value)}
                        className="bg-gray-900 border border-gray-800 rounded px-3 py-1.5 text-sm text-gray-300 focus:outline-none focus:border-indigo-500/50"
                    >
                        <option value="gpt-4o-mini">Fast (Scout - 1 cr)</option>
                        <option value="gpt-4o">Smart (Standard - 5 cr)</option>
                        <option value="claude-3-7-sonnet-20250219">Claude 3.7 (Standard - 5 cr)</option>
                        <option value="deepseek-chat">DeepSeek V3 (Standard - 5 cr)</option>
                        <option value="o3-mini">o3-mini (Scout - 1 cr)</option>
                    </select>
                    <div className="flex items-center gap-4 text-xs font-medium bg-gray-900 border border-gray-800 px-3 py-1.5 rounded text-gray-300">
                        {credits !== null ? (
                            <span className="flex items-center gap-1.5" title="Available Credits">
                                <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
                                {credits.toLocaleString()} Credits
                            </span>
                        ) : (
                            <span className="flex items-center gap-1.5">
                                <Loader2 className="h-3.5 w-3.5 animate-spin text-gray-500" />
                                Loading...
                            </span>
                        )}
                    </div>
                </div>
            </div>

            {/* Messages */}
            <div
                ref={scrollRef}
                className="flex-1 overflow-y-auto space-y-1 pr-2 scrollbar-thin scrollbar-thumb-gray-800"
            >
                {messages.length === 0 && (
                    <div className="flex flex-col items-center justify-center h-full text-gray-500">
                        <Bot className="h-16 w-16 mb-4 text-gray-700" />
                        <p className="text-lg font-medium text-gray-400">Start a conversation</p>
                        <p className="text-sm mt-1">
                            Messages are routed through the gptcgt proxy using your credits
                        </p>
                    </div>
                )}

                {messages.map((msg) => (
                    <div
                        key={msg.id}
                        className={`group flex gap-3 py-4 px-4 rounded-xl transition-colors ${msg.role === "user"
                            ? "bg-gray-900/40"
                            : "bg-gray-900/70 border border-gray-800/50"
                            }`}
                    >
                        <div
                            className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center ${msg.role === "user"
                                ? "bg-indigo-500/20 text-indigo-400"
                                : "bg-emerald-500/20 text-emerald-400"
                                }`}
                        >
                            {msg.role === "user" ? (
                                <User className="h-4 w-4" />
                            ) : (
                                <Bot className="h-4 w-4" />
                            )}
                        </div>

                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                                <span className="text-xs font-medium text-gray-400">
                                    {msg.role === "user" ? "You" : "Assistant"}
                                </span>
                                {msg.model && (
                                    <span className="text-[10px] bg-gray-800 text-gray-500 px-1.5 py-0.5 rounded">
                                        {msg.model}
                                    </span>
                                )}
                                <span className="text-[10px] text-gray-600">
                                    {msg.timestamp.toLocaleTimeString(undefined, {
                                        hour: "numeric",
                                        minute: "2-digit",
                                    })}
                                </span>
                            </div>

                            <div className="text-sm text-gray-200 whitespace-pre-wrap break-words leading-relaxed">
                                {msg.content || (
                                    <span className="flex items-center gap-2 text-gray-500">
                                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                        Thinking...
                                    </span>
                                )}
                            </div>

                            {/* Copy button */}
                            {msg.content && msg.role === "assistant" && (
                                <button
                                    onClick={() => handleCopy(msg.id, msg.content)}
                                    className="mt-2 opacity-0 group-hover:opacity-100 transition-opacity text-gray-500 hover:text-gray-300 text-xs flex items-center gap-1"
                                >
                                    {copiedId === msg.id ? (
                                        <>
                                            <Check className="h-3 w-3" /> Copied
                                        </>
                                    ) : (
                                        <>
                                            <Copy className="h-3 w-3" /> Copy
                                        </>
                                    )}
                                </button>
                            )}
                        </div>
                    </div>
                ))}
            </div>

            {/* Input */}
            <form onSubmit={handleSubmit} className="mt-4 relative">
                <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden focus-within:border-indigo-500/50 transition-colors">
                    <textarea
                        ref={inputRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Send a message..."
                        rows={1}
                        className="block w-full bg-transparent py-4 px-5 pr-14 text-white placeholder:text-gray-500 focus:outline-none resize-none text-sm"
                        style={{ minHeight: "56px", maxHeight: "200px" }}
                    />
                    <div className="flex items-center justify-between px-4 pb-3">
                        <span className="text-[10px] text-gray-600">
                            Shift+Enter for new line
                        </span>
                        <button
                            type="submit"
                            disabled={loading || !input.trim()}
                            className="bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-800 disabled:text-gray-600 text-white p-2 rounded-lg transition-colors"
                        >
                            {loading ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                                <Send className="h-4 w-4" />
                            )}
                        </button>
                    </div>
                </div>
            </form>
        </div>
    );
}
