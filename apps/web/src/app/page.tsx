import Link from "next/link";

export default function HomePage() {
  return (
    <div className="mx-auto max-w-6xl px-5">
      <section className="relative min-h-[78vh] grid lg:grid-cols-[1.1fr_0.9fr] gap-10 items-center py-14 lg:py-20">
        <div className="animate-fade-up">
          <p className="font-display text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight text-ink-900 leading-[0.95]">
            OpsLedger
          </p>
          <h1 className="mt-6 max-w-xl text-xl sm:text-2xl text-ink-700 leading-snug">
            Pedidos, pagamentos e estoque em planilhas diferentes? Cruze, ache divergências e feche o dia com confiança.
          </h1>
          <p className="mt-4 max-w-lg text-ink-500">
            Ferramenta de reconciliação operacional para pequenos e-commerces — regras claras, impacto financeiro e próximo passo acionável.
          </p>
          <div className="mt-8 flex flex-wrap gap-3 animate-fade-up-delay">
            <Link
              href="/wizard?mode=demo"
              className="inline-flex items-center justify-center rounded-full bg-accent px-6 py-3 text-sm font-semibold text-white shadow-soft transition hover:bg-accent-soft"
            >
              Rodar demo
            </Link>
            <Link
              href="/wizard?mode=upload"
              className="inline-flex items-center justify-center rounded-full border border-ink-300 bg-white/80 px-6 py-3 text-sm font-semibold text-ink-800 transition hover:border-ink-500"
            >
              Importar meus CSVs
            </Link>
          </div>
        </div>

        <div className="relative animate-fade-up-delay-2">
          <div className="absolute -inset-6 rounded-[2rem] bg-gradient-to-br from-accent/15 via-transparent to-accent-warm/15 blur-2xl" />
          <div className="relative overflow-hidden rounded-[1.75rem] border border-ink-200 bg-ink-900 text-ink-50 shadow-soft">
            <div className="border-b border-white/10 px-5 py-3 flex items-center justify-between">
              <span className="font-mono text-xs tracking-wider text-accent-muted">FECHAMENTO · 30 DIAS</span>
              <span className="h-2 w-2 rounded-full bg-accent-soft animate-pulse-soft" />
            </div>
            <div className="p-5 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <Metric label="Conciliado" value="R$ 48.2k" />
                <Metric label="Em divergência" value="R$ 3.1k" warn />
                <Metric label="Issues" value="24" />
                <Metric label="Críticas" value="1" warn />
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-ink-300">Próxima melhor ação</p>
                <p className="mt-2 text-sm leading-relaxed text-ink-100">
                  Estoque negativo em SKU-MEI-09 — revisar contagem física ou baixa duplicada.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="pb-20 grid md:grid-cols-3 gap-8">
        {[
          {
            title: "Importa o caos",
            body: "Valida schema de pedidos, pagamentos e movimentações antes de qualquer cruzamento.",
          },
          {
            title: "Reconcilia com regras",
            body: "Sete regras testáveis cobrem pagamento ausente, órfão, valor, duplicidade, estoque e canal.",
          },
          {
            title: "Orienta a revisão",
            body: "Dashboard executivo, issues filtráveis, status, exportação CSV e relatório de fechamento.",
          },
        ].map((item) => (
          <div key={item.title} className="border-t border-ink-300 pt-5">
            <h2 className="font-display text-2xl text-ink-900">{item.title}</h2>
            <p className="mt-3 text-ink-600 leading-relaxed">{item.body}</p>
          </div>
        ))}
      </section>
    </div>
  );
}

function Metric({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-3">
      <p className="text-[11px] uppercase tracking-[0.14em] text-ink-300">{label}</p>
      <p className={`mt-1 font-display text-2xl ${warn ? "text-orange-300" : "text-white"}`}>{value}</p>
    </div>
  );
}
