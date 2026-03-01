"use client";

import { Check, Shield, Database, Users, KeyRound } from "lucide-react";
import Link from "next/link";

export default function PricingPage() {
    return (
        <div className="py-24 sm:py-32 max-w-7xl mx-auto px-6 lg:px-8">
            <div className="mx-auto max-w-4xl text-center">
                <h2 className="text-base font-semibold leading-7 text-indigo-400">Pricing</h2>
                <p className="mt-2 text-4xl font-bold tracking-tight text-white sm:text-5xl">
                    Scale capabilities, not headcount
                </p>
                <p className="mt-4 text-lg text-gray-400">Use your own API keys for free, or subscribe for managed credits and zero-config access to every provider.</p>
            </div>

            <div className="isolate mx-auto mt-16 grid max-w-md grid-cols-1 gap-6 lg:max-w-7xl lg:grid-cols-4">
                {/* BYOK Free Tier */}
                <div className="rounded-3xl p-8 xl:p-10 ring-1 ring-emerald-500/30 bg-emerald-950/10 hover:bg-emerald-950/20 transition-colors flex flex-col justify-between">
                    <div>
                        <div className="flex items-center gap-2">
                            <KeyRound className="h-5 w-5 text-emerald-400" />
                            <h3 className="text-2xl font-bold text-white">BYOK</h3>
                        </div>
                        <p className="mt-4 text-sm leading-6 text-gray-400">Bring Your Own Keys. Use your own API keys from any provider — pay them directly.</p>
                        <p className="mt-6 flex items-baseline gap-x-1">
                            <span className="text-4xl font-bold tracking-tight text-emerald-400">Free</span>
                            <span className="text-sm font-semibold leading-6 text-gray-400">forever</span>
                        </p>
                        <ul className="mt-8 space-y-3 text-sm leading-6 text-gray-300">
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-emerald-400" /> All 6 Operation Modes</li>
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-emerald-400" /> Unlimited Usage</li>
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-emerald-400" /> 10+ Provider Support</li>
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-emerald-400" /> Local Model Support (Ollama)</li>
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-emerald-400" /> Secure OS Keychain Storage</li>
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-emerald-400" /> ELO Rankings &amp; Routing</li>
                        </ul>
                    </div>
                    <Link href="/docs/keys" className="mt-8 block rounded-md bg-emerald-500/10 px-3 py-2 text-center text-sm font-semibold leading-6 text-emerald-400 hover:bg-emerald-500/20 ring-1 ring-inset ring-emerald-500/20">
                        Get started — it&apos;s free
                    </Link>
                </div>

                {/* Pro Plan */}
                <div className="rounded-3xl p-8 xl:p-10 ring-1 ring-gray-800 bg-gray-900/40 hover:bg-gray-900 transition-colors flex flex-col justify-between">
                    <div>
                        <h3 className="text-2xl font-bold text-white">Pro</h3>
                        <p className="mt-4 text-sm leading-6 text-gray-400">Managed credits — zero config, one subscription for all providers.</p>
                        <p className="mt-6 flex items-baseline gap-x-1">
                            <span className="text-4xl font-bold tracking-tight text-white">$29</span>
                            <span className="text-sm font-semibold leading-6 text-gray-400">/month</span>
                        </p>
                        <ul className="mt-8 space-y-3 text-sm leading-6 text-gray-300">
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-indigo-400" /> 1,000 Credits Monthly</li>
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-indigo-400" /> Optional PAYG Overage</li>
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-indigo-400" /> No API Keys Needed</li>
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-indigo-400" /> Standard Support</li>
                        </ul>
                    </div>
                    <Link href="/auth" className="mt-8 block rounded-md bg-indigo-500/10 px-3 py-2 text-center text-sm font-semibold leading-6 text-indigo-400 hover:bg-indigo-500/20 ring-1 ring-inset ring-indigo-500/20">
                        Get started
                    </Link>
                </div>

                {/* Team Plan */}
                <div className="rounded-3xl p-8 xl:p-10 bg-gradient-to-b from-indigo-900/40 to-gray-900 ring-2 ring-indigo-500 shadow-2xl relative flex flex-col justify-between">
                    <div className="absolute top-0 right-6 transform -translate-y-1/2 rounded-full bg-indigo-500 px-3 py-1 text-xs font-semibold text-white">Most popular</div>
                    <div>
                        <h3 className="text-2xl font-bold text-white">Team</h3>
                        <p className="mt-4 text-sm leading-6 text-gray-400">For engineering teams shipping production features.</p>
                        <p className="mt-6 flex items-baseline gap-x-1">
                            <span className="text-4xl font-bold tracking-tight text-white">$49</span>
                            <span className="text-sm font-semibold leading-6 text-gray-400">/seat/month</span>
                        </p>
                        <ul className="mt-8 space-y-3 text-sm leading-6 text-gray-300">
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-indigo-400" /> 2,000 Credits Monthly</li>
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-indigo-400" /> Hard Spending Caps</li>
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-indigo-400" /> Shared Organization Keys</li>
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-indigo-400" /> Priority Support</li>
                        </ul>
                    </div>
                    <Link href="/auth" className="mt-8 block rounded-md bg-indigo-500 px-3 py-2 text-center text-sm font-semibold leading-6 text-white shadow-sm hover:bg-indigo-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2">
                        Start Team Trial
                    </Link>
                </div>

                {/* Enterprise Plan */}
                <div className="rounded-3xl p-8 xl:p-10 ring-1 ring-gray-800 bg-gray-900/40 hover:bg-gray-900 transition-colors flex flex-col justify-between">
                    <div>
                        <h3 className="text-2xl font-bold text-white">Enterprise</h3>
                        <p className="mt-4 text-sm leading-6 text-gray-400">Advanced security and compliance for large orgs.</p>
                        <p className="mt-6 flex items-baseline gap-x-1">
                            <span className="text-4xl font-bold tracking-tight text-white">$149</span>
                            <span className="text-sm font-semibold leading-6 text-gray-400">/seat/month</span>
                        </p>
                        <ul className="mt-8 space-y-3 text-sm leading-6 text-gray-300">
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-indigo-400" /> Custom Credit Volumes</li>
                            <li className="flex gap-x-3"><Shield className="h-6 w-5 flex-none text-indigo-400" /> SOC2 Compliance & Audit Logs</li>
                            <li className="flex gap-x-3"><Users className="h-6 w-5 flex-none text-indigo-400" /> SAML SSO via WorkOS</li>
                            <li className="flex gap-x-3"><Database className="h-6 w-5 flex-none text-indigo-400" /> Data Residency Guarantees</li>
                        </ul>
                    </div>
                    <Link href="mailto:sales@ia-compa.com" className="mt-8 block rounded-md bg-white/10 px-3 py-2 text-center text-sm font-semibold leading-6 text-white hover:bg-white/20">
                        Contact Sales
                    </Link>
                </div>
            </div>

            <div className="mt-24 pt-16 border-t border-gray-800 text-center max-w-4xl mx-auto">
                <h3 className="text-2xl font-bold mb-6">Pay-As-You-Go Credit Packs</h3>
                <p className="text-gray-400 mb-8">Need extra capacity this month? Purchase non-expiring proxy credits. 1 credit ≈ 1 Scout completion.</p>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div className="bg-gray-900 border border-gray-700 rounded-xl p-6">
                        <div className="text-xl font-bold text-white mb-1">100 Credits</div>
                        <div className="text-gray-400 bg-gray-800 rounded px-2 py-0.5 inline-block text-sm mb-4">$5.00</div>
                        <button className="w-full bg-gray-800 hover:bg-gray-700 text-white rounded py-2 text-sm font-medium transition">Buy Pack</button>
                    </div>
                    <div className="bg-gray-900 border border-indigo-500/50 rounded-xl p-6 relative">
                        <div className="absolute -top-3 left-1/2 transform -translate-x-1/2 bg-indigo-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-full uppercase">Value</div>
                        <div className="text-xl font-bold text-white mb-1">500 Credits</div>
                        <div className="text-gray-400 bg-gray-800 rounded px-2 py-0.5 inline-block text-sm mb-4">$20.00</div>
                        <button className="w-full bg-indigo-600 hover:bg-indigo-500 text-white rounded py-2 text-sm font-medium transition">Buy Pack</button>
                    </div>
                    <div className="bg-gray-900 border border-gray-700 rounded-xl p-6">
                        <div className="text-xl font-bold text-white mb-1">1,000 Credits</div>
                        <div className="text-gray-400 bg-gray-800 rounded px-2 py-0.5 inline-block text-sm mb-4">$35.00</div>
                        <button className="w-full bg-gray-800 hover:bg-gray-700 text-white rounded py-2 text-sm font-medium transition">Buy Pack</button>
                    </div>
                </div>
            </div>
        </div>
    );
}
