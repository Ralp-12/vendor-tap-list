#!/usr/bin/env python3
"""Vendor check-in in ONE app — local SQLite database + live spreadsheet sync.

Vendors scan the QR / tap NFC on Ralp's badge -> this page -> 5-field form ->
saved in a local SQLite database on the machine running this server, AND
appended immediately to the Vendor Tap List spreadsheet (.xlsx, see
SPREADSHEET_PATH below). The spreadsheet sync never blocks the vendor: the
check-in is saved locally first, the spreadsheet append runs in a
background thread, and a failed append is marked "pending" and retried
every 60 seconds.

The spreadsheet IS the vendor list — standalone, no Google Sheet. The old
Google Sheet / Apps Script sync (sheet-sync.gs, SHEET_WEBHOOK_URL) is
superseded and off by default; it is kept in the code only as a fallback
and is NOT used unless SHEET_WEBHOOK_URL is explicitly set.

Run:  python3 server.py            (serves on port 8000, all interfaces)
      PORT=9000 python3 server.py  (custom port)
      VENDORS_DB=/path/file.db python3 server.py  (custom database file)
      SPREADSHEET_PATH=/path/vendor-tap-list-spreadsheet.xlsx \
          python3 server.py        (custom spreadsheet; default is the
                                    goal's spreadsheet in ../files/)

Needs openpyxl (already installed in this VM: pip install openpyxl).
Python 3.8+.
"""
import csv
import io
import json
import os
import sqlite3
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
DB_PATH = os.environ.get("VENDORS_DB",
                         os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "vendors.db"))
# Apps Script Web app URL from sheet-sync.gs Deploy. Empty = no Google
# Sheet sync attempted. Kept only as a fallback; the spreadsheet below
# is the live list now.
SHEET_WEBHOOK_URL = os.environ.get("SHEET_WEBHOOK_URL", "").strip()
# The standalone Vendor Tap List spreadsheet. Default: the goal's
# spreadsheet in ../files/vendor-tap-list-spreadsheet/. On a deployed
# host (Render free plan) only the app/ folder is deployed, so fall back
# to the copy bundled next to server.py if the goal file is not there.
_here = os.path.dirname(os.path.abspath(__file__))
_default_goal = os.path.join(
    _here, "..", "files", "vendor-tap-list-spreadsheet",
    "vendor-tap-list-spreadsheet.xlsx")
_default_bundled = os.path.join(_here, "vendor-tap-list-spreadsheet.xlsx")
SPREADSHEET_PATH = os.environ.get("SPREADSHEET_PATH", "")
if not SPREADSHEET_PATH:
    SPREADSHEET_PATH = (_default_goal if os.path.isfile(_default_goal)
                        else _default_bundled)
SPREADSHEET_PATH = os.path.abspath(SPREADSHEET_PATH)
HERE = os.path.dirname(os.path.abspath(__file__))
WRITE_LOCK = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS vendors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    name TEXT NOT NULL,
    company TEXT NOT NULL,
    contact TEXT NOT NULL,
    what TEXT NOT NULL,
    expertise TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sheet_sync (
    vendor_id INTEGER PRIMARY KEY,
    status TEXT NOT NULL,  -- 'synced' | 'pending'
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    synced_at TEXT
);
CREATE TABLE IF NOT EXISTS spreadsheet_sync (
    vendor_id INTEGER PRIMARY KEY,
    status TEXT NOT NULL,  -- 'synced' | 'pending'
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    synced_at TEXT
)
"""


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def post_entry_to_sheet(entry):
    """POST one vendor entry to the Apps Script webhook. Returns (ok, error)."""
    if not SHEET_WEBHOOK_URL:
        return False, "no SHEET_WEBHOOK_URL configured"
    req = urllib.request.Request(
        SHEET_WEBHOOK_URL,
        data=json.dumps(entry).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", "replace")
        if resp.status == 200 and '"ok":true' in body.replace(" ", ""):
            return True, ""
        return False, f"sheet replied HTTP {resp.status}: {body[:200]}"
    except Exception as ex:
        return False, str(ex)[:200]


def sync_entry(vendor_id, entry):
    """Try the Sheet POST once, record the outcome. Never raises."""
    try:
        ok, err = post_entry_to_sheet(entry)
        now = datetime.now().isoformat(timespec="seconds")
        with WRITE_LOCK:
            conn = db()
            row = conn.execute(
                "SELECT attempts FROM sheet_sync WHERE vendor_id = ?",
                (vendor_id,)).fetchone()
            attempts = (row[0] + 1) if row else 1
            conn.execute(
                "INSERT INTO sheet_sync (vendor_id, status, attempts,"
                " last_error, synced_at) VALUES (?,?,?,?,?)"
                " ON CONFLICT(vendor_id) DO UPDATE SET status=excluded.status,"
                " attempts=excluded.attempts, last_error=excluded.last_error,"
                " synced_at=excluded.synced_at",
                (vendor_id, "synced" if ok else "pending", attempts,
                 "" if ok else err, now if ok else None))
            conn.commit()
            conn.close()
        print(f"[sheet] vendor {vendor_id}: {'synced' if ok else 'pending: ' + err}")
    except Exception as ex:
        print(f"[sheet] vendor {vendor_id}: log failed: {ex}")


def queue_sheet_sync(vendor_id, entry):
    """Fire-and-forget: Sheet sync in a background thread, never blocks check-in."""
    if not SHEET_WEBHOOK_URL:
        return
    threading.Thread(target=sync_entry, args=(vendor_id, entry),
                     daemon=True).start()


def retry_pending_sheet_sync():
    """Background loop: every 60s, retry every entry still marked pending."""
    while True:
        time.sleep(60)
        if not SHEET_WEBHOOK_URL:
            continue
        try:
            conn = db()
            pending = conn.execute(
                "SELECT v.id, v.timestamp, v.name, v.company, v.contact,"
                " v.what, v.expertise FROM vendors v"
                " JOIN sheet_sync s ON s.vendor_id = v.id"
                " WHERE s.status = 'pending'").fetchall()
            conn.close()
            for r in pending:
                entry = {"timestamp": r[1], "name": r[2], "company": r[3],
                         "contact": r[4], "what": r[5], "expertise": r[6]}
                sync_entry(r[0], entry)
        except Exception as ex:
            print(f"[sheet] retry loop: {ex}")


def append_entry_to_spreadsheet(entry):
    """Append one vendor entry to the Vendors sheet of the .xlsx file.

    Writes columns A-F only (Timestamp, Name, Company, Contact, What they
    do, Expertise) into the first empty row (first row with no Name).
    Columns G-H (Duplicate?, From this company) already have formulas in
    rows 2-401, so they are left untouched and calculate on open in
    Excel / LibreOffice. Returns (ok, error). Never raises.
    """
    try:
        import openpyxl
    except ImportError as ex:
        return False, f"openpyxl not installed: {ex}"
    if not os.path.isfile(SPREADSHEET_PATH):
        return False, f"spreadsheet not found: {SPREADSHEET_PATH}"
    try:
        wb = openpyxl.load_workbook(SPREADSHEET_PATH)
        ws = wb["Vendors"]
        row = None
        for r in range(2, 402):
            if ws.cell(row=r, column=2).value in (None, ""):
                row = r
                break
        if row is None:
            return False, "spreadsheet Vendors sheet is full (400 rows)"
        values = [entry["timestamp"], entry["name"], entry["company"],
                  entry["contact"], entry["what"], entry["expertise"]]
        for col, val in enumerate(values, start=1):
            ws.cell(row=row, column=col).value = val
        wb.save(SPREADSHEET_PATH)
        return True, ""
    except Exception as ex:
        return False, str(ex)[:200]


def _record_spreadsheet_sync(vendor_id, ok, err):
    now = datetime.now().isoformat(timespec="seconds")
    with WRITE_LOCK:
        conn = db()
        row = conn.execute(
            "SELECT attempts FROM spreadsheet_sync WHERE vendor_id = ?",
            (vendor_id,)).fetchone()
        attempts = (row[0] + 1) if row else 1
        conn.execute(
            "INSERT INTO spreadsheet_sync (vendor_id, status, attempts,"
            " last_error, synced_at) VALUES (?,?,?,?,?)"
            " ON CONFLICT(vendor_id) DO UPDATE SET status=excluded.status,"
            " attempts=excluded.attempts, last_error=excluded.last_error,"
            " synced_at=excluded.synced_at",
            (vendor_id, "synced" if ok else "pending", attempts,
             "" if ok else err, now if ok else None))
        conn.commit()
        conn.close()
    print(f"[spreadsheet] vendor {vendor_id}: {'synced' if ok else 'pending: ' + err}")


def sync_spreadsheet_entry(vendor_id, entry):
    """Try the spreadsheet append once, record the outcome. Never raises."""
    try:
        # Serialise load-find-row-write-save: without this, two check-ins
        # arriving together both find the same empty row and one
        # overwrites the other. (Found in testing: 2nd entry lost.)
        with WRITE_LOCK:
            ok, err = append_entry_to_spreadsheet(entry)
        _record_spreadsheet_sync(vendor_id, ok, err)
    except Exception as ex:
        print(f"[spreadsheet] vendor {vendor_id}: log failed: {ex}")


def queue_spreadsheet_sync(vendor_id, entry):
    """Fire-and-forget: spreadsheet append in a background thread."""
    threading.Thread(target=sync_spreadsheet_entry, args=(vendor_id, entry),
                     daemon=True).start()


def retry_pending_spreadsheet_sync():
    """Background loop: every 60s, retry every entry still marked pending."""
    while True:
        time.sleep(60)
        try:
            conn = db()
            pending = conn.execute(
                "SELECT v.id, v.timestamp, v.name, v.company, v.contact,"
                " v.what, v.expertise FROM vendors v"
                " JOIN spreadsheet_sync s ON s.vendor_id = v.id"
                " WHERE s.status = 'pending'").fetchall()
            conn.close()
            for r in pending:
                entry = {"timestamp": r[1], "name": r[2], "company": r[3],
                         "contact": r[4], "what": r[5], "expertise": r[6]}
                sync_spreadsheet_entry(r[0], entry)
        except Exception as ex:
            print(f"[spreadsheet] retry loop: {ex}")


def esc(s):
    return s  # values go out as JSON/CSV, no HTML injection path


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # keep the console quiet

    # ---------- helpers ----------
    def send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, filename, ctype="text/html"):
        path = os.path.join(HERE, filename)
        if not os.path.isfile(path):
            return self.send_json({"error": "not found"}, 404)
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ---------- routes ----------
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path in ("/", "/index.html"):
            return self.send_file("index.html")
        if u.path == "/admin":
            return self.send_file("admin.html")
        if u.path == "/api/vendors":
            expertise = (q.get("expertise", [""])[0] or "").strip()
            search = (q.get("q", [""])[0] or "").strip().lower()
            conn = db()
            rows = conn.execute(
                "SELECT id, timestamp, name, company, contact, what, expertise"
                " FROM vendors ORDER BY company COLLATE NOCASE ASC, id ASC").fetchall()
            conn.close()
            out = []
            for r in rows:
                d = {"id": r[0], "timestamp": r[1], "name": r[2],
                     "company": r[3], "contact": r[4], "what": r[5],
                     "expertise": r[6]}
                if expertise and d["expertise"] != expertise:
                    continue
                if search and search not in " ".join(
                        str(v) for v in d.values()).lower():
                    continue
                out.append(d)
            return self.send_json({"vendors": out, "count": len(out)})
        if u.path == "/api/sheet-sync-status":
            conn = db()
            rows = conn.execute(
                "SELECT vendor_id, status, attempts, last_error, synced_at"
                " FROM sheet_sync ORDER BY vendor_id").fetchall()
            conn.close()
            return self.send_json({
                "sheet_configured": bool(SHEET_WEBHOOK_URL),
                "sync": [{"vendor_id": r[0], "status": r[1], "attempts": r[2],
                          "last_error": r[3], "synced_at": r[4]} for r in rows]})
        if u.path == "/api/spreadsheet-sync-status":
            conn = db()
            rows = conn.execute(
                "SELECT vendor_id, status, attempts, last_error, synced_at"
                " FROM spreadsheet_sync ORDER BY vendor_id").fetchall()
            conn.close()
            return self.send_json({
                "spreadsheet_path": SPREADSHEET_PATH,
                "spreadsheet_exists": os.path.isfile(SPREADSHEET_PATH),
                "sync": [{"vendor_id": r[0], "status": r[1], "attempts": r[2],
                          "last_error": r[3], "synced_at": r[4]} for r in rows]})
            # Same filters as the list: ?q= searches every field,
            # ?expertise= picks one expertise. No params = everything.
            expertise = (q.get("expertise", [""])[0] or "").strip()
            search = (q.get("q", [""])[0] or "").strip().lower()
            conn = db()
            rows = conn.execute(
                "SELECT id, timestamp, name, company, contact, what, expertise"
                " FROM vendors ORDER BY company COLLATE NOCASE ASC, id ASC").fetchall()
            conn.close()
            out = []
            for r in rows:
                d = {"id": r[0], "timestamp": r[1], "name": r[2],
                     "company": r[3], "contact": r[4], "what": r[5],
                     "expertise": r[6]}
                if expertise and d["expertise"] != expertise:
                    continue
                if search and search not in " ".join(
                        str(v) for v in d.values()).lower():
                    continue
                out.append((d["timestamp"], d["name"], d["company"],
                            d["contact"], d["what"], d["expertise"]))
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["Timestamp", "Name", "Company", "Contact",
                        "What they do", "Expertise"])
            w.writerows(out)
            body = buf.getvalue().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv")
            self.send_header("Content-Disposition",
                             'attachment; filename="vendors.csv"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/api/checkin":
            return self.send_json({"error": "not found"}, 404)
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return self.send_json({"error": "bad request"}, 400)
        fields = ["name", "company", "contact", "what", "expertise"]
        if not all(str(data.get(f, "")).strip() for f in fields):
            return self.send_json({"error": "all fields required"}, 400)
        ts = datetime.now().isoformat(timespec="seconds")
        name = data["name"].strip()
        company = data["company"].strip()
        contact = data["contact"].strip()
        with WRITE_LOCK:
            conn = db()
            # A TRUE duplicate = same person, same company, same contact.
            # Same company with a different person is NOT a duplicate —
            # they get their own row, grouped by company on the list.
            dup = conn.execute(
                "SELECT id FROM vendors WHERE LOWER(name)=LOWER(?) AND"
                " LOWER(company)=LOWER(?) AND LOWER(contact)=LOWER(?)",
                (name, company, contact)).fetchone()
            if dup:
                conn.close()
                return self.send_json(
                    {"ok": False, "error": "already_checked_in",
                     "name": name, "company": company}, 409)
            cur = conn.execute(
                "INSERT INTO vendors (timestamp, name, company, contact,"
                " what, expertise) VALUES (?,?,?,?,?,?)",
                (ts, name, company, contact,
                 data["what"].strip(), data["expertise"].strip()))
            vendor_id = cur.lastrowid
            conn.commit()
            conn.close()
        # Local save is done — vendor gets success now. Spreadsheet sync
        # runs in the background and never blocks or fails this check-in.
        # Google Sheet sync only runs if SHEET_WEBHOOK_URL is set (it
        # isn't by default — the spreadsheet is the live list now).
        entry = {"timestamp": ts, "name": name, "company": company,
                 "contact": contact, "what": data["what"].strip(),
                 "expertise": data["expertise"].strip()}
        queue_spreadsheet_sync(vendor_id, entry)
        queue_sheet_sync(vendor_id, entry)
        return self.send_json({"ok": True, "timestamp": ts})


if __name__ == "__main__":
    db().close()  # creates the file + tables on first run
    print(f"Vendor check-in app running on http://{HOST}:{PORT}/")
    print(f"  vendor page:  http://{HOST}:{PORT}/")
    print(f"  vendor list:  http://{HOST}:{PORT}/admin")
    print(f"  database:     {DB_PATH}")
    print(f"  spreadsheet:  {SPREADSHEET_PATH} "
          f"({'found' if os.path.isfile(SPREADSHEET_PATH) else 'NOT FOUND — check-ins will stay pending until it exists'})")
    print(f"  google sheet: {'ON — ' + SHEET_WEBHOOK_URL if SHEET_WEBHOOK_URL else 'OFF — spreadsheet is the live list'}")
    print("  stop with Ctrl-C")
    threading.Thread(target=retry_pending_sheet_sync, daemon=True).start()
    threading.Thread(target=retry_pending_spreadsheet_sync, daemon=True).start()
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
