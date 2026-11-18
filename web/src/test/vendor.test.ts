import { describe, expect, it } from "vitest";
import { dedupeKey, EXPERTISE, groupByCompany, type Checkin } from "@/lib/vendor";

const row = (p: Partial<Checkin>): Checkin => ({ id: "1", full_name: "A", company: "C", contact: "x", on_display: "d", expertise: "HVAC", created_at: "2026-01-01", ...p });

describe("vendor rules", () => {
  it("has exactly 14 expertise options", () => expect(EXPERTISE).toHaveLength(14));
  it("same name+company+contact in any case is a duplicate", () =>
    expect(dedupeKey(row({ full_name: "Jo Smith", company: "Acme", contact: "JO@X.COM" })))
      .toBe(dedupeKey(row({ full_name: "jo smith ", company: "ACME", contact: "jo@x.com" }))));
  it("same company, different person is not a duplicate", () =>
    expect(dedupeKey(row({ full_name: "Jo", company: "Acme" }))).not.toBe(dedupeKey(row({ full_name: "Sam", company: "Acme" }))));
  it("groups by company A-Z with counts", () => {
    const g = groupByCompany([row({ company: "zeta" }), row({ company: "Acme" }), row({ company: "acme" })]);
    expect(g.map((x) => [x.company, x.rows.length])).toEqual([["Acme", 2], ["zeta", 1]]);
  });
});
