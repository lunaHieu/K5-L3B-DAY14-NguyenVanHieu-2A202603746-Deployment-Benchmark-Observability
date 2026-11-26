# Deployment — Day 14

**Nền tảng:** Render Blueprint (`06-lab-complete/render.yaml`)

**Branch:** `main`

**Public URL:** https://k5-day14-agent-dcce.onrender.com

## Dịch vụ và cấu hình

| Mục | Giá trị |
|---|---|
| Web service | `k5-day14-agent`, Docker, Singapore, Free |
| Key Value | `k5-day14-cache`, Singapore, Free |
| `ENVIRONMENT` | `production` |
| `RATE_LIMIT_PER_MINUTE` | `10` |
| `DAILY_BUDGET_USD` | `1.0` (budget demo) |
| `REDIS_URL` | Render tự lấy từ connection string của Key Value; không ghi URL chứa credential vào repo |
| `AGENT_API_KEY` | Đặt riêng trong Render khi tạo Blueprint; không ghi giá trị vào repo |

Railway đã thử trước đó nhưng workspace bị giới hạn và Redis deployment Failed, nên không có public URL Railway để kiểm chứng. Học viên báo Render web service đã Live; ảnh Dashboard cho thấy `k5-day14-agent` Deployed và `k5-day14-cache` Available. Kiểm tra public URL ngày 26/11/2026 lúc 20:58 (GMT+7): `/health` **HTTP 200**, body `{"status":"ok","environment":"production","uptime_seconds":114.46}`; `/ready` **HTTP 200**, body `{"ready":true}`; `/ask` khi thiếu key **HTTP 401**, body `{"detail":"Missing or invalid API key"}`. `/ready` 200 chứng tỏ app kết nối được Redis tại thời điểm kiểm tra. Học viên chạy lệnh `curl` có `X-API-Key` trong WSL và báo **HTTP 200**; AI không nhận hoặc lưu giá trị key.

## Kiểm tra public URL

Trong WSL, nhập API key trong terminal; biến này chỉ tồn tại ở phiên shell hiện tại.

```bash
export BASE_URL='https://k5-day14-agent-dcce.onrender.com'
read -rsp 'AGENT_API_KEY: ' AGENT_API_KEY; echo

curl -i "$BASE_URL/health"
curl -i "$BASE_URL/ready"
curl -i -X POST "$BASE_URL/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'
curl -i -X POST "$BASE_URL/ask" -H "X-API-Key: $AGENT_API_KEY" -H 'Content-Type: application/json' -d '{"question":"Hello"}'

unset AGENT_API_KEY
```

Đã xác nhận đủ bốn mã HTTP: `/health` **200**, `/ready` **200**, `/ask` thiếu key **401**, `/ask` có key **200**. Ba kết quả đầu do AI gọi trực tiếp; kết quả cuối dựa trên output terminal học viên cung cấp.

## Bằng chứng giao diện

- [x] `screenshots/dashboard.png` — Render Dashboard hiển thị `k5-day14-agent` Deployed và `k5-day14-cache` Available.
- [x] `screenshots/running.png` — web service trạng thái Live và URL public.
- [x] `screenshots/test.png` — terminal hiển thị `/health` 200, `/ready` 200, `/ask` thiếu key 401 và có key 200.
