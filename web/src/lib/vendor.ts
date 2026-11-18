export const EXPERTISE = [
  "HVAC","Electrical","Plumbing","Fire & Life Safety","Building Automation & Controls",
  "Elevators & Lifts","Power & Generators","Water Treatment","Equipment & Tools",
  "Software & IoT","Roofing & Building Envelope","Janitorial & Grounds","Security Systems","Other",
] as const;

export const BRAND = {
  name: "Acid Solution",
  title: "Facilities Maintenance Operations",
  phone: "+10000000000",
  email: "you@example.com",
};

export type Checkin = {
  id: string; full_name: string; company: string; contact: string;
  on_display: string; expertise: string; created_at: string;
};

const norm = (s: string) => s.trim().toLowerCase();
export const dedupeKey = (c: { full_name: string; company: string; contact: string }) =>
  [norm(c.full_name), norm(c.company), norm(c.contact)].join("|");

export function groupByCompany(rows: Checkin[]) {
  const map = new Map<string, { company: string; rows: Checkin[] }>();
  for (const r of rows) {
    const k = norm(r.company);
    if (!map.has(k)) map.set(k, { company: r.company.trim(), rows: [] });
    map.get(k)!.rows.push(r);
  }
  return [...map.values()].sort((a, b) => a.company.localeCompare(b.company, undefined, { sensitivity: "base" }));
}

export function matchesSearch(r: Checkin, q: string) {
  if (!q.trim()) return true;
  const n = norm(q);
  return [r.full_name, r.company, r.contact, r.on_display, r.expertise, new Date(r.created_at).toLocaleString()]
    .some((v) => v.toLowerCase().includes(n));
}

const esc = (v: string) => `"${v.replace(/"/g, '""')}"`;
export function toCsv(rows: Checkin[]) {
  const head = ["Checked in", "Full name", "Company", "Phone or email", "On display", "Expertise"];
  const body = rows.map((r) => [r.created_at, r.full_name, r.company, r.contact, r.on_display, r.expertise].map(esc).join(","));
  return [head.map(esc).join(","), ...body].join("\r\n");
}

export function vcard() {
  return ["BEGIN:VCARD","VERSION:3.0",`FN:${BRAND.name}`,`ORG:${BRAND.name}`,`TITLE:${BRAND.title}`,
    `TEL;TYPE=WORK,VOICE:${BRAND.phone}`,`EMAIL;TYPE=WORK:${BRAND.email}`,"END:VCARD"].join("\r\n");
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30_000);
}
