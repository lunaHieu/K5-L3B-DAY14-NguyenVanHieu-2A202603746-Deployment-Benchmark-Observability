# Deployment — Day 14

**Học viên:** Nguyễn Văn Hiếu

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

Railway đã thử trước đó nhưng workspace bị giới hạn và Redis deployment Failed, nên không có public URL Railway để kiểm chứng. Học viên báo Render web service đã Live. Kiểm tra public URL ngày 26/11/2026 lúc 20:58 (GMT+7): `/health` **HTTP 200**, body `{"status":"ok","environment":"production","uptime_seconds":114.46}`; `/ready` **HTTP 200**, body `{"ready":true}`; `/ask` khi thiếu key **HTTP 401**, body `{"detail":"Missing or invalid API key"}`. `/ready` 200 chứng tỏ app kết nối được Redis tại thời điểm kiểm tra; trạng thái Key Value trên giao diện Render và `/ask` với key đúng chưa được xác nhận.

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

Đã xác nhận ba kết quả đầu: `/health` **200**, `/ready` **200**, `/ask` thiếu key **401**. Còn cần xác nhận `/ask` có key **200** bằng lệnh cuối; chỉ ghi kết quả sau khi có response thực tế.

## Bằng chứng giao diện

- [ ] `screenshots/dashboard.png` — Render Dashboard hiển thị cả web service và Key Value.
- [ ] `screenshots/running.png` — web service trạng thái Live và URL public.
- [ ] `screenshots/test.png` — kết quả gọi endpoint từ public URL.
