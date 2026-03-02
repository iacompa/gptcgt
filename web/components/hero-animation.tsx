"use client";

import { useEffect, useState } from "react";

export function HeroAnimation() {
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
    }, []);

    if (!mounted) return <div className="h-[200px] sm:h-[300px] w-full" />; // Placeholder to prevent hydration mismatch

    return (
        <div className="relative w-full h-[200px] sm:h-[300px] flex items-center justify-center overflow-visible select-none">
            <style jsx>{`
                @keyframes cinematicSuck {
                    0% {
                        opacity: 0;
                        transform: translate(0, 0) scale(0.9);
                        filter: blur(10px);
                    }
                    15% {
                        opacity: 0.3;
                        transform: translate(0, 0) scale(1);
                        filter: blur(0px);
                    }
                    60% {
                        opacity: 0.3;
                        transform: translate(0, 0) scale(1);
                        filter: blur(0px);
                    }
                    85% {
                        opacity: 0.1;
                        transform: translate(calc(var(--targetX) * -1), calc(var(--targetY) * -1)) scale(0.3);
                        filter: blur(8px);
                    }
                    100% {
                        opacity: 0;
                        transform: translate(calc(var(--targetX) * -1), calc(var(--targetY) * -1)) scale(0);
                        filter: blur(20px);
                    }
                }

                @keyframes brandBreathe {
                    0%, 100% {
                        transform: scale(1);
                        filter: brightness(1) drop-shadow(0 0 0px rgba(255,255,255,0));
                    }
                    50% {
                        transform: scale(1.02);
                        filter: brightness(1.2) drop-shadow(0 0 20px rgba(255,255,255,0.15));
                    }
                }

                @keyframes glowPulse {
                    0%, 100% { opacity: 0.5; transform: scale(1); }
                    50% { opacity: 0.8; transform: scale(1.1); }
                }

                .suffix-item {
                    animation: cinematicSuck 3s cubic-bezier(0.8, 0, 0.2, 1) forwards;
                }

                .brand-logo {
                    transform-origin: center;
                    animation: brandBreathe 4s ease-in-out infinite;
                    animation-delay: 2.8s;
                }
                
                .core-letter {
                    position: relative;
                    z-index: 10;
                }
            `}</style>

            <svg viewBox="0 -50 1000 600" className="w-full max-w-4xl h-full overflow-visible">
                {/* Background glow that appears after animation */}
                <circle cx="500" cy="200" r="200" fill="url(#hero-glow)" className="opacity-0" style={{ animation: "glowPulse 4s ease-in-out infinite, fadeIn 1s forwards 2.8s" }} />

                <defs>
                    <radialGradient id="hero-glow" cx="50%" cy="50%" r="50%">
                        <stop offset="0%" stopColor="rgba(99, 102, 241, 0.15)" />
                        <stop offset="100%" stopColor="rgba(99, 102, 241, 0)" />
                    </radialGradient>

                    {/* Gradients for letters */}
                    <linearGradient id="gpt-grad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#34D399" />
                        <stop offset="100%" stopColor="#059669" />
                    </linearGradient>
                    <linearGradient id="claude-grad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#A78BFA" />
                        <stop offset="100%" stopColor="#7C3AED" />
                    </linearGradient>
                    <linearGradient id="gemini-grad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#60A5FA" />
                        <stop offset="100%" stopColor="#2563EB" />
                    </linearGradient>
                    <linearGradient id="team-grad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#FB923C" />
                        <stop offset="100%" stopColor="#EA580C" />
                    </linearGradient>
                </defs>

                <g className="brand-logo" style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 800 }}>

                    {/* G (ChatGPT & Grok) */}
                    <g transform="translate(300, 200)">
                        <text x="0" y="0" fontSize="120" fill="url(#gpt-grad)" textAnchor="middle" dominantBaseline="middle" className="core-letter">g</text>
                        {/* CHAT flowing right into G */}
                        <text x="-240" y="0" fontSize="80" fill="#34D399" textAnchor="middle" dominantBaseline="middle" className="suffix-item" style={{ "--targetX": "-240px", "--targetY": "0px" } as any}>c</text>
                        <text x="-160" y="0" fontSize="80" fill="#34D399" textAnchor="middle" dominantBaseline="middle" className="suffix-item" style={{ "--targetX": "-160px", "--targetY": "0px" } as any}>h</text>
                        <text x="-80" y="0" fontSize="80" fill="#34D399" textAnchor="middle" dominantBaseline="middle" className="suffix-item" style={{ "--targetX": "-80px", "--targetY": "0px" } as any}>a</text>

                        {/* ROK flowing up into G */}
                        <text x="0" y="80" fontSize="80" fill="#34D399" textAnchor="middle" dominantBaseline="middle" className="suffix-item" style={{ "--targetX": "0px", "--targetY": "80px" } as any}>r</text>
                        <text x="0" y="160" fontSize="80" fill="#34D399" textAnchor="middle" dominantBaseline="middle" className="suffix-item" style={{ "--targetX": "0px", "--targetY": "160px" } as any}>o</text>
                        <text x="0" y="240" fontSize="80" fill="#34D399" textAnchor="middle" dominantBaseline="middle" className="suffix-item" style={{ "--targetX": "0px", "--targetY": "240px" } as any}>k</text>
                    </g>

                    {/* P & T (ChatGPT continued) */}
                    <g transform="translate(380, 200)">
                        <text x="0" y="0" fontSize="120" fill="url(#gpt-grad)" textAnchor="middle" dominantBaseline="middle" className="core-letter">p</text>
                    </g>
                    <g transform="translate(460, 200)">
                        <text x="0" y="0" fontSize="120" fill="url(#gpt-grad)" textAnchor="middle" dominantBaseline="middle" className="core-letter">t</text>
                    </g>

                    {/* C (Claude) */}
                    <g transform="translate(540, 200)">
                        <text x="0" y="0" fontSize="120" fill="url(#claude-grad)" textAnchor="middle" dominantBaseline="middle" className="core-letter">c</text>
                        {/* LAUDE flowing up into C */}
                        <text x="0" y="80" fontSize="80" fill="#A78BFA" textAnchor="middle" dominantBaseline="middle" className="suffix-item" style={{ "--targetX": "0px", "--targetY": "80px" } as any}>l</text>
                        <text x="0" y="160" fontSize="80" fill="#A78BFA" textAnchor="middle" dominantBaseline="middle" className="suffix-item" style={{ "--targetX": "0px", "--targetY": "160px" } as any}>a</text>
                        <text x="0" y="240" fontSize="80" fill="#A78BFA" textAnchor="middle" dominantBaseline="middle" className="suffix-item" style={{ "--targetX": "0px", "--targetY": "240px" } as any}>u</text>
                        <text x="0" y="320" fontSize="80" fill="#A78BFA" textAnchor="middle" dominantBaseline="middle" className="suffix-item" style={{ "--targetX": "0px", "--targetY": "320px" } as any}>d</text>
                        <text x="0" y="400" fontSize="80" fill="#A78BFA" textAnchor="middle" dominantBaseline="middle" className="suffix-item" style={{ "--targetX": "0px", "--targetY": "400px" } as any}>e</text>
                    </g>

                    {/* G (Gemini) */}
                    <g transform="translate(620, 200)">
                        <text x="0" y="0" fontSize="120" fill="url(#gemini-grad)" textAnchor="middle" dominantBaseline="middle" className="core-letter">g</text>
                        {/* EMINI flowing up into G */}
                        <text x="0" y="80" fontSize="80" fill="#60A5FA" textAnchor="middle" dominantBaseline="middle" className="suffix-item" style={{ "--targetX": "0px", "--targetY": "80px" } as any}>e</text>
                        <text x="0" y="160" fontSize="80" fill="#60A5FA" textAnchor="middle" dominantBaseline="middle" className="suffix-item" style={{ "--targetX": "0px", "--targetY": "160px" } as any}>m</text>
                        <text x="0" y="240" fontSize="80" fill="#60A5FA" textAnchor="middle" dominantBaseline="middle" className="suffix-item" style={{ "--targetX": "0px", "--targetY": "240px" } as any}>i</text>
                        <text x="0" y="320" fontSize="80" fill="#60A5FA" textAnchor="middle" dominantBaseline="middle" className="suffix-item" style={{ "--targetX": "0px", "--targetY": "320px" } as any}>n</text>
                        <text x="0" y="400" fontSize="80" fill="#60A5FA" textAnchor="middle" dominantBaseline="middle" className="suffix-item" style={{ "--targetX": "0px", "--targetY": "400px" } as any}>i</text>
                    </g>

                    {/* T (Team) */}
                    <g transform="translate(700, 200)">
                        <text x="0" y="0" fontSize="120" fill="url(#team-grad)" textAnchor="middle" dominantBaseline="middle" className="core-letter">t</text>
                        {/* EAM flowing left into T */}
                        <text x="80" y="0" fontSize="80" fill="#FB923C" textAnchor="middle" dominantBaseline="middle" className="suffix-item" style={{ "--targetX": "80px", "--targetY": "0px" } as any}>e</text>
                        <text x="160" y="0" fontSize="80" fill="#FB923C" textAnchor="middle" dominantBaseline="middle" className="suffix-item" style={{ "--targetX": "160px", "--targetY": "0px" } as any}>a</text>
                        <text x="240" y="0" fontSize="80" fill="#FB923C" textAnchor="middle" dominantBaseline="middle" className="suffix-item" style={{ "--targetX": "240px", "--targetY": "0px" } as any}>m</text>

                        {/* ALK flowing up into T */}
                        <text x="0" y="80" fontSize="80" fill="#FB923C" textAnchor="middle" dominantBaseline="middle" className="suffix-item" style={{ "--targetX": "0px", "--targetY": "80px" } as any}>a</text>
                        <text x="0" y="160" fontSize="80" fill="#FB923C" textAnchor="middle" dominantBaseline="middle" className="suffix-item" style={{ "--targetX": "0px", "--targetY": "160px" } as any}>l</text>
                        <text x="0" y="240" fontSize="80" fill="#FB923C" textAnchor="middle" dominantBaseline="middle" className="suffix-item" style={{ "--targetX": "0px", "--targetY": "240px" } as any}>k</text>
                    </g>
                </g>
            </svg>
        </div>
    );
}
