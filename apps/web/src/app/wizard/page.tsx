import { Suspense } from "react";
import WizardPage from "./WizardClient";

export default function Page() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-4xl px-5 py-12 text-ink-500">Carregando wizard…</div>}>
      <WizardPage />
    </Suspense>
  );
}
