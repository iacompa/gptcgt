"use client";

import { useCallback, useEffect, useState } from "react";
import {
    Github,
    GitBranch,
    File,
    Folder,
    ChevronRight,
    ChevronDown,
    Star,
    Lock,
    Globe,
    Loader2,
    ExternalLink,
    RefreshCw,
} from "lucide-react";
import { fetchAPI } from "@/lib/api";

interface Repo {
    id: number;
    name: string;
    full_name: string;
    description: string | null;
    language: string | null;
    private: boolean;
    updated_at: string;
    html_url: string;
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

    // Sort: dirs first, then alpha
    items.sort((a, b) => {
        if (a.type !== b.type) return a.type === "tree" ? -1 : 1;
        return a.path.localeCompare(b.path);
    });

    for (const item of items) {
        const parts = item.path.split("/");
        const name = parts[parts.length - 1];
        const node: TreeNode = { ...item, name, children: [], expanded: false };
        map.set(item.path, node);

        if (parts.length === 1) {
            root.push(node);
        } else {
            const parentPath = parts.slice(0, -1).join("/");
            const parent = map.get(parentPath);
            if (parent) {
                parent.children.push(node);
            } else {
                root.push(node);
            }
        }
    }

    return root;
}

function FileTreeNode({
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
    const ext = node.name.split(".").pop()?.toLowerCase();

    const langColor: Record<string, string> = {
        py: "text-blue-400",
        ts: "text-blue-300",
        tsx: "text-blue-300",
        js: "text-yellow-400",
        jsx: "text-yellow-400",
        rs: "text-orange-400",
        go: "text-cyan-400",
        md: "text-gray-400",
        json: "text-green-400",
        yaml: "text-purple-400",
        yml: "text-purple-400",
        toml: "text-pink-400",
        css: "text-pink-300",
        html: "text-orange-300",
    };

    const color = isDir ? "text-indigo-400" : langColor[ext || ""] || "text-gray-400";

    return (
        <div>
            <button
                onClick={() => (isDir ? onToggle(node.path) : onSelect(node.path))}
                className="w-full flex items-center gap-1.5 py-1 px-2 text-sm hover:bg-gray-800/50 rounded transition-colors group"
                style={{ paddingLeft: `${depth * 16 + 8}px` }}
            >
                {isDir ? (
                    node.expanded ? (
                        <ChevronDown className="w-3.5 h-3.5 text-gray-500" />
                    ) : (
                        <ChevronRight className="w-3.5 h-3.5 text-gray-500" />
                    )
                ) : (
                    <span className="w-3.5" />
                )}
                {isDir ? (
                    <Folder className={`w-4 h-4 ${color}`} />
                ) : (
                    <File className={`w-4 h-4 ${color}`} />
                )}
                <span className="truncate text-gray-300 group-hover:text-white">
                    {node.name}
                </span>
                {!isDir && node.size > 0 && (
                    <span className="ml-auto text-[10px] text-gray-600">
                        {node.size > 1024
                            ? `${(node.size / 1024).toFixed(1)}KB`
                            : `${node.size}B`}
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
}

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

    const loadRepos = useCallback(async () => {
        try {
            const data = await fetchAPI("/github/repos");
            setRepos(data);
        } catch (err: any) {
            console.error("Failed to load repos:", err);
        }
    }, []);

    const checkGithubStatus = useCallback(async () => {
        try {
            const status = await fetchAPI("/github/status");
            setConnected(status.connected);
            setGhUsername(status.username || "");
            if (status.connected) {
                await loadRepos();
            }
        } catch {
            setConnected(false);
        } finally {
            setLoading(false);
        }
    }, [loadRepos]);

    useEffect(() => {
        checkGithubStatus();
    }, [checkGithubStatus]);

    const handleConnect = async () => {
        try {
            const data = await fetchAPI("/github/connect");
            if (data.auth_url) {
                window.location.href = data.auth_url;
            }
        } catch (err: any) {
            alert(err.message || "Failed to connect to GitHub");
        }
    };

    const selectRepo = async (repo: Repo) => {
        setSelectedRepo(repo);
        setFileContent(null);
        setSelectedFile(null);
        setLoadingTree(true);

        try {
            const [owner, name] = repo.full_name.split("/");
            const data = await fetchAPI(`/github/tree/${owner}/${name}?branch=${repo.default_branch}`);
            setTree(buildTree(data));
        } catch (err: any) {
            console.error("Failed to load tree:", err);
            setTree([]);
        } finally {
            setLoadingTree(false);
        }
    };

    const handleFileSelect = async (path: string) => {
        if (!selectedRepo) return;
        setSelectedFile(path);
        setLoadingFile(true);

        try {
            const [owner, name] = selectedRepo.full_name.split("/");
            const data = await fetchAPI(
                `/github/file/${owner}/${name}/${path}?branch=${selectedRepo.default_branch}`
            );
            setFileContent(data.content);
        } catch (err: any) {
            setFileContent(`Error loading file: ${err.message}`);
        } finally {
            setLoadingFile(false);
        }
    };

    const handleToggle = (path: string) => {
        setTree((prev) => toggleNode(prev, path));
    };

    const filteredRepos = repos.filter((r) =>
        r.name.toLowerCase().includes(repoSearch.toLowerCase())
    );

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
            </div>
        );
    }

    // Not connected — show connect dialog
    if (!connected) {
        return (
            <div className="max-w-lg mx-auto mt-16">
                <div className="bg-gray-900 border border-gray-800 rounded-2xl p-10 text-center">
                    <div className="w-16 h-16 rounded-2xl bg-gray-800 flex items-center justify-center mx-auto mb-6">
                        <Github className="w-8 h-8 text-white" />
                    </div>
                    <h1 className="text-2xl font-bold mb-2">Connect GitHub</h1>
                    <p className="text-gray-400 mb-8">
                        Link your GitHub account to browse repositories, view code, and run
                        gptcgt agents on your projects directly from the web.
                    </p>
                    <button
                        onClick={handleConnect}
                        className="bg-white text-gray-900 hover:bg-gray-200 px-6 py-3 rounded-lg font-bold flex items-center gap-2 mx-auto transition-colors"
                    >
                        <Github className="w-5 h-5" />
                        Connect with GitHub
                    </button>
                </div>
            </div>
        );
    }

    // Connected — show hub
    return (
        <div className="flex flex-col h-[calc(100vh-4rem)]">
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h1 className="text-2xl font-bold flex items-center gap-2">
                        <Github className="w-6 h-6" /> Hub
                    </h1>
                    <p className="text-gray-400 text-sm mt-1">
                        Connected as <span className="text-white font-medium">@{ghUsername}</span>
                    </p>
                </div>
                <button
                    onClick={loadRepos}
                    className="text-gray-500 hover:text-white transition-colors p-2"
                    title="Refresh repos"
                >
                    <RefreshCw className="w-4 h-4" />
                </button>
            </div>

            <div className="flex flex-1 gap-4 min-h-0">
                {/* Repo list / file tree sidebar */}
                <div className="w-72 flex-shrink-0 bg-gray-900 border border-gray-800 rounded-xl overflow-hidden flex flex-col">
                    {!selectedRepo ? (
                        <>
                            <div className="p-3 border-b border-gray-800">
                                <input
                                    type="text"
                                    value={repoSearch}
                                    onChange={(e) => setRepoSearch(e.target.value)}
                                    placeholder="Search repositories..."
                                    className="w-full bg-gray-950 border border-gray-700 rounded-md px-3 py-1.5 text-sm text-white placeholder:text-gray-500 focus:outline-none focus:border-indigo-500"
                                />
                            </div>
                            <div className="flex-1 overflow-y-auto">
                                {filteredRepos.map((repo) => (
                                    <button
                                        key={repo.id}
                                        onClick={() => selectRepo(repo)}
                                        className="w-full text-left px-4 py-3 hover:bg-gray-800/50 border-b border-gray-800/50 transition-colors"
                                    >
                                        <div className="flex items-center gap-2">
                                            {repo.private ? (
                                                <Lock className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
                                            ) : (
                                                <Globe className="w-3.5 h-3.5 text-gray-500 flex-shrink-0" />
                                            )}
                                            <span className="text-sm font-medium truncate">{repo.name}</span>
                                        </div>
                                        {repo.description && (
                                            <p className="text-xs text-gray-500 mt-1 line-clamp-1">
                                                {repo.description}
                                            </p>
                                        )}
                                        <div className="flex items-center gap-3 mt-1.5">
                                            {repo.language && (
                                                <span className="text-[10px] text-gray-500">{repo.language}</span>
                                            )}
                                            {repo.stargazers_count > 0 && (
                                                <span className="text-[10px] text-gray-500 flex items-center gap-0.5">
                                                    <Star className="w-2.5 h-2.5" /> {repo.stargazers_count}
                                                </span>
                                            )}
                                        </div>
                                    </button>
                                ))}
                            </div>
                        </>
                    ) : (
                        <>
                            <div className="p-3 border-b border-gray-800">
                                <button
                                    onClick={() => {
                                        setSelectedRepo(null);
                                        setTree([]);
                                        setFileContent(null);
                                        setSelectedFile(null);
                                    }}
                                    className="text-xs text-gray-500 hover:text-white transition-colors mb-2 flex items-center gap-1"
                                >
                                    ← All repos
                                </button>
                                <div className="flex items-center gap-2">
                                    <span className="text-sm font-bold truncate">{selectedRepo.name}</span>
                                    <a
                                        href={selectedRepo.html_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-gray-500 hover:text-white"
                                    >
                                        <ExternalLink className="w-3.5 h-3.5" />
                                    </a>
                                </div>
                                <div className="flex items-center gap-1 text-[10px] text-gray-500 mt-1">
                                    <GitBranch className="w-3 h-3" /> {selectedRepo.default_branch}
                                </div>
                            </div>
                            <div className="flex-1 overflow-y-auto py-1">
                                {loadingTree ? (
                                    <div className="flex items-center justify-center h-32">
                                        <Loader2 className="w-5 h-5 animate-spin text-gray-500" />
                                    </div>
                                ) : (
                                    tree.map((node) => (
                                        <FileTreeNode
                                            key={node.path}
                                            node={node}
                                            depth={0}
                                            onSelect={handleFileSelect}
                                            onToggle={handleToggle}
                                        />
                                    ))
                                )}
                            </div>
                        </>
                    )}
                </div>

                {/* Code viewer */}
                <div className="flex-1 bg-gray-900 border border-gray-800 rounded-xl overflow-hidden flex flex-col">
                    {selectedFile ? (
                        <>
                            <div className="px-4 py-2.5 border-b border-gray-800 flex items-center justify-between">
                                <span className="text-sm text-gray-300 font-mono">{selectedFile}</span>
                            </div>
                            <div className="flex-1 overflow-auto">
                                {loadingFile ? (
                                    <div className="flex items-center justify-center h-32">
                                        <Loader2 className="w-5 h-5 animate-spin text-gray-500" />
                                    </div>
                                ) : (
                                    <pre className="p-4 text-sm font-mono text-gray-300 whitespace-pre overflow-x-auto leading-relaxed">
                                        {fileContent?.split("\n").map((line, i) => (
                                            <div key={i} className="flex hover:bg-gray-800/30">
                                                <span className="w-12 flex-shrink-0 text-right text-gray-600 select-none pr-4">
                                                    {i + 1}
                                                </span>
                                                <span>{line || " "}</span>
                                            </div>
                                        ))}
                                    </pre>
                                )}
                            </div>
                        </>
                    ) : (
                        <div className="flex items-center justify-center h-full text-gray-600">
                            <div className="text-center">
                                <File className="w-12 h-12 mx-auto mb-3 text-gray-700" />
                                <p className="text-sm">
                                    {selectedRepo
                                        ? "Select a file from the tree"
                                        : "Select a repository to browse"}
                                </p>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

function toggleNode(nodes: TreeNode[], path: string): TreeNode[] {
    return nodes.map((n) => {
        if (n.path === path) {
            return { ...n, expanded: !n.expanded };
        }
        if (n.children.length > 0) {
            return { ...n, children: toggleNode(n.children, path) };
        }
        return n;
    });
}
