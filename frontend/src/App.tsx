export default function App() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-6 py-4">
        <h1 className="text-xl font-semibold tracking-tight">TraceIQ</h1>
        <p className="text-sm text-slate-400">Autonomous Data Analyst</p>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-16">
        <h2 className="mb-2 text-2xl font-medium">Ask a business question</h2>
        <p className="mb-6 text-slate-400">
          Investigation, evidence, and reports land in later phases.
        </p>

        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            type="text"
            disabled
            placeholder="Why did conversion decline in Q3?"
            className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-4 py-3 text-slate-300 placeholder:text-slate-600 disabled:cursor-not-allowed"
          />
          <button
            type="button"
            disabled
            className="rounded-lg bg-indigo-600 px-5 py-3 font-medium text-white opacity-50 disabled:cursor-not-allowed"
          >
            Investigate
          </button>
        </div>

        <p className="mt-8 text-sm text-emerald-400">
          Phase 0 — infrastructure ready.
        </p>
      </main>
    </div>
  );
}
