"""merge_verified.py <sheet_export.json> : merge an export from the verification sheet into data/verified_parts.json.
Sheet rows get keys 'u<id>'. Re-running with a newer export replaces all earlier 'u*' rows (exports are cumulative).
Rows on pages already hand cross-read (non-'u' keys) are skipped; 'add' entries are de-duplicated by (page, pn)."""
import sys, json, shutil, collections
KEEP = "--keep" in sys.argv   # export covers only NEW work (fresh sheet): add to earlier u* rows instead of replacing them
src = json.load(open([a for a in sys.argv[1:] if not a.startswith("--")][0])); P = "data/verified_parts.json"
cur = json.load(open(P)); shutil.copy(P, P.replace(".json", ".pre_merge_backup.json"))
if not KEEP: cur["rows"] = {k: v for k, v in cur["rows"].items() if not k.startswith("u")}
xr_pages = {v["page"] for k, v in cur["rows"].items() if not k.startswith("u")}
n = skipped = 0
for k, v in src["rows"].items():
    if v["page"] in xr_pages: skipped += 1; continue
    cur["rows"]["u" + k] = v; n += 1
seen = {(a["page"], a["pn"]) for a in cur["add"] if (KEEP or not a.get("u"))}
if not KEEP: cur["add"] = [a for a in cur["add"] if not a.get("u")]
na = 0
for a in src["add"]:
    if (a["page"], a["pn"]) in seen or a["page"] in xr_pages: continue
    cur["add"].append(dict(a, u=1)); na += 1
json.dump(cur, open(P, "w"), indent=1)
c = collections.Counter(v["st"] for k, v in cur["rows"].items() if k.startswith("u"))
print(f"merged {n} rows ({dict(c)}), skipped {skipped} on cross-read pages, {na} added rows; total rows {len(cur['rows'])}, adds {len(cur['add'])}")
