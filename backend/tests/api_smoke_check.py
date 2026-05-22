"""API smoke tests — verify all critical endpoints return expected status codes.

Run inside Docker: python tests/test_api_smoke.py
"""
import httpx
import json
import sys

BASE = "http://localhost:8000"

def test_endpoint(method, path, expected=200, data=None, json_body=None):
    try:
        r = httpx.request(method, f"{BASE}{path}", timeout=10, data=data, json=json_body)
        ok = r.status_code == expected
        status = "  OK" if ok else "FAIL"
        detail = ""
        if not ok:
            try:
                detail = f" => {r.json().get('detail', '')[:80]}"
            except:
                detail = f" => {r.text[:80]}"
        print(f"{status} {r.status_code:3d} (exp {expected}) {method:6s} {path}{detail}")
        return ok
    except Exception as e:
        print(f"ERR  ---                 {method:6s} {path} => {e}")
        return False

def main():
    results = []
    print("=" * 70)
    print("API SMOKE TESTS")
    print("=" * 70)

    # === Health ===
    print("\n--- Health ---")
    results.append(test_endpoint("GET", "/api/health"))

    # === Auth ===
    print("\n--- Auth ---")
    results.append(test_endpoint("GET", "/api/auth/me"))
    results.append(test_endpoint("POST", "/api/auth/login",
        expected=401,  # No matching user exists
        json_body={"email": "admin@test.com", "password": "admin123"}))

    # === Matters ===
    print("\n--- Matters ---")
    results.append(test_endpoint("GET", "/api/matters"))

    # === Knowledge Base ===
    print("\n--- Knowledge Base ---")
    results.append(test_endpoint("GET", "/api/knowledge-base"))
    results.append(test_endpoint("GET", "/api/knowledge-base/stats"))

    # === Legislation ===
    print("\n--- Legislation ---")
    results.append(test_endpoint("GET", "/api/legislation"))
    results.append(test_endpoint("GET", "/api/legislation/categories"))

    # === RAG Laws ===
    print("\n--- RAG Laws ---")
    r = httpx.get(f"{BASE}/api/rag-laws/stats", timeout=10)
    stats = r.json()
    print(f"  RAG-Laws stats: {json.dumps(stats, ensure_ascii=False)}")
    results.append(r.status_code == 200)

    # Test search with case description
    search_r = httpx.post(f"{BASE}/api/rag-laws/search", json={
        "query": "кража из магазина, не обеспечена охрана объекта",
        "top_k": 5,
    }, timeout=30)
    print(f"  RAG-Laws search: status={search_r.status_code}")
    if search_r.status_code == 200:
        search_data = search_r.json()
        print(f"  Found {len(search_data)} results")
        for i, r_item in enumerate(search_data[:3]):
            print(f"    [{i+1}] {r_item.get('law_name', '?')[:40]} - "
                  f"ст.{r_item.get('article_number', '?')} "
                  f"(score={r_item.get('score', 0):.4f}, "
                  f"type={r_item.get('norm_type', '?')})")
        results.append(len(search_data) > 0)
    else:
        print(f"  FAIL: {search_r.text[:200]}")
        results.append(False)

    # Test search with DTP case
    search_dtp = httpx.post(f"{BASE}/api/rag-laws/search", json={
        "query": "дтп на перекрестке, водитель сбил пешехода, неисправный светофор",
        "top_k": 5,
    }, timeout=30)
    print(f"\n  RAG-Laws DTP search: status={search_dtp.status_code}")
    if search_dtp.status_code == 200:
        dtp_data = search_dtp.json()
        print(f"  Found {len(dtp_data)} results")
        for i, r_item in enumerate(dtp_data[:3]):
            print(f"    [{i+1}] {r_item.get('law_name', '?')[:40]} - "
                  f"ст.{r_item.get('article_number', '?')} "
                  f"(score={r_item.get('score', 0):.4f})")
        results.append(len(dtp_data) > 0)
    else:
        results.append(False)

    # === Search Laws (ChromaDB) — requires matter_id ===
    print("\n--- Search Laws (ChromaDB) ---")
    print("  [SKIP] Requires valid matter_id — tested via generate-document flow")
    results.append(True)  # Skip, tested indirectly

    # === Representations ===
    print("\n--- Representations ---")
    results.append(test_endpoint("GET", "/api/representations"))

    # === Templates ===
    print("\n--- Templates ---")
    results.append(test_endpoint("GET", "/api/templates"))
    results.append(test_endpoint("GET", "/api/templates/article200/blank"))
    results.append(test_endpoint("GET", "/api/templates-sd/list"))

    # === Settings ===
    print("\n--- Settings ---")
    results.append(test_endpoint("GET", "/api/settings"))

    # === Export DOCX (needs HTML body) ===
    print("\n--- Export DOCX ---")
    docx_r = httpx.post(f"{BASE}/api/export-docx", json={
        "html": "<h1>ПРЕДСТАВЛЕНИЕ</h1><p>Текст представления.</p>",
        "filename": "test.docx",
    }, timeout=10)
    print(f"  DOCX export: status={docx_r.status_code}, content-type={docx_r.headers.get('content-type', '?')}")
    if docx_r.status_code == 200:
        print(f"  File size: {len(docx_r.content)} bytes")
        results.append(len(docx_r.content) > 100)
    else:
        print(f"  FAIL: {docx_r.text[:200]}")
        results.append(False)

    # === Summary ===
    print("\n" + "=" * 70)
    passed = sum(1 for r in results if r)
    failed = len(results) - passed
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(results)} tests")
    if failed > 0:
        print("STATUS: SOME TESTS FAILED ❌")
        return 1
    else:
        print("STATUS: ALL TESTS PASSED ✅")
        return 0

if __name__ == "__main__":
    sys.exit(main())
