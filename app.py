from __future__ import annotations
from document_index import DocumentIndex

import os
import time
import csv

from pathlib import Path
from typing import Dict, List
from threading import Lock
from document_index import DocumentIndex

from flask import Flask, jsonify, render_template, request

from engine import AutocompleteEngine
from trie import Trie

# Patricia is optional
try:
    from patricia import PatriciaTrie  # type: ignore
    HAS_PATRICIA = True
except Exception:
    HAS_PATRICIA = False


app = Flask(__name__)
QUERY_LOG = Path(os.environ.get("query_log.csv"))
LOG_LOCK = Lock()



# ----------------------------
# Build engines (Trie + Patricia)
# ----------------------------
engines: Dict[str, AutocompleteEngine] = {"trie": AutocompleteEngine(Trie())}
if HAS_PATRICIA:
    engines["patricia"] = AutocompleteEngine(PatriciaTrie())

doc_indexes = {"trie": DocumentIndex(Trie())}
if HAS_PATRICIA:
    doc_indexes["patricia"] = DocumentIndex(PatriciaTrie())

def load_queries() -> List[str]:
    """
    Loads queries from:
      1) env QUERY_FILE
      2) ./queries.txt
    Else falls back to a small default list.
    """
    candidates = []
    env_fp = os.environ.get("QUERY_FILE", "").strip()
    if env_fp:
        candidates.append(Path(env_fp))
    candidates.append(Path("queries_generated.txt"))

    for fp in candidates:
        if fp.exists() and fp.is_file():
            lines = [ln.strip("\n") for ln in fp.read_text(encoding="utf-8", errors="ignore").splitlines()]
            return [ln for ln in lines if ln.strip()]

    return [
        "car", "cart", "cat", "camera", "camp", "can", "candy",
        "dog", "door", "doom", "dormitory",
        "apple", "application", "apply", "app",
    ]


EVENTS_FILE = Path(os.environ.get("EVENTS_FILE", "events_rle.csv"))

def load_events_rle(fp: Path):
    if not fp.exists():
        return
    with fp.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            q = row.get("query", "")
            n = int(row.get("count", "1") or 1)
            for e in engines.values():
                e.add_query_n(q, n)

load_events_rle(EVENTS_FILE)
#print("EVENTS_FILE:", EVENTS_FILE.resolve(), "exists?", EVENTS_FILE.exists())
#print("freq coffee:", engines["trie"].freq.get("can i sleep after coffee", 0))
print("trie freq:",
      engines["trie"].trie._get_freq("can i sleep"),
      engines["trie"].trie._get_freq("can i sleep after"),
      engines["trie"].trie._get_freq("can i sleep after coffee"))

# Load once at startup
# for q in load_queries():
#     for e in engines.values():
#         e.add_query(q)


@app.get("/")
def index():
    return render_template("index.html", has_patricia=HAS_PATRICIA)
@app.get("/doc-search")
def doc_search_page():
    return render_template("doc_search.html", has_patricia=HAS_PATRICIA)


@app.get("/suggest")
def suggest():
    q = request.args.get("q", "")
    ds = request.args.get("ds", "trie")
    mode = request.args.get("mode", "cached")
    try:
        k = int(request.args.get("k", "10"))
    except ValueError:
        k = 10

    # guardrails
    if ds not in engines:
        ds = "trie"
    if k < 1:
        k = 1
    if k > 50:
        k = 50

    t0 = time.perf_counter()
    items = engines[ds].suggest(q, k=k, mode=mode)
    ms = (time.perf_counter() - t0) * 1000.0

    return jsonify({"items": items, "ms": ms})

@app.get("/api/doc/list")
def list_docs():
    ds = request.args.get("ds", "trie")
    if ds not in doc_indexes:
        ds = "trie"

    docs = sorted(doc_indexes[ds].documents.keys())
    return jsonify({"ok": True, "documents": docs})

@app.get("/api/doc/view")
def doc_view():
    ds = request.args.get("ds", "trie")
    doc_id = request.args.get("doc_id", "").strip()
    prefix = request.args.get("prefix", "").strip()

    if ds not in doc_indexes:
        ds = "trie"

    if not doc_id:
        return jsonify({"ok": False, "error": "doc_id is required"}), 400

    result = doc_indexes[ds].search_prefix(prefix, doc_id=doc_id)

    return jsonify({
        "ok": True,
        "doc_id": result["document_doc_id"],
        "document_html": result["document_html"],
        "matched_words": result["matched_words"],
        "results": result["results"],
    })

@app.post("/add")
def add_query():
    data = request.get_json(silent=True) or {}
    q = str(data.get("q", "")).strip()
    if not q:
        return jsonify({"ok": False, "error": "empty"}), 400

    nq = engines["trie"].normalize(q)
    if not nq:
        return jsonify({"ok": False, "error": "empty"}), 400

    for e in engines.values():
        e.add_query(nq)

    ts = time.time()
    with LOG_LOCK:
        is_new = not QUERY_LOG.exists()
        QUERY_LOG.parent.mkdir(parents=True, exist_ok=True)
        with QUERY_LOG.open("a", encoding="utf-8") as f:
            if is_new:
                f.write("ts,query\n")
            f.write(f'{ts},"{nq}"\n')

    return jsonify({"ok": True})

@app.post("/api/doc/upload_text")
def upload_doc_text():
    ds = request.form.get("ds", "trie")
    doc_id = request.form.get("doc_id", "").strip()
    text = request.form.get("text", "").strip()

    if ds not in doc_indexes:
        ds = "trie"

    if not doc_id:
        return jsonify({"ok": False, "error": "Document name is required"}), 400
    if not text:
        return jsonify({"ok": False, "error": "Text content is required"}), 400

    try:
        doc_indexes[ds].add_document(doc_id, text)
        return jsonify({"ok": True, "message": f"Document '{doc_id}' uploaded to {ds}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.post("/api/doc/upload_file")
def upload_doc_file():
    ds = request.form.get("ds", "trie")
    doc_id = request.form.get("doc_id", "").strip()
    file = request.files.get("file")

    if ds not in doc_indexes:
        ds = "trie"

    if not doc_id:
        return jsonify({"ok": False, "error": "Document name is required"}), 400
    if file is None or file.filename == "":
        return jsonify({"ok": False, "error": "Please choose a .txt file"}), 400

    try:
        text = file.read().decode("utf-8")
    except UnicodeDecodeError:
        return jsonify({"ok": False, "error": "Only UTF-8 .txt files are supported for now"}), 400

    try:
        doc_indexes[ds].add_document(doc_id, text)
        return jsonify({"ok": True, "message": f"File '{doc_id}' uploaded to {ds}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@app.get("/api/doc/search_prefix")
def doc_search_prefix():
    ds = request.args.get("ds", "trie")
    prefix = request.args.get("prefix", "").strip()
    doc_id = request.args.get("doc_id", "all").strip()

    if ds not in doc_indexes:
        ds = "trie"

    t0 = time.perf_counter()
    result = doc_indexes[ds].search_prefix(prefix, doc_id=doc_id)
    ms = (time.perf_counter() - t0) * 1000.0

    result["ok"] = True
    result["ms"] = ms
    result["ds"] = ds
    return jsonify(result)

if __name__ == "__main__":
    # http://127.0.0.1:5000
    app.run(host="127.0.0.1", port=5000, debug=True)
