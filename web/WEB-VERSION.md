# Vendor Tap List — live web version

This folder is the **live web version** of Vendor Tap List, built in Lovable
and deployed at https://vendor-tap-list.lovable.app/ (admin at /admin).

It is a separate build from the Python booth version at the repo root
(`server.py`, `index.html`, `admin.html` — runs on a laptop at the booth,
SQLite + spreadsheet sync). Do not mix the two: check-ins on the web
version save to Lovable's Supabase database and do NOT appear in the
booth spreadsheet, and vice versa.

Same 5 fields, same 14 expertise options, same duplicate rule
(same name + company + contact, case-insensitive, is blocked).

Setup: `npm install` then `npm run dev`. Supabase keys are NOT in this
folder — they live in Lovable. Copy the Supabase values from Lovable
if you run it locally.
