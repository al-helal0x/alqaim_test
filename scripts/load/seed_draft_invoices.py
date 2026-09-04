"""يولّد فواتير مبيعات مسودة (draft) بعدد كافٍ لـ k6_sales_invoice_post.js
ضد core-api حقيقي، ويكتب معرّفاتها إلى JSON. بلا أي تبعية خارجية (urllib
فقط) كي يعمل بأي بايثون 3 قياسي على المضيف بلا pip install.
"""
import json
import sys
import time
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8000"
REFRESH_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJlMTY2NTBkMC01MzZhLTQ3NDQtYjQ2OS0wNTNiODQ5YTlhZDgiLCJ0eXBlIjoicmVmcmVzaCIsImlhdCI6MTc4NzQyNTI3OSwiZXhwIjoxNzkwMDE3Mjc5LCJqdGkiOiI3ZDU0MDRmOS1hN2ViLTQyNmUtYWNhZi0xYTExNGIzMTg3NTEifQ.DGjEJgNYy1GlMSoCp4G_pU75Ni48pdJZ9lM6-21n0Vc"
PARTNER_ID = "c0db349c-0ebe-4d76-a69f-b3013add8d38"
PRODUCT_ID = "3cc66d5e-0426-4fd7-9caf-682749d157f0"
WAREHOUSE_ID = "9c1901a6-9409-4bd0-975f-2f6dc2222a92"
COUNT = 4000
OUT_FILE = "draft_invoice_ids.json"


def _post(path, body, token=None):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(BASE_URL + path, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def refresh_access_token():
    resp = _post("/auth/refresh", {"refresh_token": REFRESH_TOKEN})
    return resp["access_token"]


def main():
    token = refresh_access_token()
    refreshed_at = time.time()
    ids = []
    for i in range(COUNT):
        if time.time() - refreshed_at > 600:  # كل 10 دقائق
            token = refresh_access_token()
            refreshed_at = time.time()
        body = {
            "partner_id": PARTNER_ID,
            "warehouse_id": WAREHOUSE_ID,
            "lines": [{"product_id": PRODUCT_ID, "quantity": 1, "unit_price": 10.0}],
        }
        try:
            resp = _post("/sales-invoices", body, token=token)
            ids.append(resp["id"])
        except urllib.error.HTTPError as exc:
            print(f"[{i}] فشل: {exc.code} {exc.read()[:200]}", file=sys.stderr)
        if i % 200 == 0:
            print(f"{i}/{COUNT}")
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(ids, f)
    print(f"تم: {len(ids)} فاتورة مسودة مكتوبة إلى {OUT_FILE}")


if __name__ == "__main__":
    main()