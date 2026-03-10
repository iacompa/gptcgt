"use client";

import { ReactNode } from "react";
import { ToastProvider } from "@/components/toaster";

export function AppProviders({ children }: { children: ReactNode }) {
    return <ToastProvider>{children}</ToastProvider>;
}
