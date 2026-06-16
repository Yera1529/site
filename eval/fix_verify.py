"""Проверка исправлений аудита против живого backend (DEV_BYPASS on)."""
import json, urllib.request, urllib.error

BASE = "http://localhost:8000"


def call(method, path, payload=None, timeout=60):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return None, str(e).encode()


def docx(html, filename="doc.docx"):
    st, body = call("POST", "/api/export-docx", {"html": html, "filename": filename})
    return st, (len(body) if isinstance(body, (bytes, bytearray)) else 0)


VT, FF, ESC, NUL, SUR = chr(0x0b), chr(0x0c), chr(0x1b), chr(0x01), chr(0xd800)
print("== export-docx: должно быть 200 (санитизация) или 400, НЕ 500 ==")
cases = [
    ("control 0x0b", "<p>before" + VT + "after</p>"),
    ("control 0x0c", "<p>a" + FF + "b</p>"),
    ("control 0x1b", "<p>a" + ESC + "b</p>"),
    ("control 0x01", "<p>a" + NUL + "b</p>"),
    ("entity &#11;", "<p>x&#11;y</p>"),
    ("entity &#x1b;", "<p>x&#x1b;y</p>"),
    ("surrogate entity &#xd800;", "<p>x&#xd800;y</p>"),
    ("normal html", "<h1>Представление</h1><p>текст дела</p>"),
]
for label, html in cases:
    st, n = docx(html)
    verdict = "OK" if st in (200, 400) else f"!!FAIL {st}"
    print(f"  [{verdict}] {label}: status={st} bytes={n}")

print("\n== export-docx path traversal filename → должен 200 и НЕ выйти из storage ==")
st, n = docx("<p>pwned</p>", "../../../../Windows/Temp/pwned2.docx")
print(f"  status={st}")

print("\n== search-laws с null-полями violations: 200 + нормы, НЕ 0/краш ==")
_, m = call("POST", "/api/matters", {"name": "__fixtest__", "description": "Продажа алкоголя несовершеннолетнему в магазине"})
mid = json.loads(m)["id"]
try:
    payload = {"matter_id": mid, "query": "",
               "violations": [{"description": None, "responsible": None, "link_to_crime": None},
                              {"description": "продажа алкоголя несовершеннолетнему", "responsible": "магазин"}],
               "addressee": None}
    st, body = call("POST", "/api/search-laws", payload, timeout=120)
    laws = json.loads(body) if st == 200 else []
    print(f"  null violations: status={st} норм={len(laws) if isinstance(laws, list) else 'n/a'} (ждём 200 и >0)")
    st2, body2 = call("POST", "/api/search-laws",
                      {"matter_id": mid, "query": "кража из неохраняемого склада", "violations": [], "addressee": None}, timeout=120)
    laws2 = json.loads(body2) if st2 == 200 else []
    print(f"  пустые violations: status={st2} норм={len(laws2) if isinstance(laws2, list) else 'n/a'}")
finally:
    call("DELETE", f"/api/matters/{mid}")
    print(f"  matter {mid} удалён")
