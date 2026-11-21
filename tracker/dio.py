#!/usr/bin/env python3
"""Dio's learning tracker, built on the Marble os-taxonomy.

  python3 tracker/dio.py find <text>                     search topics by name/description
  python3 tracker/dio.py show <topicId>                  show a topic, its evidence and prerequisites
  python3 tracker/dio.py seed                            set every SSIS-mapped topic to 'introduced' (if it isn't set yet)
  python3 tracker/dio.py log <topicId|unitId> <status> [--note ..] [--source ..] [--date YYYY-MM-DD]
  python3 tracker/dio.py next                            print what to check and what to learn next
  python3 tracker/dio.py build                           write tracker/dashboard.html

status: not_started | introduced | practising | secure | review
"""
import argparse, datetime, html, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TAX = ROOT / "taxonomy"
PROGRESS = ROOT / "progress.json"
STATUSES = ["not_started", "introduced", "practising", "secure", "review"]
STATUS_TH = {"not_started": "ยังไม่เริ่ม", "introduced": "เพิ่งเรียน", "practising": "กำลังฝึก",
             "secure": "ทำได้แล้ว", "review": "ต้องทบทวน"}
DONE = {"secure"}
OK_FOR_NEXT = {"secure", "practising"}


def load():
    topics = {t["id"]: t for t in json.load(open(TAX / "topics.json"))["topics"]}
    deps = json.load(open(TAX / "dependencies.json"))
    deps = deps["dependencies"] if isinstance(deps, dict) else deps
    ext = json.load(open(ROOT / "extensions.json"))
    for t in ext["topics"]:
        t["extension"] = True
        topics[t["id"]] = t
    deps = deps + ext["prerequisites"]
    smap = json.load(open(ROOT / "ssis-map.json"))
    prog = json.load(open(PROGRESS)) if PROGRESS.exists() else {"topics": {}, "log": []}
    prereqs = {}
    for d in deps:
        prereqs.setdefault(d["topicId"], []).append(d)
    return topics, prereqs, smap, prog


def save(prog):
    PROGRESS.write_text(json.dumps(prog, ensure_ascii=False, indent=1) + "\n")


def status_of(prog, tid):
    return prog["topics"].get(tid, {}).get("status", "not_started")


def tracked_ids(smap, prog):
    ids = [t for u in smap["units"] for t in u["topics"]]
    ids += [t for t in prog["topics"] if t not in ids]
    return list(dict.fromkeys(ids))


def units_by_topic(smap):
    m = {}
    for u in smap["units"]:
        for t in u["topics"]:
            m.setdefault(t, []).append(u)
    return m


def validate(topics, smap):
    bad = [(u["id"], t) for u in smap["units"] for t in u["topics"] if t not in topics]
    for u, t in bad:
        print(f"!! unit {u}: topic {t} not found", file=sys.stderr)
    return not bad


def analysis(topics, prereqs, smap, prog, min_age=6, max_age=7):
    tracked = tracked_ids(smap, prog)
    tset = set(tracked)
    check, ready = {}, {}
    for tid in tracked:
        if status_of(prog, tid) in DONE:
            continue
        for d in prereqs.get(tid, []):
            p = d["prerequisiteId"]
            if d["strength"] == "hard" and p in topics and p not in tset and status_of(prog, p) == "not_started":
                check.setdefault(p, []).append(tid)
    # ready next: an untracked topic whose hard prerequisites include something tracked, and all its hard prerequisites are practising/secure
    for tid, ds in prereqs.items():
        t = topics.get(tid)
        if not t or tid in tset or status_of(prog, tid) != "not_started" or not (min_age <= t.get("ageRangeStart", 99) <= max_age):
            continue
        hard = [d["prerequisiteId"] for d in ds if d["strength"] == "hard"]
        if hard and any(h in tset for h in hard) and all(status_of(prog, h) in OK_FOR_NEXT for h in hard):
            ready[tid] = hard
    # most central (most other topics build on it) first
    ready = dict(sorted(ready.items(), key=lambda kv: -topics[kv[0]].get("centrality", 0)))
    return check, ready


def cmd_find(a):
    topics, *_ = load()
    q = " ".join(a.text).lower()
    for t in topics.values():
        if q in (t["name"] + " " + t["description"]).lower():
            print(f'{t["id"]:16} {t["subject"][:11]:11} {t["domain"][:22]:22} {t["ageRangeStart"]}-{t["ageRangeEnd"]}  {t["name"]}')


def cmd_show(a):
    topics, prereqs, smap, prog = load()
    t = topics[a.id]
    print(f'{t["name"]}  [{t["subject"]} / {t["domain"]}, age {t["ageRangeStart"]}-{t["ageRangeEnd"]}]')
    print(t["description"])
    print("status:", status_of(prog, a.id))
    print("evidence:")
    for e in t["evidence"]:
        print("  -", e)
    print("prerequisites:")
    for d in prereqs.get(a.id, []):
        p = topics.get(d["prerequisiteId"], {"name": "?"})
        print(f'  [{d["strength"]}] {d["prerequisiteId"]} {p["name"]} ({status_of(prog, d["prerequisiteId"])}): {d["reason"]}')


def cmd_seed(a):
    topics, prereqs, smap, prog = load()
    if not validate(topics, smap):
        sys.exit(1)
    today = datetime.date.today().isoformat()
    n = 0
    for u in smap["units"]:
        for tid in u["topics"]:
            if tid not in prog["topics"]:
                prog["topics"][tid] = {"status": "introduced", "updated": today}
                prog["log"].append({"date": today, "topic": tid, "status": "introduced",
                                    "source": u["id"], "note": "Taught at school (from the SSIS map)"})
                n += 1
    save(prog)
    print(f"seeded {n} topics")


def cmd_log(a):
    topics, prereqs, smap, prog = load()
    if a.status not in STATUSES:
        sys.exit(f"status must be one of {STATUSES}")
    unit = next((u for u in smap["units"] if u["id"] == a.target), None)
    ids = unit["topics"] if unit else [a.target]
    for tid in ids:
        if tid not in topics:
            sys.exit(f"unknown topic/unit: {tid}")
    date = a.date or datetime.date.today().isoformat()
    for tid in ids:
        prog["topics"][tid] = {"status": a.status, "updated": date}
        prog["log"].append({"date": date, "topic": tid, "status": a.status,
                            "source": a.source or (unit["id"] if unit else ""), "note": a.note or ""})
    save(prog)
    print(f"logged {len(ids)} topic(s) → {a.status}")


def cmd_next(a):
    topics, prereqs, smap, prog = load()
    check, ready = analysis(topics, prereqs, smap, prog)
    print("== Prerequisites to check (untested hard prerequisites of what Dio is learning now) ==")
    for p, needed in sorted(check.items(), key=lambda x: -len(x[1])):
        print(f'  {p:16} {topics[p]["name"]}  ← needed by {len(needed)} topic(s)')
    print("\n== Ready next (all hard prerequisites at practising/secure) ==")
    for tid in ready:
        print(f'  {tid:16} {topics[tid]["subject"]}: {topics[tid]["name"]}')
    if not ready:
        print("  (none yet: mark some topics practising/secure first)")


def cmd_build(a):
    topics, prereqs, smap, prog = load()
    validate(topics, smap)
    clusters = json.load(open(TAX / "clusters.json"))
    clusters = clusters["clusters"] if isinstance(clusters, dict) else clusters
    check, ready = analysis(topics, prereqs, smap, prog)
    ubt = units_by_topic(smap)
    tracked = tracked_ids(smap, prog)

    def tinfo(tid):
        t = topics[tid]
        return {"id": tid, "name": t["name"], "subject": t["subject"], "domain": t["domain"],
                "desc": t["description"], "evidence": t["evidence"], "age": [t["ageRangeStart"], t["ageRangeEnd"]],
                "ext": bool(t.get("extension")), "status": status_of(prog, tid),
                "updated": prog["topics"].get(tid, {}).get("updated", ""),
                "units": [{"id": u["id"], "title": u["title"], "assessment": u.get("assessment", "")} for u in ubt.get(tid, [])],
                "prereqs": [{"id": d["prerequisiteId"], "name": topics[d["prerequisiteId"]]["name"],
                             "strength": d["strength"], "status": status_of(prog, d["prerequisiteId"])}
                            for d in prereqs.get(tid, []) if d["prerequisiteId"] in topics]}

    data = {
        "generated": datetime.date.today().isoformat(),
        "student": smap["student"],
        "statusTh": STATUS_TH,
        "units": smap["units"],
        "tracked": [tinfo(t) for t in tracked],
        "check": [dict(tinfo(p), neededBy=[topics[n]["name"] for n in ns]) for p, ns in sorted(check.items(), key=lambda x: -len(x[1]))],
        "ready": [tinfo(t) for t in ready],
        "reports": prog.get("reports", []),
        "log": sorted(prog["log"], key=lambda e: e["date"], reverse=True)[:60],
        "names": {tid: topics[tid]["name"] for tid in {e["topic"] for e in prog["log"]} if tid in topics},
        "clusters": [c for c in clusters if c.get("ageRangeStart", 99) <= 7 and c["subject"] in {"English", "Mathematics", "Science"}],
    }
    tpl = (ROOT / "dashboard.template.html").read_text()
    out = tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    (ROOT / "dashboard.html").write_text(out)
    print(f"wrote {ROOT / 'dashboard.html'}  ({len(tracked)} tracked, {len(check)} to check, {len(ready)} ready)")
    build_graph(topics, prereqs, prog, data["generated"])
    export_artifact()


def export_artifact():
    """tracker/publish/: the same pages, shaped for the private claude.ai artifact.
    index.html = dashboard as page content (the artifact host adds doctype/head/body), graph.html = its own full page."""
    import re
    pub = ROOT / "publish"
    pub.mkdir(exist_ok=True)
    dash = (ROOT / "dashboard.html").read_text()
    dash = re.sub(r"<!doctype html>\s*|</?html[^>]*>\s*|<head>\s*|</head>\s*|</?body>\s*", "", dash, flags=re.I)
    dash = re.sub(r'<meta (charset|name="viewport")[^>]*>\s*', "", dash)
    (pub / "index.html").write_text(dash)
    graph = (ROOT / "graph.html").read_text().replace(
        '<a href="dashboard.html">', '<a href="./" onclick="if(history.length>1){history.back();return false}">')
    (pub / "graph.html").write_text(graph)


def likely_passed(topics, prereqs, prog):
    """Topics Dio has probably already passed even though nobody logged them:
    - inf_prereq: a prerequisite (hard or soft, transitive) of a topic at practising/secure
    - inf_age:    English/Maths topics for age 6 and under (Dio is in P1 and scored A*)"""
    out = {}
    stack = [t for t, v in prog["topics"].items() if v["status"] in OK_FOR_NEXT]
    seen = set()
    while stack:
        for d in prereqs.get(stack.pop(), []):
            p = d["prerequisiteId"]
            if p in topics and p not in seen:
                seen.add(p)
                stack.append(p)
    for p in seen:
        if p not in prog["topics"]:
            out[p] = "inf_prereq"
    for tid, t in topics.items():
        if tid not in prog["topics"] and tid not in out and t["subject"] in ("English", "Mathematics") and t["ageRangeEnd"] <= 6:
            out[tid] = "inf_age"
    return out


def build_graph(topics, prereqs, prog, generated):
    inferred = likely_passed(topics, prereqs, prog)
    ids = list(topics)
    idx = {t: i for i, t in enumerate(ids)}
    nodes = []
    for tid in ids:
        t = topics[tid]
        st = prog["topics"].get(tid, {}).get("status") or inferred.get(tid, "")
        nodes.append([tid, t["name"], t["subject"], t["domain"], t["ageRangeStart"], t["ageRangeEnd"], st,
                      t["description"][:240], round(t.get("centrality") or 0.02, 4)])
    edges = [[idx[d["topicId"]], idx[d["prerequisiteId"]], 1 if d["strength"] == "hard" else 0]
             for ds in prereqs.values() for d in ds if d["topicId"] in idx and d["prerequisiteId"] in idx]
    data = {"generated": generated, "nodes": nodes, "edges": edges}
    tpl = (ROOT / "graph.template.html").read_text()
    out = tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
    (ROOT / "graph.html").write_text(out)
    n_inf = sum(1 for v in inferred.values())
    print(f"wrote {ROOT / 'graph.html'}  ({len(nodes)} topics, {len(edges)} edges, {len(prog['topics'])} logged + {n_inf} likely passed)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("find"); p.add_argument("text", nargs="+"); p.set_defaults(f=cmd_find)
    p = sp.add_parser("show"); p.add_argument("id"); p.set_defaults(f=cmd_show)
    p = sp.add_parser("seed"); p.set_defaults(f=cmd_seed)
    p = sp.add_parser("log"); p.add_argument("target"); p.add_argument("status")
    p.add_argument("--note"); p.add_argument("--source"); p.add_argument("--date"); p.set_defaults(f=cmd_log)
    p = sp.add_parser("next"); p.set_defaults(f=cmd_next)
    p = sp.add_parser("build"); p.set_defaults(f=cmd_build)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
