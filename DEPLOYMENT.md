# Deployment — Day 14

**Học viên:** Nguyễn Văn Hiếu

**Nền tảng:** Render Blueprint (`06-lab-complete/render.yaml`)

**Branch:** `main`

**Public URL:** Chờ Render triển khai; điền URL `.onrender.com` thực tế sau khi web service báo Live.

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

Railway đã thử trước đó nhưng workspace bị giới hạn và Redis deployment Failed, nên không có public URL Railway để kiểm chứng. Render Blueprint đang chờ kết quả triển khai; các dòng trạng thái dưới đây chưa được đánh dấu PASS.

## Kiểm tra public URL

Trong WSL, thay URL đúng từ trang web service Render. Nhập API key trong terminal; biến này chỉ tồn tại ở phiên shell hiện tại.

```bash
export BASE_URL='https://<ten-web-service>.onrender.com'
read -rsp 'AGENT_API_KEY: ' AGENT_API_KEY; echo

curl -i "$BASE_URL/health"
curl -i "$BASE_URL/ready"
curl -i -X POST "$BASE_URL/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'
curl -i -X POST "$BASE_URL/ask" -H "X-API-Key: $AGENT_API_KEY" -H 'Content-Type: application/json' -d '{"question":"Hello"}'

unset AGENT_API_KEY
```

Kết quả cần ghi sau khi chạy: `/health` **200**, `/ready` **200**, `/ask` thiếu key **401**, `/ask` có key **200**. Chỉ đánh dấu đạt khi có response thực tế; lần đầu trên gói Free có thể cần chờ service khởi động.

## Bằng chứng giao diện

- [ ] `screenshots/dashboard.png` — Render Dashboard hiển thị cả web service và Key Value.
- [ ] `screenshots/running.png` — web service trạng thái Live và URL public.
- [ ] `screenshots/test.png` — kết quả gọi endpoint từ public URL.
