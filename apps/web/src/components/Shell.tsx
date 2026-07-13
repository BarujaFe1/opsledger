"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import { readRememberedBatchId } from "@/lib/routing";

export function SiteHeader() {
  const [lastBatchId, setLastBatchId] = useState<number | null>(null);

  useEffect(() => {
    setLastBatchId(readRememberedBatchId());
  }, []);

  return (
    <header className="border-b border-ink-200/80 bg-white/70 backdrop-blur-md sticky top-0 z-40">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4">
        <Link href="/" className="group flex items-baseline gap-2" aria-label="OpsLedger — início">
          <span className="font-display text-2xl font-bold tracking-tight text-ink-900">
            OpsLedger
          </span>
          <span className="text-xs font-medium uppercase tracking-[0.18em] text-accent">
            reconciliação
          </span>
        </Link>
        <nav className="flex items-center gap-5 text-sm text-ink-600" aria-label="Principal">
          <Link href="/wizard" className="hover:text-ink-900 transition-colors">
            Importar
          </Link>
          <Link href="/wizard?mode=demo" className="hidden sm:inline hover:text-ink-900 transition-colors">
            Demo
          </Link>
          {lastBatchId ? (
            <Link
              href={`/batches/${lastBatchId}`}
              className="hidden sm:inline rounded-full border border-ink-200 bg-white px-3 py-1 text-xs font-semibold text-ink-800 hover:border-accent"
            >
              Último batch #{lastBatchId}
            </Link>
          ) : null}
        </nav>
      </div>
    </header>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-hero-wash bg-grid-faint bg-[size:28px_28px]">
      <a
        href="#conteudo"
        className="sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:block focus:h-auto focus:w-auto focus:overflow-visible focus:rounded-md focus:bg-white focus:px-3 focus:py-2 focus:text-sm focus:shadow"
      >
        Ir para o conteúdo
      </a>
      <SiteHeader />
      <main id="conteudo">{children}</main>
      <footer className="border-t border-ink-200/70 mt-16">
        <div className="mx-auto max-w-6xl px-5 py-8 text-sm text-ink-500 flex flex-col sm:flex-row gap-2 sm:items-center sm:justify-between">
          <p>OpsLedger — fechamento operacional para e-commerces pequenos.</p>
          <p className="font-mono text-xs">MVP demo · SQLite · sem autenticação</p>
        </div>
      </footer>
    </div>
  );
}
