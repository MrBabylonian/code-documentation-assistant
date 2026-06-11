import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Codedoc — Code Documentation Assistant",
  description: "Ask questions about any public GitHub repository, with cited answers.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-slate-950 text-slate-200 antialiased">
        <header className="border-b border-slate-800 px-6 py-4">
          <span className="font-mono text-lg font-semibold tracking-tight text-teal-400">
            codedoc
          </span>
          <span className="ml-3 text-sm text-slate-500">
            cited answers about any public GitHub repository
          </span>
        </header>
        <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
