import { createFileRoute } from "@tanstack/react-router";
import { useState, type FormEvent, type ReactNode } from "react";
import { z } from "zod";
import { Mail, Phone, Download, CheckCircle2, AlertCircle } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { AppHeader } from "@/components/AppHeader";
import { BRAND, EXPERTISE, downloadBlob, vcard } from "@/lib/vendor";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Vendor Check-in — Acid Solution" },
      { name: "description", content: "Check in at the Acid Solution vendor tap list in under a minute." },
      { property: "og:title", content: "Vendor Check-in — Acid Solution" },
      { property: "og:description", content: "Check in at the Acid Solution vendor tap list in under a minute." },
    ],
  }),
  component: CheckinPage,
});

const schema = z.object({
  full_name: z.string().trim().min(1, "Enter your full name").max(120),
  company: z.string().trim().min(1, "Enter your company").max(160),
  contact: z.string().trim().min(3, "Enter a phone number or email").max(200),
  on_display: z.string().trim().min(1, "Tell us what you do or have on display").max(240),
  expertise: z.enum(EXPERTISE, { message: "Choose an area of expertise" }),
});
type Form = Record<keyof z.infer<typeof schema>, string>;
const empty: Form = { full_name: "", company: "", contact: "", on_display: "", expertise: "" };

function CheckinPage() {
  const [form, setForm] = useState<Form>(empty);
  const [errors, setErrors] = useState<Partial<Form>>({});
  const [status, setStatus] = useState<"idle" | "saving" | "done" | "duplicate" | "error">("idle");

  const set = (k: keyof Form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });

  async function submit(e: FormEvent) {
    e.preventDefault();
    const parsed = schema.safeParse(form);
    if (!parsed.success) {
      const errs: Partial<Form> = {};
      for (const i of parsed.error.issues) errs[i.path[0] as keyof Form] ??= i.message;
      setErrors(errs);
      return;
    }
    setErrors({});
    setStatus("saving");
    const { error } = await supabase.from("vendor_checkins").insert(parsed.data);
    if (!error) setStatus("done");
    else if (error.code === "23505") setStatus("duplicate");
    else setStatus("error");
  }

  return (
    <div className="min-h-screen bg-background">
      <AppHeader subtitle="Vendor Tap List" />
      <main className="mx-auto max-w-xl px-5 pb-16 pt-8">
        {status === "done" || status === "duplicate" ? (
          <Success duplicate={status === "duplicate"} onReset={() => { setForm(empty); setStatus("idle"); }} />
        ) : (
          <>
            <h1 className="font-display text-3xl tracking-tight">Vendor check-in</h1>
            <p className="mt-2 text-muted-foreground">All fields are required. Takes under a minute.</p>
            <form onSubmit={submit} noValidate className="mt-8 space-y-5">
              <Field label="Full name" error={errors.full_name}>
                <input className="field" autoComplete="name" value={form.full_name} onChange={set("full_name")} />
              </Field>
              <Field label="Company" error={errors.company}>
                <input className="field" autoComplete="organization" value={form.company} onChange={set("company")} />
              </Field>
              <Field label="Phone or email" error={errors.contact}>
                <input className="field" autoComplete="email" inputMode="email" value={form.contact} onChange={set("contact")} />
              </Field>
              <Field label="What do you do / what is on display today" error={errors.on_display}>
                <input className="field" maxLength={240} value={form.on_display} onChange={set("on_display")} />
              </Field>
              <Field label="Area of expertise" error={errors.expertise}>
                <select className="field" value={form.expertise} onChange={set("expertise")}>
                  <option value="" disabled>Select one…</option>
                  {EXPERTISE.map((x) => <option key={x}>{x}</option>)}
                </select>
              </Field>
              {status === "error" && (
                <p className="flex items-center gap-2 text-destructive"><AlertCircle className="h-4 w-4" />Couldn't save. Please try again.</p>
              )}
              <button type="submit" disabled={status === "saving"}
                className="h-14 w-full rounded-xl bg-primary text-lg font-semibold text-primary-foreground shadow-card transition active:scale-[0.99] disabled:opacity-60">
                {status === "saving" ? "Checking in…" : "Check in"}
              </button>
            </form>
          </>
        )}
      </main>
    </div>
  );
}

function Field({ label, error, children }: { label: string; error?: string | undefined; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-semibold">{label}</span>
      {children}
      {error && <span className="mt-1.5 block text-sm text-destructive">{error}</span>}
    </label>
  );
}

function Success({ duplicate, onReset }: { duplicate: boolean; onReset: () => void }) {
  return (
    <div>
      <div className="flex items-center gap-3">
        {duplicate ? <AlertCircle className="h-8 w-8 text-primary" /> : <CheckCircle2 className="h-8 w-8 text-success" />}
        <h1 className="font-display text-3xl tracking-tight">{duplicate ? "Already checked in" : "You're checked in"}</h1>
      </div>
      <p className="mt-2 text-muted-foreground">
        {duplicate ? "We already have you on today's list — no need to check in again." : "Thanks! Save our contact so you can reach us."}
      </p>
      <div className="mt-8 rounded-2xl bg-card-gradient p-6 text-navy-foreground shadow-card">
        <div className="flex items-center gap-3">
          <span className="grid h-12 w-12 place-items-center rounded-xl bg-primary font-display text-xl text-primary-foreground">A</span>
          <div>
            <p className="font-display text-xl">{BRAND.name}</p>
            <p className="text-sm text-navy-muted">{BRAND.title}</p>
          </div>
        </div>
        <div className="mt-6 grid grid-cols-2 gap-3">
          <a href={`tel:${BRAND.phone}`} className="flex h-14 items-center justify-center gap-2 rounded-xl bg-navy-foreground/10 font-semibold"><Phone className="h-5 w-5" />Call</a>
          <a href={`mailto:${BRAND.email}`} className="flex h-14 items-center justify-center gap-2 rounded-xl bg-navy-foreground/10 font-semibold"><Mail className="h-5 w-5" />Email</a>
          <button onClick={() => downloadBlob(new Blob([vcard()], { type: "text/vcard;charset=utf-8" }), "acid-solution.vcf")}
            className="col-span-2 flex h-14 items-center justify-center gap-2 rounded-xl bg-primary font-semibold text-primary-foreground">
            <Download className="h-5 w-5" />Save my contact
          </button>
        </div>
      </div>
      <button onClick={onReset} className="mt-6 w-full py-3 text-sm font-medium text-muted-foreground underline">Check in someone else</button>
    </div>
  );
}
