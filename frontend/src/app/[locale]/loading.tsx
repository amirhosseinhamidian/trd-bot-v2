export default function Loading() {
  return (
    <div className="animate-pulse space-y-8" aria-busy="true" aria-label="Loading">
      <section className="space-y-4">
        <div className="h-3 w-40 rounded-full bg-slate-800" />
        <div className="h-10 w-72 max-w-full rounded-xl bg-slate-800" />
        <div className="h-4 w-full max-w-2xl rounded-full bg-slate-900" />
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="h-32 rounded-2xl border border-slate-800 bg-slate-900/60" />
        ))}
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.35fr_1fr]">
        <div className="h-80 rounded-2xl border border-slate-800 bg-slate-900/60" />
        <div className="h-80 rounded-2xl border border-slate-800 bg-slate-900/60" />
      </section>

      <section className="h-80 rounded-2xl border border-slate-800 bg-slate-900/60" />
    </div>
  );
}
