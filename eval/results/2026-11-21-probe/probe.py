# T-028 retrieval probe (rag-llm-scientist), kept as-is for reproducibility. Not production code.
# Input dir <S> needs chunks_vec.json = Qdrant scroll of rag_eval_papers with with_vector=true, with_payload=true, limit=100:
#   curl -s -H "api-key: $QDRANT_API_KEY" -H content-type:application/json localhost:6333/collections/rag_eval_papers/points/scroll -d '{"limit":100,"with_payload":true,"with_vector":true}' > <S>/chunks_vec.json
# Run with the backend venv (fastembed, numpy): QDRANT_API_KEY=... uv run --project backend python eval/results/2026-11-21-probe/probe.py <S>
# 오프라인 검색 프로브 (스크래치, 운영 코드 아님)
import json, math, re, sys, collections, numpy as np, urllib.request
from fastembed import TextEmbedding, SparseTextEmbedding
S = sys.argv[1]
pts = json.load(open(f"{S}/chunks_vec.json"))["result"]["points"]
pts.sort(key=lambda p: (p["payload"]["filename"], p["payload"]["chunk_index"]))
golden = json.load(open("/Users/kimjuseong/Desktop/code/RAG_Chatbot/eval/fixtures/golden-dataset.json"))
DOC = {"transformer": "Attention", "bert": "BERT", "gpt": "Improving"}
SILVER = {"transformer-attention-heads": r"h\s*=\s*8", "transformer-bleu-score": r"28\.4",
  "transformer-attention-scaling": r"extremely small gradients", "bert-pretraining-tasks": r"Next Sentence Prediction",
  "bert-model-sizes": r"340M", "bert-masking-strategy": r"80%", "gpt-pretraining-corpus": r"BooksCorpus",
  "gpt-architecture": r"768", "gpt-ablation-no-pretraining": r"14\.8"}
KO = {"transformer-attention-heads": "기본 Transformer 모델은 어텐션 헤드를 몇 개 쓰고, 헤드당 차원은 얼마인가?",
  "transformer-bleu-score": "'big' Transformer 모델은 WMT 2014 영어-독일어 번역에서 BLEU 점수를 얼마나 받았나?",
  "transformer-attention-scaling": "scaled dot-product attention에서 왜 내적을 d_k의 제곱근으로 나누나?",
  "bert-pretraining-tasks": "BERT가 사용하는 두 가지 비지도 사전학습 과제는 무엇인가?",
  "bert-model-sizes": "BERT_BASE와 BERT_LARGE의 파라미터 수는 각각 몇 개인가?",
  "bert-masking-strategy": "BERT의 MLM에서 마스킹할 토큰을 고르면 어떤 세 가지 대체 전략을 각각 얼마나 자주 쓰나?",
  "gpt-pretraining-corpus": "GPT 언어 모델 사전학습에 쓴 데이터셋은 무엇이고 책이 대략 몇 권인가?",
  "gpt-architecture": "GPT 모델은 레이어 수, 히든 차원, 어텐션 헤드 수가 각각 얼마인가?",
  "gpt-ablation-no-pretraining": "GPT 어블레이션에서 비지도 사전학습을 빼면 평균 점수가 얼마나 떨어졌나?"}

def reconstruct(fname):
    cs = [p["payload"]["text"].split() for p in pts if p["payload"]["filename"] == fname]
    words = cs[0][:]
    for c in cs[1:]: words += c[80:]
    return words

def rechunk(size, ov):
    out = []
    for f in sorted({p["payload"]["filename"] for p in pts}):
        w = reconstruct(f); step = size - ov
        for s in range(0, len(w), step):
            out.append({"filename": f, "text": " ".join(w[s:s+size])})
            if s + size >= len(w): break
    return out

dense = TextEmbedding("intfloat/multilingual-e5-large", cache_dir="/Users/kimjuseong/Desktop/code/RAG_Chatbot/backend/app/.cache/fastembed")
bm25 = SparseTextEmbedding("Qdrant/bm25")

def idf_index(sparse_docs):
    N = len(sparse_docs); df = collections.Counter()
    for d in sparse_docs: df.update(d.keys())
    return {t: math.log((N - n + 0.5) / (n + 0.5) + 1) for t, n in df.items()}

def bm25_scores(q, sparse_docs, idf):
    qs = next(iter(bm25.query_embed([q])))
    qd = dict(zip(qs.indices.tolist(), qs.values.tolist()))
    return np.array([sum(idf.get(t, 0) * v * d.get(t, 0) for t, v in qd.items()) for d in sparse_docs])

def rrf(lists, k=2):
    sc = collections.defaultdict(float)
    for L in lists:
        for pos, i in enumerate(L): sc[i] += 1 / (pos + k)
    return [i for i, _ in sorted(sc.items(), key=lambda x: -x[1])]

def build(docs, prefix, header, from_store=False):
    texts = [(f"Document: {d['filename'].rsplit('.pdf',1)[0]}\n" if header else "") + d["text"] for d in docs]
    if from_store:
        D = np.array([p["vector"]["dense"] for p in pts])
        sp = [dict(zip(p["vector"]["sparse"]["indices"], p["vector"]["sparse"]["values"])) for p in pts]
    else:
        D = np.array(list(dense.embed([("passage: " if prefix else "") + t for t in texts])))
        sp = [dict(zip(e.indices.tolist(), e.values.tolist())) for e in bm25.embed(texts)]
    D = D / np.linalg.norm(D, axis=1, keepdims=True)
    return D, sp, idf_index(sp)

def run(name, docs, prefix, header, mode="hybrid", pre=8, k=2, lang="en", from_store=False, idx=None):
    D, sp, idf = idx or build(docs, prefix, header, from_store)
    agg = collections.defaultdict(list); tops = {}
    for g in golden:
        q = KO[g["id"]] if lang == "ko" else g["query"]
        qv = np.array(next(iter(dense.embed([("query: " if prefix else "") + q]))))
        qv /= np.linalg.norm(qv)
        dl = list(np.argsort(-(D @ qv))[:pre]); bs = bm25_scores(q, sp, idf)
        bl = [i for i in np.argsort(-bs)[:pre] if bs[i] > 0]
        top = (dl if mode == "dense" else bl if mode == "bm25" else rrf([dl, bl], k))[:8]
        tops[g["id"]] = top
        doc = DOC[g["id"].split("-")[0]]
        rel = [i for i, d in enumerate(docs) if d["filename"].startswith(doc) and re.search(SILVER[g["id"]], d["text"])]
        ranks = [r for r, i in enumerate(top) if i in rel]
        agg["docP@8"].append(sum(docs[i]["filename"].startswith(doc) for i in top) / max(len(top), 1))
        agg["hit@8"].append(1.0 if ranks else 0.0)
        agg["mrr@8"].append(1 / (ranks[0] + 1) if ranks else 0.0)
        agg["recall@8"].append(len(ranks) / len(rel) if rel else 0.0)
        agg["hit@3"].append(1.0 if ranks and ranks[0] < 3 else 0.0)
        agg["gpt_docP"].append(agg["docP@8"][-1]) if doc == "Improving" else None
    print(f"| {name} | " + " | ".join(f"{np.mean(agg[m]):.3f}" for m in ["docP@8","hit@3","hit@8","mrr@8","recall@8","gpt_docP"]) + " |", flush=True)
    return tops, (D, sp, idf)

base = [{"filename": p["payload"]["filename"], "text": p["payload"]["text"]} for p in pts]
print("| variant | docP@8 | hit@3 | hit@8 | MRR@8 | recall@8 | docP@8 (GPT cases) |\n|---|---|---|---|---|---|---|")
t0, idx0 = run("V0 prod replica (stored vectors, no prefix, RRF k=2, prefetch 8)", base, False, False, from_store=True)
# 재현 검증: 라이브 Qdrant 질의와 top-8 비교
ids = [p["id"] for p in pts]; same = 0
for g in golden:
    qv = next(iter(dense.query_embed([g["query"]]))).tolist(); qs = next(iter(bm25.query_embed([g["query"]])))
    body = {"prefetch": [{"query": qv, "using": "dense", "limit": 8}, {"query": {"indices": qs.indices.tolist(), "values": qs.values.tolist()}, "using": "sparse", "limit": 8}], "query": {"fusion": "rrf"}, "limit": 8}
    req = urllib.request.Request("http://localhost:6333/collections/rag_eval_papers/points/query", json.dumps(body).encode(), {"api-key": __import__("os").environ["QDRANT_API_KEY"], "content-type": "application/json"})
    live = [r["id"] for r in json.load(urllib.request.urlopen(req))["result"]["points"]]
    same += len(set(live) & {ids[i] for i in t0[g["id"]]})
print(f"replica-vs-live top-8 overlap: {same}/{8*len(golden)}", flush=True)
run("V1 dense only (stored, no prefix)", base, False, False, mode="dense", idx=idx0)
run("V2 BM25 only (stored)", base, False, False, mode="bm25", idx=idx0)
run("V0b prod, prefetch 50 (RRF over wider lists)", base, False, False, pre=50, idx=idx0)
_, idx3 = run("V3 + e5 query:/passage: prefixes", base, True, False)
run("V3d dense only + prefixes", base, True, False, mode="dense", idx=idx3)
_, idx4 = run("V4 V3 + title header per chunk", base, True, True)
run("V4d dense only + prefixes + header", base, True, True, mode="dense", idx=idx4)
r = rechunk(300, 60)
print(f"(rechunk 300w/60 -> {len(r)} chunks)", flush=True)
_, idx5 = run("V5 V4 + 300-word chunks (fits 512 tok)", r, True, True)
r2 = rechunk(150, 30)
print(f"(rechunk 150w/30 -> {len(r2)} chunks)", flush=True)
run("V6 V4 + 150-word chunks", r2, True, True)
print("\nKorean-translated queries (same corpus)")
run("K0 prod replica, KO queries", base, False, False, lang="ko", idx=idx0)
run("K1 prod replica dense only, KO queries", base, False, False, mode="dense", lang="ko", idx=idx0)
run("K2 bm25 only, KO queries", base, False, False, mode="bm25", lang="ko", idx=idx0)
run("K4 V4 (prefix+header), KO queries", base, True, True, lang="ko", idx=idx4)
run("K4d V4 dense only, KO queries", base, True, True, mode="dense", lang="ko", idx=idx4)
