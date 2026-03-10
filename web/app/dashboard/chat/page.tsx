"use client";

import { startTransition, useEffect, useRef, useState } from "react";
import { Bot, Check, Copy, Loader2, Send, Sparkles, User } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { useToast } from "@/components/toaster";

interface Message {
    id: string;
    role: "user" | "assistant";
    content: string;
    model?: string;
    timestamp: Date;
}

const STARTER_PROMPTS = [
    "Explain the most expensive part of this architecture.",
    "Draft a safer migration plan for a production schema change.",
    "Compare two model choices for a repo-wide refactor.",
];

export default function ChatPage() {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const [selectedModel, setSelectedModel] = useState("gpt-4o-mini");
    const [models, setModels] = useState<{ id: string; name: string; provider: string; tier: string }[]>([]);
    const [copiedId, setCopiedId] = useState<string | null>(null);
    const [credits, setCredits] = useState<number | null>(null);
    const scrollRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const messagesRef = useRef<Message[]>([]);
    const autoScrollRef = useRef(true);
    const scrollFrameRef = useRef<number | null>(null);
    const streamBufferRef = useRef("");
    const streamModelRef = useRef<string | undefined>(undefined);
    const streamFlushFrameRef = useRef<number | null>(null);
    const { pushToast } = useToast();

    useEffect(() => {
        messagesRef.current = messages;
    }, [messages]);

    useEffect(() => {
        apiClient.GET("/user/me")
            .then(({ data, error }) => {
                if (error) throw error;
                const profile = data as any;
                if (profile?.credits_remaining !== undefined) {
                    setCredits(profile.credits_remaining);
                }
            })
            .catch((error) => {
                console.error(error);
                pushToast({
                    tone: "error",
                    title: "Could not load profile",
                    description: "Credit balance may be unavailable until the backend responds.",
                });
            });

        apiClient.GET("/models")
            .then(({ data, error }) => {
                if (error) throw error;
                if (data && (data as any[]).length > 0) {
                    setModels(data as any[]);
                    setSelectedModel((previous) =>
                        (data as any[]).some((model) => model.id === previous)
                            ? previous
                            : (data as any[])[0].id
                    );
                }
            })
            .catch((error) => {
                console.error(error);
                pushToast({
                    tone: "info",
                    title: "Using fallback models",
                    description: "The model catalog is unavailable, so the default shortlist is shown.",
                });
            });
    }, [pushToast]);

    useEffect(() => {
        const scrollContainer = scrollRef.current;
        if (!scrollContainer) return;

        const updateAutoScroll = () => {
            const distanceFromBottom =
                scrollContainer.scrollHeight - scrollContainer.scrollTop - scrollContainer.clientHeight;
            autoScrollRef.current = distanceFromBottom < 120;
        };

        updateAutoScroll();
        scrollContainer.addEventListener("scroll", updateAutoScroll, { passive: true });
        return () => scrollContainer.removeEventListener("scroll", updateAutoScroll);
    }, []);

    useEffect(() => {
        return () => {
            if (scrollFrameRef.current !== null) {
                window.cancelAnimationFrame(scrollFrameRef.current);
            }
            if (streamFlushFrameRef.current !== null) {
                window.cancelAnimationFrame(streamFlushFrameRef.current);
            }
        };
    }, []);

    const resizeTextarea = () => {
        if (!textareaRef.current) return;
        textareaRef.current.style.height = "0px";
        textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 220)}px`;
    };

    useEffect(() => {
        resizeTextarea();
    }, [input]);

    const scheduleScrollToBottom = () => {
        if (!autoScrollRef.current || !scrollRef.current) return;
        if (scrollFrameRef.current !== null) {
            window.cancelAnimationFrame(scrollFrameRef.current);
        }
        scrollFrameRef.current = window.requestAnimationFrame(() => {
            scrollFrameRef.current = null;
            scrollRef.current?.scrollTo({
                top: scrollRef.current.scrollHeight,
                behavior: "auto",
            });
        });
    };

    const resetStreamBuffer = () => {
        if (streamFlushFrameRef.current !== null) {
            window.cancelAnimationFrame(streamFlushFrameRef.current);
            streamFlushFrameRef.current = null;
        }
        streamBufferRef.current = "";
        streamModelRef.current = undefined;
    };

    const flushAssistantMessage = (assistantId: string, immediate = false) => {
        const commit = () => {
            streamFlushFrameRef.current = null;
            const content = streamBufferRef.current;
            const model = streamModelRef.current;

            startTransition(() => {
                setMessages((current) =>
                    current.map((message) =>
                        message.id === assistantId
                            ? { ...message, content, ...(model ? { model } : {}) }
                            : message
                    )
                );
            });
            scheduleScrollToBottom();
        };

        if (immediate) {
            if (streamFlushFrameRef.current !== null) {
                window.cancelAnimationFrame(streamFlushFrameRef.current);
            }
            commit();
            return;
        }

        if (streamFlushFrameRef.current !== null) return;
        streamFlushFrameRef.current = window.requestAnimationFrame(commit);
    };

    const handleCopy = (id: string, content: string) => {
        navigator.clipboard.writeText(content);
        setCopiedId(id);
        window.setTimeout(() => setCopiedId(null), 1800);
    };

    const handleSubmit = async (event?: { preventDefault: () => void }) => {
        event?.preventDefault();
        if (!input.trim() || loading) return;

        const userMessage: Message = {
            id: `user-${Date.now()}`,
            role: "user",
            content: input.trim(),
            timestamp: new Date(),
        };

        const assistantId = `assistant-${Date.now()}`;
        const assistantMessage: Message = {
            id: assistantId,
            role: "assistant",
            content: "",
            timestamp: new Date(),
        };
        const requestMessages = [...messagesRef.current, userMessage];

        setMessages((current) => [...current, userMessage, assistantMessage]);
        messagesRef.current = [...requestMessages, assistantMessage];
        setInput("");
        setLoading(true);
        autoScrollRef.current = true;
        resetStreamBuffer();
        scheduleScrollToBottom();

        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    model: selectedModel,
                    messages: requestMessages.map((message) => ({
                        role: message.role,
                        content: message.content,
                    })),
                }),
            });

            if (!response.ok) {
                const payload = await response.json().catch(() => ({}));
                const errorMessage = payload.error || response.statusText;
                resetStreamBuffer();
                setMessages((current) =>
                    current.map((message) =>
                        message.id === assistantId ? { ...message, content: `Error: ${errorMessage}` } : message
                    )
                );
                pushToast({
                    tone: "error",
                    title: "Chat request failed",
                    description: errorMessage,
                });
                return;
            }

            const reader = response.body?.getReader();
            const decoder = new TextDecoder();
            if (!reader) {
                resetStreamBuffer();
                setMessages((current) =>
                    current.map((message) =>
                        message.id === assistantId
                            ? { ...message, content: "No response body was returned." }
                            : message
                    )
                );
                return;
            }

            let accumulated = "";
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                for (const line of chunk.split("\n")) {
                    if (!line.startsWith("data: ")) continue;
                    const data = line.slice(6);
                    if (data === "[DONE]") continue;
                    try {
                        const parsed = JSON.parse(data);
                        const delta = parsed.choices?.[0]?.delta?.content || "";
                        accumulated += delta;
                        streamBufferRef.current = accumulated;
                        streamModelRef.current = parsed.model;
                        flushAssistantMessage(assistantId);
                    } catch {
                        accumulated += data;
                        streamBufferRef.current = accumulated;
                        flushAssistantMessage(assistantId);
                    }
                }
            }
            flushAssistantMessage(assistantId, true);
            resetStreamBuffer();
        } catch (error: any) {
            resetStreamBuffer();
            setMessages((current) =>
                current.map((message) =>
                    message.id === assistantId
                        ? { ...message, content: `Connection error: ${error.message}` }
                        : message
                )
            );
            pushToast({
                tone: "error",
                title: "Connection error",
                description: error.message,
            });
        } finally {
            setLoading(false);
        }
    };

    const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            void handleSubmit();
        }
    };

    const applyStarterPrompt = (prompt: string) => {
        setInput(prompt);
        window.requestAnimationFrame(() => textareaRef.current?.focus());
    };

    return (
        <div className="grid gap-6 xl:grid-cols-[280px_1fr]">
            <aside className="space-y-4">
                <div className="panel p-5">
                    <p className="eyebrow">Chat</p>
                    <h1 className="mt-3 text-2xl font-semibold tracking-[-0.03em] text-slate-950">
                        Fast model routing, without leaving the workspace.
                    </h1>
                    <p className="mt-3 copy-sm">
                        Use chat for probing questions, draft generation, and quick comparisons before a repo-aware run.
                    </p>
                </div>

                <div className="panel p-5">
                    <p className="metric-label">Model selection</p>
                    <select
                        value={selectedModel}
                        onChange={(event) => setSelectedModel(event.target.value)}
                        className="select-field mt-3"
                    >
                        {models.length > 0 ? (
                            models.map((model) => (
                                <option key={model.id} value={model.id}>
                                    {model.name} ({model.provider} · {model.tier})
                                </option>
                            ))
                        ) : (
                            <>
                                <option value="gpt-4o-mini">gpt-4o-mini</option>
                                <option value="gpt-4o">gpt-4o</option>
                                <option value="claude-3-7-sonnet-20250219">Claude 3.7 Sonnet</option>
                                <option value="deepseek-chat">DeepSeek V3</option>
                                <option value="o3-mini">o3-mini</option>
                            </>
                        )}
                    </select>
                    <div className="mt-4 rounded-[22px] bg-[var(--accent-soft)] px-4 py-3 text-sm text-[var(--accent-strong)]">
                        <div className="flex items-center gap-2 font-medium">
                            <Sparkles className="h-4 w-4" />
                            {credits !== null ? `${credits.toLocaleString()} credits available` : "Loading credit balance"}
                        </div>
                        <p className="mt-1 text-sm opacity-80">Use chat to validate intent before spending on deeper repo orchestration.</p>
                    </div>
                </div>

                <div className="panel p-5">
                    <p className="metric-label">Starter prompts</p>
                    <div className="mt-3 space-y-2">
                        {STARTER_PROMPTS.map((prompt) => (
                            <button
                                key={prompt}
                                type="button"
                                onClick={() => applyStarterPrompt(prompt)}
                                className="panel-muted w-full p-3 text-left text-sm text-slate-700 transition hover:bg-white/80"
                            >
                                {prompt}
                            </button>
                        ))}
                    </div>
                </div>
            </aside>

            <section className="flex min-h-[68vh] flex-col gap-4">
                <div className="panel flex flex-wrap items-center justify-between gap-3 px-5 py-4">
                    <div>
                        <p className="text-sm font-semibold text-slate-950">Conversation</p>
                        <p className="text-sm text-[var(--text-muted)]">
                            Stream responses through the proxy and keep the selected model explicit.
                        </p>
                    </div>
                    <div className="badge badge-accent">{selectedModel}</div>
                </div>

                <div ref={scrollRef} className="panel flex-1 space-y-4 overflow-y-auto p-4 sm:p-5">
                    {messages.length === 0 ? (
                        <div className="flex h-full min-h-[320px] flex-col items-center justify-center rounded-[24px] border border-dashed border-[var(--border-strong)] bg-white/45 px-6 text-center">
                            <Bot className="h-10 w-10 text-[var(--accent)]" />
                            <h2 className="mt-4 text-xl font-semibold tracking-[-0.03em] text-slate-950">
                                Start with a narrow question.
                            </h2>
                            <p className="mt-2 max-w-md text-sm text-[var(--text-muted)]">
                                Ask for architecture critique, refactor planning, cost tradeoffs, or model selection advice before you launch a heavier workflow.
                            </p>
                        </div>
                    ) : (
                        messages.map((message) => (
                            <div
                                key={message.id}
                                className={`rounded-[28px] px-4 py-4 sm:px-5 ${
                                    message.role === "user"
                                        ? "ml-auto max-w-3xl bg-slate-950 text-white"
                                        : "max-w-3xl border border-[var(--border)] bg-white/75 text-slate-800"
                                }`}
                            >
                                <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] opacity-70">
                                    {message.role === "user" ? (
                                        <User className="h-3.5 w-3.5" />
                                    ) : (
                                        <Bot className="h-3.5 w-3.5" />
                                    )}
                                    <span>{message.role === "user" ? "You" : "Assistant"}</span>
                                    {message.model && <span className="rounded-full bg-black/5 px-2 py-1 normal-case tracking-normal">{message.model}</span>}
                                    <span className="normal-case tracking-normal">
                                        {message.timestamp.toLocaleTimeString(undefined, {
                                            hour: "numeric",
                                            minute: "2-digit",
                                        })}
                                    </span>
                                </div>
                                <div className="mt-3 whitespace-pre-wrap text-sm leading-7">
                                    {message.content || (
                                        <span className="inline-flex items-center gap-2 text-sm opacity-70">
                                            <Loader2 className="h-4 w-4 animate-spin" />
                                            Thinking...
                                        </span>
                                    )}
                                </div>
                                {message.content && message.role === "assistant" && (
                                    <button
                                        type="button"
                                        onClick={() => handleCopy(message.id, message.content)}
                                        className="mt-3 inline-flex items-center gap-2 text-xs font-medium text-[var(--accent)]"
                                    >
                                        {copiedId === message.id ? (
                                            <>
                                                <Check className="h-3.5 w-3.5" /> Copied
                                            </>
                                        ) : (
                                            <>
                                                <Copy className="h-3.5 w-3.5" /> Copy response
                                            </>
                                        )}
                                    </button>
                                )}
                            </div>
                        ))
                    )}
                </div>

                <form onSubmit={handleSubmit} className="panel p-4">
                    <textarea
                        ref={textareaRef}
                        value={input}
                        onChange={(event) => setInput(event.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Ask for architecture feedback, a migration plan, or a model recommendation..."
                        rows={1}
                        className="textarea-field min-h-[88px]"
                        style={{ maxHeight: "220px" }}
                    />
                    <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                        <p className="text-sm text-[var(--text-muted)]">Press Enter to send. Use Shift+Enter for a new line.</p>
                        <button type="submit" disabled={loading || !input.trim()} className="btn-primary">
                            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                            Send prompt
                        </button>
                    </div>
                </form>
            </section>
        </div>
    );
}
