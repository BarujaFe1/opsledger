import Link from "next/link";
import type { ReactNode } from "react";

export function SiteHeader() {
  return (
    <header className="border-b border-ink-200/80 bg-white/70 backdrop-blur-md sticky top-0 z-40">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4">
        <Link href="/" className="group flex items-baseline gap-2">
          <span className="font-display text-2xl font-bold tracking-tight text-ink-900">
            OpsLedger
          </span>
          <span className="text-xs font-medium uppercase tracking-[0.18em] text-accent">
            reconciliação
          </span>
        </Link>
        <nav className="flex items-center gap-5 text-sm text-ink-600">
          <Link href="/wizard" className="hover:text-ink-900 transition-colors">
            Importar
          </Link>
          <Link href="/wizard?mode=demo" className="hidden sm:inline hover:text-ink-900 transition-colors">
            Demo
          </Link>
        </nav>
      </div>
    </header>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-hero-wash bg-grid-faint bg-[size:28px_28px]">
      <SiteHeader />
      <main>{children}</main>
      <footer className="border-t border-ink-200/70 mt-16">
        <div className="mx-auto max-w-6xl px-5 py-8 text-sm text-ink-500 flex flex-col sm:flex-row gap-2 sm:items-center sm:justify-between">
          <p>OpsLedger — fechamento operacional para e-commerces pequenos.</p>
          <p className="font-mono text-xs">MVP local · SQLite · sem autenticação</p>
        </div>
      </footer>
    </div>
  );
}
