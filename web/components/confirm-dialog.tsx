"use client";

import { AlertTriangle, X } from "lucide-react";

interface ConfirmDialogProps {
    open: boolean;
    title: string;
    description: string;
    confirmLabel: string;
    cancelLabel?: string;
    tone?: "danger" | "neutral";
    busy?: boolean;
    onCancel: () => void;
    onConfirm: () => void;
}

export function ConfirmDialog({
    open,
    title,
    description,
    confirmLabel,
    cancelLabel = "Cancel",
    tone = "danger",
    busy = false,
    onCancel,
    onConfirm,
}: ConfirmDialogProps) {
    if (!open) {
        return null;
    }

    return (
        <div className="fixed inset-0 z-[90] flex items-center justify-center bg-slate-950/45 px-4 backdrop-blur-sm">
            <div className="panel w-full max-w-md p-6">
                <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3">
                        <div
                            className={`mt-0.5 rounded-2xl p-2 ${
                                tone === "danger"
                                    ? "bg-red-100 text-red-700"
                                    : "bg-teal-100 text-teal-700"
                            }`}
                        >
                            <AlertTriangle className="h-5 w-5" />
                        </div>
                        <div>
                            <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
                            <p className="mt-2 text-sm leading-6 text-slate-600">{description}</p>
                        </div>
                    </div>
                    <button
                        type="button"
                        onClick={onCancel}
                        className="rounded-full p-1 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900"
                        aria-label="Close dialog"
                    >
                        <X className="h-4 w-4" />
                    </button>
                </div>
                <div className="mt-6 flex justify-end gap-3">
                    <button type="button" onClick={onCancel} className="btn-secondary">
                        {cancelLabel}
                    </button>
                    <button
                        type="button"
                        onClick={onConfirm}
                        disabled={busy}
                        className={tone === "danger" ? "btn-danger" : "btn-primary"}
                    >
                        {busy ? "Working..." : confirmLabel}
                    </button>
                </div>
            </div>
        </div>
    );
}
