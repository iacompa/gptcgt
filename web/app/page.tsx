import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { HeroAnimation } from "@/components/hero-animation";

export default function Home() {
    return (
        <div className="relative isolate px-6 pt-14 lg:px-8 max-w-7xl mx-auto">
            <div className="absolute inset-x-0 -top-40 -z-10 transform-gpu overflow-hidden blur-3xl sm:-top-80">
                <div className="relative left-[calc(50%-11rem)] aspect-[1155/678] w-[36.125rem] -translate-x-1/2 rotate-[30deg] bg-gradient-to-tr from-[#ff80b5] to-[#9089fc] opacity-20 sm:left-[calc(50%-30rem)] sm:w-[72.1875rem]" />
            </div>

            <div className="mx-auto max-w-4xl py-24 sm:py-32 lg:py-40 text-center">
                <HeroAnimation />
                <h1 className="mt-8 text-5xl font-extrabold tracking-tight sm:text-6xl bg-clip-text text-transparent bg-gradient-to-r from-gray-100 to-gray-400 pb-2">
                    Run multiple AIs on your code.
                </h1>
                <p className="mt-6 text-xl leading-8 text-gray-400">
                    Pick the best solution with proof. Shows you exactly what it costs.
                </p>
                <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-6">
                    <Link
                        href="/dashboard"
                        className="rounded-md bg-indigo-600 px-6 py-3 text-lg font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 flex items-center gap-2 transition-all"
                    >
                        Go to Dashboard <ArrowRight size={20} />
                    </Link>
                    <div className="px-6 py-3 rounded-md bg-black/40 border border-gray-700 font-mono text-gray-300 flex items-center gap-2">
                        <span className="text-gray-500">$</span> pip install <span className="flex"><span className="text-emerald-400">gpt</span><span className="text-orange-400">c</span><span className="text-blue-400">g</span><span className="text-purple-400">t</span></span>
                    </div>
                </div>
            </div>
        </div>
    );
}
