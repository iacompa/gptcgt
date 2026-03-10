"use client";

import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';

export function UsageChart({ data }: { data: any[] }) {
    if (!data || data.length === 0) {
        return <div className="flex h-64 items-center justify-center text-[var(--text-muted)]">No usage data available</div>;
    }

    return (
        <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(100, 90, 78, 0.18)" vertical={false} />
                    <XAxis
                        dataKey="date"
                        stroke="#857a6c"
                        fontSize={12}
                        tickLine={false}
                        axisLine={false}
                    />
                    <YAxis
                        stroke="#857a6c"
                        fontSize={12}
                        tickLine={false}
                        axisLine={false}
                        tickFormatter={(value) => `${value}`}
                    />
                    <Tooltip
                        cursor={{ fill: "rgba(15, 118, 110, 0.08)" }}
                        contentStyle={{
                            backgroundColor: "rgba(255, 252, 247, 0.96)",
                            borderColor: "rgba(77, 58, 38, 0.12)",
                            borderRadius: "1rem",
                            boxShadow: "0 14px 28px rgba(44, 30, 16, 0.1)",
                        }}
                        itemStyle={{ color: "#171412" }}
                    />
                    <Bar dataKey="credits" fill="#0f766e" radius={[8, 8, 0, 0]} />
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
}
