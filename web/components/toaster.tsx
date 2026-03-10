"use client";

import {
    createContext,
    ReactNode,
    useCallback,
    useContext,
    useMemo,
    useRef,
    useState,
} from "react";
import { CheckCircle2, AlertTriangle, Info, X } from "lucide-react";

type ToastTone = "success" | "error" | "info";

interface ToastItem {
    id: number;
    title: string;
    description?: string;
    tone: ToastTone;
}

interface ToastContextValue {
    pushToast: (toast: Omit<ToastItem, "id">) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

function toneIcon(tone: ToastTone) {
    switch (tone) {
        case "success":
            return <CheckCircle2 className="h-4 w-4" />;
        case "error":
            return <AlertTriangle className="h-4 w-4" />;
        default:
            return <Info className="h-4 w-4" />;
    }
}

export function ToastProvider({ children }: { children: ReactNode }) {
    const [toasts, setToasts] = useState<ToastItem[]>([]);
    const nextId = useRef(1);

    const dismissToast = useCallback((id: number) => {
        setToasts((current) => current.filter((toast) => toast.id !== id));
    }, []);

    const pushToast = useCallback(
        (toast: Omit<ToastItem, "id">) => {
            const id = nextId.current++;
            setToasts((current) => [...current, { ...toast, id }]);
            window.setTimeout(() => dismissToast(id), 4200);
        },
        [dismissToast]
    );

    const value = useMemo(() => ({ pushToast }), [pushToast]);

    return (
        <ToastContext.Provider value={value}>
            {children}
            <div className="pointer-events-none fixed inset-x-0 top-4 z-[100] flex justify-center px-4">
                <div className="flex w-full max-w-xl flex-col gap-3">
                    {toasts.map((toast) => (
                        <div
                            key={toast.id}
                            className={`pointer-events-auto rounded-[22px] border px-4 py-3 shadow-[0_18px_40px_rgba(34,24,15,0.16)] backdrop-blur ${
                                toast.tone === "success"
                                    ? "border-emerald-300/70 bg-emerald-50 text-emerald-950"
                                    : toast.tone === "error"
                                      ? "border-red-300/70 bg-red-50 text-red-950"
                                      : "border-teal-300/70 bg-white/90 text-slate-900"
                            }`}
                        >
                            <div className="flex items-start gap-3">
                                <div className="mt-0.5">{toneIcon(toast.tone)}</div>
                                <div className="min-w-0 flex-1">
                                    <p className="text-sm font-semibold">{toast.title}</p>
                                    {toast.description && (
                                        <p className="mt-1 text-sm opacity-80">{toast.description}</p>
                                    )}
                                </div>
                                <button
                                    type="button"
                                    onClick={() => dismissToast(toast.id)}
                                    className="rounded-full p-1 opacity-60 transition hover:bg-black/5 hover:opacity-100"
                                    aria-label="Dismiss notification"
                                >
                                    <X className="h-4 w-4" />
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </ToastContext.Provider>
    );
}

export function useToast() {
    const context = useContext(ToastContext);
    if (!context) {
        throw new Error("useToast must be used within ToastProvider");
    }
    return context;
}
