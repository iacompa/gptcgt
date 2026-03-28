"use client";

import { memo, startTransition, useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import {
    ExternalLink,
    File,
    Folder,
    Github,
    GitBranch,
    Globe,
    Loader2,
    Lock,
    Play,
    RefreshCw,
    Search,
    Square,
    Star,
} from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { useToast } from "@/components/toaster";

interface Repo {
    id: number;
    name: string;
    full_name: string;
    description: string | null;
    language: string | null;
    private: boolean;
    updated_at: string;
    html_url: string;
    clone_url?: string;
    default_branch: string;
    stargazers_count: number;
}

interface TreeItem {
    path: string;
    type: "blob" | "tree";
    size: number;
    sha: string;
}

interface TreeNode extends TreeItem {
    name: string;
    children: TreeNode[];
    expanded: boolean;
}

function buildTree(items: TreeItem[]): TreeNode[] {
    const root: TreeNode[] = [];
    const map = new Map<string, TreeNode>();

    items
        .slice()
        .sort((left, right) => {
            if (left.type !== right.type) return left.type === "tree" ? -1 : 1;
            return left.path.localeCompare(right.path);
        })
        .forEach((item) => {
            const parts = item.path.split("/");
            const name = parts[parts.length - 1];
            const node: TreeNode = { ...item, name, children: [], expanded: false };
            map.set(item.path, node);

            if (parts.length === 1) {
                root.push(node);
                return;
            }

            const parent = map.get(parts.slice(0, -1).join("/"));
            if (parent) {
                parent.children.push(node);
            } else {
                root.push(node);
            }
        });

    return root;
}

function toggleNode(nodes: TreeNode[], path: string): TreeNode[] {
    return nodes.map((node) => {
        if (node.path === path) {
            return { ...node, expanded: !node.expanded };
        }
        if (node.children.length > 0) {
            return { ...node, children: toggleNode(node.children, path) };
        }
        return node;
    });
}

const FileTreeNode = memo(function FileTreeNodeView({
    node,
    depth,
    onSelect,
    onToggle,
}: {
    node: TreeNode;
    depth: number;
    onSelect: (path: string) => void;
    onToggle: (path: string) => void;
}) {
    const isDir = node.type === "tree";
    const color = isDir ? "text-[var(--accent)]" : "text-slate-500";

    return (
        <div>
            <button
                type="button"
                onClick={() => (isDir ? onToggle(node.path) : onSelect(node.path))}
                className="flex w-full items-center gap-2 rounded-2xl px-3 py-2 text-left text-sm text-slate-700 transition hover:bg-white/70"
                style={{ paddingLeft: `${depth * 16 + 12}px` }}
            >
                {isDir ? <Folder className={`h-4 w-4 ${color}`} /> : <File className={`h-4 w-4 ${color}`} />}
                <span className="truncate">{node.name}</span>
                {!isDir && node.size > 0 && (
                    <span className="ml-auto text-[11px] text-[var(--text-soft)]">
                        {node.size > 1024 ? `${(node.size / 1024).toFixed(1)}KB` : `${node.size}B`}
                    </span>
                )}
            </button>
            {isDir && node.expanded && (
                <div>
                    {node.children.map((child) => (
                        <FileTreeNode
                            key={child.path}
                            node={child}
                            depth={depth + 1}
                            onSelect={onSelect}
                            onToggle={onToggle}
                        />
                    ))}
                </div>
            )}
        </div>
    );
});

const MAX_VISIBLE_RUN_LOGS = 1500;

export default function HubPage() {
    const [connected, setConnected] = useState(false);
    const [ghUsername, setGhUsername] = useState("");
    const [repos, setRepos] = useState<Repo[]>([]);
    const [selectedRepo, setSelectedRepo] = useState<Repo | null>(null);
    const [tree, setTree] = useState<TreeNode[]>([]);
    const [fileContent, setFileContent] = useState<string | null>(null);
    const [selectedFile, setSelectedFile] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [loadingTree, setLoadingTree] = useState(false);
    const [loadingFile, setLoadingFile] = useState(false);
    const [repoSearch, setRepoSearch] = useState("");
    const [activeRunId, setActiveRunId] = useState<string | null>(null);
    const [runLogs, setRunLogs] = useState<string[]>([]);
    const [runPrompt, setRunPrompt] = useState("");
    const [isStartingRun, setIsStartingRun] = useState(false);
    const [isCancellingRun, setIsCancellingRun] = useState(false);
    const eventSourceRef = useRef<EventSource | null>(null);
    const logViewportRef = useRef<HTMLDivElement>(null);
    const logBufferRef = useRef<string[]>([]);
    const logFlushTimerRef = useRef<number | null>(null);
    const stickToBottomRef = useRef(true);
    const { pushToast } = useToast();
    const deferredRepoSearch = useDeferredValue(repoSearch);

    const scheduleLogScroll = useCallback(() => {
        if (!stickToBottomRef.current) return;
        window.requestAnimationFrame(() => {
            logViewportRef.current?.scrollTo({
                top: logViewportRef.current.scrollHeight,
                behavior: "auto",
            });
        });
    }, []);

    const flushRunLogs = useCallback((force = false) => {
        const commit = () => {
            logFlushTimerRef.current = null;
            if (logBufferRef.current.length === 0) return;

            const chunk = logBufferRef.current.splice(0, logBufferRef.current.length);
            startTransition(() => {
                setRunLogs((current) => {
                    const next = current.concat(chunk);
                    return next.length > MAX_VISIBLE_RUN_LOGS
                        ? next.slice(next.length - MAX_VISIBLE_RUN_LOGS)
                        : next;
                });
            });
            scheduleLogScroll();
        };

        if (force) {
            if (logFlushTimerRef.current !== null) {
                window.clearTimeout(logFlushTimerRef.current);
            }
            commit();
            return;
        }

        if (logFlushTimerRef.current !== null) return;
        logFlushTimerRef.current = window.setTimeout(commit, 48);
    }, [scheduleLogScroll]);

    const loadRepos = useCallback(async () => {
        try {
            const { data, error } = await apiClient.GET("/github/repos");
            if (error) throw error;
            setRepos((data as any[]) || []);
        } catch (error: any) {
            console.error(error);
            pushToast({
                tone: "error",
                title: "Could not load repositories",
                description: error.message,
            });
        }
    }, [pushToast]);

    const checkGithubStatus = useCallback(async () => {
        try {
            const { data, error } = await apiClient.GET("/github/status");
            if (error) throw error;
            const status = data as any;
            setConnected(!!status?.connected);
            setGhUsername(status?.username || "");
            if (status?.connected) {
                await loadRepos();
            }
        } catch {
            setConnected(false);
        } finally {
            setLoading(false);
        }
    }, [loadRepos]);

    useEffect(() => {
        void checkGithubStatus();
        return () => {
            eventSourceRef.current?.close();
            if (logFlushTimerRef.current !== null) {
                window.clearTimeout(logFlushTimerRef.current);
            }
        };
    }, [checkGithubStatus]);

    useEffect(() => {
        const viewport = logViewportRef.current;
        if (!viewport) return;

        const updateStickiness = () => {
            const distanceFromBottom =
                viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight;
            stickToBottomRef.current = distanceFromBottom < 120;
        };

        updateStickiness();
        viewport.addEventListener("scroll", updateStickiness, { passive: true });
        return () => viewport.removeEventListener("scroll", updateStickiness);
    }, []);

    const listenToLogs = (runId: string) => {
        eventSourceRef.current?.close();
        const eventSource = new EventSource(`/api/backend/hub/${runId}/logs`);
        eventSourceRef.current = eventSource;

        eventSource.addEventListener("status", (event) => {
            flushRunLogs(true);
            eventSource.close();
            eventSourceRef.current = null;
            setActiveRunId(null);

            let status = "unknown";
            try {
                status = JSON.parse((event as MessageEvent).data).status || "unknown";
            } catch {
                status = "unknown";
            }

            if (status === "completed") {
                pushToast({
                    tone: "success",
                    title: "Hub run finished",
                    description: "The run completed and the log stream closed cleanly.",
                });
                return;
            }

            if (status === "cancelled") {
                pushToast({
                    tone: "info",
                    title: "Hub run cancelled",
                    description: "The run exited after the cancellation request.",
                });
                return;
            }

            pushToast({
                tone: "error",
                title: "Hub run failed",
                description: "The runner exited without producing a successful result.",
            });
        });

        eventSource.onmessage = (event) => {
            if (event.data === "[DONE]") {
                flushRunLogs(true);
                return;
            }
            logBufferRef.current.push(event.data);
            flushRunLogs();
        };

        eventSource.onerror = () => {
            flushRunLogs(true);
            eventSource.close();
            eventSourceRef.current = null;
            setActiveRunId(null);
            pushToast({
                tone: "error",
                title: "Hub log stream disconnected",
                description: "The log stream ended unexpectedly.",
            });
        };
    };

    const handleConnect = async () => {
        try {
            const { data, error } = await apiClient.GET("/github/connect");
            if (error) throw error;
            const response = data as any;
            if (response?.auth_url) {
                window.location.href = response.auth_url;
            }
        } catch (error: any) {
            pushToast({
                tone: "error",
                title: "GitHub connect failed",
                description: error.message || "The backend did not return an OAuth URL.",
            });
        }
    };

    const handleDisconnect = async () => {
        try {
            const response = await fetch("/api/backend/github/disconnect", {
                method: "POST",
                credentials: "include",
            });
            if (!response.ok) {
                const payload = await response.json().catch(() => ({}));
                throw new Error(payload.detail || payload.error || "The backend could not clear the GitHub integration.");
            }

            eventSourceRef.current?.close();
            eventSourceRef.current = null;
            setConnected(false);
            setGhUsername("");
            setRepos([]);
            setSelectedRepo(null);
            setTree([]);
            setFileContent(null);
            setSelectedFile(null);
            setRunLogs([]);
            setActiveRunId(null);
            pushToast({
                tone: "success",
                title: "GitHub disconnected",
                description: "Repo browsing is disabled until a new GitHub connection is created.",
            });
        } catch (error: any) {
            pushToast({
                tone: "error",
                title: "GitHub disconnect failed",
                description: error.message || "The backend could not clear the GitHub integration.",
            });
        }
    };

    const selectRepo = useCallback(async (repo: Repo) => {
        setSelectedRepo(repo);
        setFileContent(null);
        setSelectedFile(null);
        setLoadingTree(true);

        try {
            const [owner, name] = repo.full_name.split("/");
            const { data, error } = await apiClient.GET("/github/tree/{owner}/{repo}", {
                params: {
                    path: { owner, repo: name },
                    query: { branch: repo.default_branch },
                },
            });
            if (error) throw error;
            const payload = data as any;
            const items = Array.isArray(payload) ? payload : payload?.items || [];
            setTree(buildTree(items));
            if (payload?.truncated) {
                pushToast({
                    tone: "info",
                    title: "Large repository tree truncated by GitHub",
                    description: "The API returned a partial tree. Clone locally for the full repository view.",
                });
            }
        } catch (error: any) {
            console.error(error);
            setTree([]);
            pushToast({
                tone: "error",
                title: "Could not load repository tree",
                description: error.message,
            });
        } finally {
            setLoadingTree(false);
        }
    }, [pushToast]);

    const handleFileSelect = useCallback(async (path: string) => {
        if (!selectedRepo) return;
        setSelectedFile(path);
        setLoadingFile(true);

        try {
            const [owner, name] = selectedRepo.full_name.split("/");
            const { data, error } = await apiClient.GET("/github/file/{owner}/{repo}/{path}", {
                params: {
                    path: { owner, repo: name, path },
                    query: { branch: selectedRepo.default_branch },
                },
            });
            if (error) throw error;
            setFileContent((data as any)?.content || "");
        } catch (error: any) {
            setFileContent(`Error loading file: ${error.message}`);
            pushToast({
                tone: "error",
                title: "Could not load file",
                description: error.message,
            });
        } finally {
            setLoadingFile(false);
        }
    }, [pushToast, selectedRepo]);

    const handleTreeToggle = useCallback((path: string) => {
        setTree((current) => toggleNode(current, path));
    }, []);

    const startRun = async () => {
        if (!selectedRepo || !runPrompt.trim()) return;
        setIsStartingRun(true);
        setRunLogs(["Initializing run..."]);
        if (logFlushTimerRef.current !== null) {
            window.clearTimeout(logFlushTimerRef.current);
            logFlushTimerRef.current = null;
        }
        logBufferRef.current = [];
        stickToBottomRef.current = true;

        try {
            const { data, error } = await apiClient.POST("/hub", {
                body: {
                    repo_url: selectedRepo.clone_url || selectedRepo.html_url,
                    prompt: runPrompt.trim(),
                },
            });
            if (error) throw error;

            const runId = (data as any)?.id;
            if (runId) {
                setActiveRunId(runId);
                listenToLogs(runId);
                pushToast({
                    tone: "success",
                    title: "Hub run started",
                    description: `Streaming logs for ${selectedRepo.full_name}.`,
                });
            }
        } catch (error: any) {
            pushToast({
                tone: "error",
                title: "Could not start Hub run",
                description: error.message,
            });
            setRunLogs([`Failed to start run: ${error.message}`]);
        } finally {
            setIsStartingRun(false);
        }
    };

    const cancelRun = async () => {
        if (!activeRunId) return;
        setIsCancellingRun(true);
        try {
            const { error } = await apiClient.POST("/hub/{run_id}/cancel", {
                params: { path: { run_id: activeRunId } },
            });
            if (error) throw error;
            flushRunLogs(true);
            setRunLogs((current) => [...current, "[Run Cancelled]"]);
            setActiveRunId(null);
            eventSourceRef.current?.close();
            eventSourceRef.current = null;
            pushToast({
                tone: "info",
                title: "Hub run cancelled",
                description: "The runner received the cancellation request.",
            });
        } catch (error: any) {
            pushToast({
                tone: "error",
                title: "Could not cancel Hub run",
                description: error.message,
            });
        } finally {
            setIsCancellingRun(false);
        }
    };

    const filteredRepos = useMemo(
        () => repos.filter((repo) => repo.name.toLowerCase().includes(deferredRepoSearch.toLowerCase())),
        [deferredRepoSearch, repos]
    );
    const fileLines = useMemo(() => (fileContent === null ? [] : fileContent.split("\n")), [fileContent]);

    if (loading) {
        return (
            <div className="flex h-64 items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-[var(--accent)]" />
            </div>
        );
    }

    if (!connected) {
        return (
            <div className="mx-auto max-w-2xl">
                <div className="hero-panel p-8 text-center sm:p-10">
                    <p className="eyebrow">GitHub connection</p>
                    <h1 className="mt-4 text-3xl font-semibold tracking-[-0.04em] text-slate-950 sm:text-4xl">
                        Connect GitHub to unlock repo-aware runs.
                    </h1>
                    <p className="mx-auto mt-4 max-w-xl copy-lg">
                        Browse repositories, inspect files, queue agent runs, and watch logs stream without leaving the workspace.
                    </p>
                    <button type="button" onClick={handleConnect} className="btn-primary mt-8" data-testid="hub-connect">
                        <Github className="h-4 w-4" />
                        Connect with GitHub
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="page-stack">
            <section className="hero-panel p-6 sm:p-8">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                    <div>
                        <p className="eyebrow">Hub</p>
                        <h1 className="mt-3 text-3xl font-semibold tracking-[-0.04em] text-slate-950 sm:text-4xl">
                            Repo browsing, task setup, and live run logs in one surface.
                        </h1>
                        <p className="mt-3 copy-lg">
                            Connected as <span className="font-medium text-slate-950">@{ghUsername}</span>.
                        </p>
                    </div>
                    <div className="flex gap-3">
                        <button type="button" onClick={loadRepos} className="btn-secondary">
                            <RefreshCw className="h-4 w-4" />
                            Refresh repositories
                        </button>
                        <button type="button" onClick={handleDisconnect} className="btn-secondary" data-testid="hub-disconnect">
                            <Github className="h-4 w-4" />
                            Disconnect GitHub
                        </button>
                    </div>
                </div>
            </section>

            <section className="grid gap-6 xl:grid-cols-[300px_1fr_340px]">
                <div className="panel flex min-h-[62vh] flex-col p-4">
                    <div className="flex items-center gap-2 rounded-2xl border border-[var(--border)] bg-white/75 px-3 py-2">
                        <Search className="h-4 w-4 text-[var(--text-soft)]" />
                        <input
                            data-testid="hub-repo-search"
                            value={repoSearch}
                            onChange={(event) => setRepoSearch(event.target.value)}
                            placeholder="Search repositories..."
                            className="w-full bg-transparent text-sm text-slate-900 outline-none placeholder:text-[var(--text-soft)]"
                        />
                    </div>
                    <div className="mt-4 flex-1 space-y-2 overflow-y-auto pr-1">
                        {filteredRepos.map((repo) => (
                            <button
                                key={repo.id}
                                type="button"
                                onClick={() => selectRepo(repo)}
                                className={`w-full rounded-[24px] px-4 py-4 text-left transition ${
                                    selectedRepo?.id === repo.id
                                        ? "bg-slate-950 text-white shadow-[0_14px_28px_rgba(15,23,42,0.18)]"
                                        : "panel-muted hover:bg-white/80"
                                }`}
                            >
                                <div className="flex items-center gap-2">
                                    {repo.private ? (
                                        <Lock className={`h-4 w-4 ${selectedRepo?.id === repo.id ? "text-amber-300" : "text-[var(--amber)]"}`} />
                                    ) : (
                                        <Globe className={`h-4 w-4 ${selectedRepo?.id === repo.id ? "text-slate-300" : "text-[var(--text-soft)]"}`} />
                                    )}
                                    <span className="truncate text-sm font-semibold">{repo.name}</span>
                                </div>
                                {repo.description && (
                                    <p className={`mt-2 line-clamp-2 text-sm ${selectedRepo?.id === repo.id ? "text-slate-300" : "text-[var(--text-muted)]"}`}>
                                        {repo.description}
                                    </p>
                                )}
                                <div className={`mt-3 flex flex-wrap items-center gap-3 text-[11px] ${selectedRepo?.id === repo.id ? "text-slate-400" : "text-[var(--text-soft)]"}`}>
                                    {repo.language && <span>{repo.language}</span>}
                                    {repo.stargazers_count > 0 && (
                                        <span className="inline-flex items-center gap-1">
                                            <Star className="h-3 w-3" /> {repo.stargazers_count}
                                        </span>
                                    )}
                                    <span>{new Date(repo.updated_at).toLocaleDateString()}</span>
                                </div>
                            </button>
                        ))}
                    </div>
                </div>

                <div className="panel flex min-h-[62vh] flex-col overflow-hidden">
                    {selectedRepo ? (
                        <>
                            <div className="border-b border-[color:var(--border)] px-5 py-4">
                                <div className="flex flex-wrap items-start justify-between gap-3">
                                    <div>
                                        <h2 className="text-xl font-semibold tracking-[-0.03em] text-slate-950">
                                            {selectedRepo.full_name}
                                        </h2>
                                        <div className="mt-2 flex items-center gap-3 text-sm text-[var(--text-muted)]">
                                            <span className="inline-flex items-center gap-1">
                                                <GitBranch className="h-4 w-4" /> {selectedRepo.default_branch}
                                            </span>
                                            {selectedRepo.language && <span>{selectedRepo.language}</span>}
                                        </div>
                                    </div>
                                    <a
                                        href={selectedRepo.html_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="btn-secondary"
                                    >
                                        View on GitHub <ExternalLink className="h-4 w-4" />
                                    </a>
                                </div>
                            </div>
                            <div className="grid min-h-0 flex-1 gap-0 lg:grid-cols-[280px_1fr]">
                                <div className="border-b border-[color:var(--border)] p-3 lg:border-b-0 lg:border-r">
                                    {loadingTree ? (
                                        <div className="flex h-32 items-center justify-center">
                                            <Loader2 className="h-5 w-5 animate-spin text-[var(--accent)]" />
                                        </div>
                                    ) : (
                                        <div className="max-h-[56vh] space-y-1 overflow-y-auto pr-1">
                                            {tree.map((node) => (
                                                <FileTreeNode
                                                    key={node.path}
                                                    node={node}
                                                    depth={0}
                                                    onSelect={handleFileSelect}
                                                    onToggle={handleTreeToggle}
                                                />
                                            ))}
                                        </div>
                                    )}
                                </div>
                                <div className="min-h-0 p-4">
                                    {selectedFile ? (
                                        <div className="terminal-shell h-full overflow-hidden">
                                            <div className="border-b border-white/10 px-4 py-3">
                                                <p className="mono text-xs uppercase tracking-[0.24em] text-slate-400">{selectedFile}</p>
                                            </div>
                                            <div className="max-h-[56vh] overflow-auto p-4">
                                                {loadingFile ? (
                                                    <div className="flex h-32 items-center justify-center">
                                                        <Loader2 className="h-5 w-5 animate-spin text-emerald-300" />
                                                    </div>
                                                ) : (
                                                    <pre className="mono whitespace-pre-wrap text-sm leading-6 text-slate-200">
                                                        {fileLines.map((line, index) => (
                                                            <div key={index} className="flex gap-4 hover:bg-white/5">
                                                                <span className="w-10 flex-shrink-0 text-right text-slate-500">{index + 1}</span>
                                                                <span className="flex-1">{line || " "}</span>
                                                            </div>
                                                        ))}
                                                    </pre>
                                                )}
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="flex h-full min-h-[300px] items-center justify-center rounded-[24px] border border-dashed border-[var(--border-strong)] bg-white/45 px-6 text-center">
                                            <div>
                                                <File className="mx-auto h-10 w-10 text-[var(--accent)]" />
                                                <h3 className="mt-4 text-lg font-semibold text-slate-950">Select a file to inspect it.</h3>
                                                <p className="mt-2 text-sm text-[var(--text-muted)]">
                                                    The file tree and code preview stay visible while you configure a run on the right.
                                                </p>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </>
                    ) : (
                        <div className="flex h-full min-h-[62vh] items-center justify-center px-6 text-center">
                            <div>
                                <Github className="mx-auto h-10 w-10 text-[var(--accent)]" />
                                <h2 className="mt-4 text-2xl font-semibold tracking-[-0.03em] text-slate-950">
                                    Choose a repository to begin.
                                </h2>
                                <p className="mt-2 text-sm text-[var(--text-muted)]">
                                    Pick a repo on the left to browse files, set an objective, and launch a Hub run.
                                </p>
                            </div>
                        </div>
                    )}
                </div>

                <div className="space-y-4">
                    <div className="panel p-5">
                        <p className="eyebrow">Run objective</p>
                        <textarea
                            value={runPrompt}
                            onChange={(event) => setRunPrompt(event.target.value)}
                            placeholder="Describe the goal, constraints, and what a successful PR should contain..."
                            className="textarea-field mt-3"
                        />
                        <div className="mt-4 flex gap-3">
                            <button
                                type="button"
                                onClick={startRun}
                                disabled={!selectedRepo || !runPrompt.trim() || isStartingRun || !!activeRunId}
                                className="btn-primary flex-1"
                            >
                                {isStartingRun ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                                Start run
                            </button>
                            <button
                                type="button"
                                onClick={cancelRun}
                                disabled={!activeRunId || isCancellingRun}
                                className="btn-secondary"
                            >
                                {isCancellingRun ? <Loader2 className="h-4 w-4 animate-spin" /> : <Square className="h-4 w-4" />}
                                Stop
                            </button>
                        </div>
                        <p className="mt-3 text-sm text-[var(--text-muted)]">
                            {selectedRepo
                                ? `Runs execute against ${selectedRepo.full_name}.`
                                : "Select a repository before starting a run."}
                        </p>
                    </div>

                    <div className="terminal-shell overflow-hidden">
                        <div className="border-b border-white/10 px-4 py-3">
                            <p className="mono text-xs uppercase tracking-[0.24em] text-slate-400">Live logs</p>
                        </div>
                        <div ref={logViewportRef} className="max-h-[420px] min-h-[320px] overflow-y-auto px-4 py-4">
                            {runLogs.length === 0 ? (
                                <p className="text-sm italic text-slate-500">
                                    No active run logs yet. Queue a run to stream output here.
                                </p>
                            ) : (
                                runLogs.map((log, index) => (
                                    <div key={`${log}-${index}`} className="mono whitespace-pre-wrap py-1 text-xs leading-6 text-emerald-300">
                                        {log}
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                </div>
            </section>
        </div>
    );
}
