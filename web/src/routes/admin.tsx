import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { Download, Search } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { AppHeader } from "@/components/AppHeader";
import { EXPERTISE, downloadBlob, groupByCompany, matchesSearch, toCsv, type Checkin } from "@/lib/vendor";

export const Route = createFileRoute("/admin")({
  head: () => ({
    meta: [
      { title: "Vendor List — Acid Solution Admin" },
      { name: "description", content: "Checked-in vendors grouped by company, with search, filter and CSV export." },
      { property: "og:title", content: "Vendor List — Acid Solution Admin" },
      { property: "og:description", content: "Checked-in vendors grouped by company, with search, filter and CSV export." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: AdminPage,
});

function AdminPage() {
  const [rows, setRows] = useState<Checkin[] | null>(null);
  const [q, setQ] = useState("");
  const [exp, setExp] = useState("");

  useEffect(() => {
    supabase.from("vendor_checkins").select("*").order("created_at", { ascending: false }).limit(5000)
      .then(({ data }) => setRows(data ?? []));
  }, []);

  const filtered = useMemo(() => (rows ?? []).filter((r) => (!exp || r.expertise === exp) && matchesSearch(r, q)), [rows, q, exp]);
  const groups = useMemo(() => groupByCompany(filtered), [filtered]);
  const exportCsv = (list: Checkin[], name: string) =>
    downloadBlob(new Blob(["\uFEFF" + toCsv(list)], { type: "text/csv;charset=utf-8" }), name);

  return (
    <div className="min-h-screen bg-background">
      <AppHeader subtitle="Admin · Vendor List" />
      <main className="mx-auto max-w-3xl px-5 pb-16 pt-8">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="font-display text-3xl tracking-tight">Vendors</h1>
            <p className="mt-1 text-muted-foreground">{rows ? `${filtered.length} of ${rows.length} check-ins · ${groups.length} companies` : "Loading…"}</p>
          </div>
          <div className="flex gap-2">
            <button onClick={() => exportCsv(groups.flatMap((g) => g.rows), "vendors-filtered.csv")} className="flex h-11 items-center gap-2 rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground"><Download className="h-4 w-4" />Export filtered</button>
            <button onClick={() => exportCsv(groupByCompany(rows ?? []).flatMap((g) => g.rows), "vendors-all.csv")} className="flex h-11 items-center gap-2 rounded-lg border border-input bg-card px-4 text-sm font-semibold"><Download className="h-4 w-4" />Export all</button>
          </div>
        </div>
        <div className="mt-6 grid gap-3 sm:grid-cols-[1fr_16rem]">
          <label className="relative">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
            <input className="field pl-12" placeholder="Search name, company, contact…" value={q} onChange={(e) => setQ(e.target.value)} />
          </label>
          <select className="field" value={exp} onChange={(e) => setExp(e.target.value)}>
            <option value="">All expertise</option>
            {EXPERTISE.map((x) => <option key={x}>{x}</option>)}
          </select>
        </div>
        <div className="mt-8 space-y-5">
          {rows && groups.length === 0 && <p className="rounded-xl border border-dashed p-8 text-center text-muted-foreground">No vendors match.</p>}
          {groups.map((g) => (
            <section key={g.company} className="overflow-hidden rounded-xl border bg-card">
              <header className="flex items-center justify-between bg-secondary px-4 py-3">
                <h2 className="font-semibold">{g.company}</h2>
                <span className="rounded-full bg-navy px-2.5 py-0.5 text-xs font-semibold text-navy-foreground">{g.rows.length}</span>
              </header>
              <ul className="divide-y">
                {g.rows.map((r) => (
                  <li key={r.id} className="px-4 py-3">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <p className="font-semibold">{r.full_name}</p>
                      <span className="rounded-md bg-accent px-2 py-0.5 text-xs font-medium text-accent-foreground">{r.expertise}</span>
                    </div>
                    <p className="text-sm text-muted-foreground">{r.contact}</p>
                    <p className="mt-1 text-sm">{r.on_display}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{new Date(r.created_at).toLocaleString()}</p>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </main>
    </div>
  );
}
