import Link from "next/link";

export function Footer() {
    const currentYear = new Date().getFullYear();
    return (
        <footer className="border-t border-gray-800 bg-gray-950/50 py-12 mt-auto">
            <div className="max-w-7xl mx-auto px-4 md:px-8 text-center text-gray-500 text-sm">
                <p>© {currentYear} IA Compa LLC, Portsmouth Ohio. All rights reserved.</p>
                <div className="mt-4 flex justify-center gap-6">
                    <Link href="/terms" className="hover:text-gray-300">Terms of Service</Link>
                    <Link href="/privacy" className="hover:text-gray-300">Privacy Policy</Link>
                    <Link href="/acceptable-use" className="hover:text-gray-300">Acceptable Use</Link>
                    <Link href="/support" className="hover:text-gray-300">Support</Link>
                </div>
            </div>
        </footer>
    );
}
