"use client";

export function CreditMeter({
    remaining,
    total
}: {
    remaining: number;
    total: number;
}) {
    const percent = total > 0 ? ((total - remaining) / total) * 100 : 0;
    const isOverage = remaining < 0;
    let colorClass = "bg-indigo-500";

    if (isOverage) {
        colorClass = "bg-red-500";
    } else if (percent > 90) {
        colorClass = "bg-amber-500";
    }

    const displayPercent = isOverage ? 100 : Math.min(100, Math.max(0, percent));

    return (
        <div className="w-full">
            <div className="flex justify-between text-sm mb-2">
                <span className="text-gray-400">Monthly Usage</span>
                <span className={isOverage ? "text-red-400 font-bold" : "text-white"}>
                    {isOverage
                        ? `${Math.abs(remaining)} credits OVER limit`
                        : `${total - remaining} / ${total} credits used`
                    }
                </span>
            </div>
            <div className="h-2 w-full bg-gray-800 rounded-full overflow-hidden">
                <div
                    className={`h-full ${colorClass} transition-all duration-500 ease-out`}
                    style={{ width: `${displayPercent}%` }}
                />
            </div>
        </div>
    );
}
