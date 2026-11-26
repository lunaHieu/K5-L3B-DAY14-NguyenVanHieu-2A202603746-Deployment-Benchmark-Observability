# Day 14 Lab — Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns trong bản develop

1. `01-localhost-vs-production/develop/app.py:17-18`: API key và URL database được ghi trực tiếp trong mã nguồn. Nếu là secret thật, người có quyền đọc repo sẽ thấy chúng và không thể thay đổi theo môi trường mà không sửa code.
2. `app.py:34`: app in API key ra log. Log có thể được thu thập và chia sẻ rộng hơn mã nguồn, làm lộ credential.
3. `app.py:21-22`: `DEBUG` và `MAX_TOKENS` được đặt cố định; cấu hình không lấy từ biến môi trường.
4. `app.py:33-38`: dùng `print()` để ghi log thay cho log có cấu trúc, gây khó lọc và phân tích khi chạy nhiều instance.
5. `app.py:25-38`: chỉ có `/` và `/ask`, không có endpoint `/health` hoặc `/ready` để nền tảng kiểm tra trạng thái.
6. `app.py:51`: server chỉ bind vào `localhost`, nên không nhận kết nối từ ngoài container.
7. `app.py:52`: port cố định là `8000`, không nhận `PORT` do nền tảng cloud cấp.
8. `app.py:53`: bật `reload=True` mọi lúc, phù hợp phát triển nhưng không phải chế độ chạy production.
9. File không có lifespan shutdown hoặc xử lý tắt dịch vụ để dọn tài nguyên và hoàn tất request đang xử lý.

### Exercise 1.2: Chạy bản develop

Đã chạy `python app.py` trong `01-localhost-vs-production/develop/`, sau đó gọi từ terminal WSL thứ hai:

```text
POST http://127.0.0.1:8000/ask?question=Hello
HTTP/1.1 200 OK
{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}

GET http://127.0.0.1:8000/health
HTTP/1.1 404 Not Found
```

Kết luận: agent trả lời được trên localhost, nhưng thiếu health check. Đây mới là bằng chứng chạy bản develop, chưa phải kiểm thử bản production.

### Exercise 1.3: So sánh develop và production

| Tính năng | Develop | Production | Vì sao quan trọng? |
| --- | --- | --- | --- |
| Cấu hình và secret | Giá trị cố định trong `app.py` | `config.py` đọc biến môi trường | Tách cấu hình khỏi code, đổi được theo môi trường và tránh commit secret. |
| Địa chỉ và cổng | `localhost:8000` cố định | `0.0.0.0` và `PORT` từ môi trường | Container/cloud có thể nhận kết nối và dùng cổng được cấp. |
| Health/readiness | Không có | Có `GET /health` và `GET /ready` | Nền tảng biết process còn sống và đã sẵn sàng nhận traffic. |
| Logging | `print()` và in cả key | Dùng `logging`, ghi sự kiện request/response | Dễ truy tìm sự kiện; không nên ghi secret vào log. |
| Shutdown | Không có lifecycle shutdown | Có lifespan startup/shutdown | Có chỗ đóng tài nguyên và phối hợp tắt dịch vụ. |
| Debug reload | Luôn bật | Phụ thuộc biến `DEBUG` | Tránh chạy trình theo dõi file trong môi trường production. |

**Bằng chứng runtime bản production:** đã chạy `ENVIRONMENT=staging DEBUG=false python app.py` trong `01-localhost-vs-production/production/`. Kết quả `curl`:

```text
GET http://127.0.0.1:8000/health
HTTP/1.1 200 OK

GET http://127.0.0.1:8000/ready
HTTP/1.1 200 OK

POST http://127.0.0.1:8000/ask
Content-Type: application/json
Body: {"question":"Hello"}
HTTP/1.1 200 OK
{"question":"Hello","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.","model":"gpt-4o-mini"}
```

Terminal không hiển thị body của `/health` và `/ready`, nên ở đây chỉ ghi các mã HTTP đã quan sát được. So với bản develop, bản production có thêm cả hai endpoint vận hành và chấp nhận JSON body cho `/ask`.

## Part 2: Docker

### Exercise 2.1: Đọc Dockerfile cơ bản

1. **Base image:** `python:3.11` (`02-docker/develop/Dockerfile:8`), gồm Python và môi trường nền cần để chạy ứng dụng.
2. **Working directory:** `/app` (`Dockerfile:10`); các lệnh `COPY`, `RUN`, `CMD` sau đó làm việc với thư mục này trong container.
3. **Vì sao copy `requirements.txt` trước mã nguồn:** Docker có thể dùng lại layer cài thư viện khi chỉ sửa `app.py`; không cần chạy lại `pip install` nếu dependency không đổi (`Dockerfile:14-24`).
4. **`CMD` và `ENTRYPOINT`:** `CMD` đặt lệnh hoặc tham số mặc định, có thể bị thay bằng command truyền cho `docker run`; `ENTRYPOINT` đặt chương trình chính, command truyền sau tên image thường trở thành tham số của chương trình đó. Dockerfile này dùng `CMD ["python", "app.py"]`.

### Exercise 2.2: Build và chạy image develop

Docker CLI và daemon hoạt động trong phiên WSL mới (`docker info` in phiên bản `29.8.1`). Lần build đầu chưa tạo được image vì Docker Hub trả `429 Too Many Requests` khi lấy metadata cho `python:3.11`. Sau đó đã tải bản Python Official Image từ Docker ECR, gắn tag cục bộ `python:3.11` và build lại bằng Dockerfile gốc, không sửa file trong repo.

```text
docker images my-agent:develop
my-agent:develop  c2408295180f  1.67GB

docker image inspect my-agent:develop --format '{{.Size}}'
1667800504 bytes (1667.8 MB theo hệ thập phân)

POST http://127.0.0.1:8000/ask?question=What%20is%20Docker%3F
HTTP/1.1 200 OK
{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

### Exercise 2.3: Multi-stage build và so sánh image

`02-docker/production/Dockerfile` có hai stage: `builder` cài dependencies, `runtime` chỉ nhận phần cần chạy. Stage runtime dùng `python:3.11-slim`, tạo user không phải root, có healthcheck và chạy uvicorn. Bản develop dùng `python:3.11` đầy đủ trong một stage. Cả hai base image được lấy từ bản phân phối Python Official Image trên ECR do Docker Hub trả 429; Dockerfile gốc không bị sửa.

| Image | Kích thước từ `docker images` | Kích thước từ `docker image inspect` |
| --- | ---: | ---: |
| `my-agent:develop` | 1.67 GB | 1,667,800,504 byte |
| `my-agent:advanced` | 240 MB | 239,815,410 byte |

Tính theo byte của `docker image inspect`, image advanced nhỏ hơn **85.62%** so với develop: `(1 - 239815410 / 1667800504) × 100`.

Đã chạy `my-agent:advanced` và gọi API thật:

```text
GET http://127.0.0.1:8000/health
HTTP/1.1 200 OK
{"status":"ok","uptime_seconds":94.2,"version":"2.0.0","timestamp":"2026-11-26T08:33:04.632285"}

POST http://127.0.0.1:8000/ask
Content-Type: application/json
Body: {"question":"What is Docker?"}
HTTP/1.1 200 OK
{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

### Exercise 2.4: Docker Compose stack

Đã tạo file `02-docker/production/.env.local` rỗng (được `.gitignore` loại trừ) rồi chạy Compose với project name `k5-day14-docker`. `docker compose config --services` liệt kê `qdrant`, `redis`, `agent`, `nginx`. Compose có cảnh báo `version` đã cũ nhưng vẫn đọc cấu hình. Lần `up` đầu bị Docker Hub trả 429 khi tải Qdrant; sau khi tải Qdrant từ GHCR và Nginx từ ECR rồi gắn tag cục bộ, stack khởi động được mà không sửa Compose.

```text
Client --HTTP :80--> Nginx --proxy--> Agent :8000
                                   |-- REDIS_URL --> Redis :6379
                                   `-- QDRANT_URL -> Qdrant :6333
```

Nginx là cổng công khai; agent, Redis và Qdrant chỉ ở mạng Compose nội bộ. Compose cấp `REDIS_URL` và `QDRANT_URL` cho agent, nhưng `02-docker/production/main.py` hiện chưa sử dụng hai dịch vụ này trong logic `/ask`.

Trạng thái `docker compose ps`: cả bốn service `agent`, `nginx`, `qdrant`, `redis` đều `running`; agent, Qdrant và Redis đều `healthy`.

```text
GET http://127.0.0.1/health (qua Nginx)
HTTP/1.1 200 OK
Server: nginx
{"status":"ok","uptime_seconds":19.5,"version":"2.0.0","timestamp":"2026-11-26T08:38:28.397296"}

POST http://127.0.0.1/ask (qua Nginx)
Content-Type: application/json
Body: {"question":"Explain microservices"}
HTTP/1.1 200 OK
Server: nginx
{"answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

## Part 3: Cloud Deployment

### Exercise 3.1/3.2: So sánh Railway và Render

Ban đầu thử Railway: đã tạo project và Redis nhưng Redis báo `Failed`; lệnh thêm agent bị Railway từ chối với thông báo workspace bị giới hạn và yêu cầu nâng gói. Vì vậy chuyển sang **Render** theo lựa chọn còn lại của CP6; chưa có public URL hoặc kết quả API cloud. `06-lab-complete/railway.toml` là TOML cấu hình **build bằng Dockerfile** và health check `/health`; Redis và biến môi trường phải tạo riêng trên Railway. `06-lab-complete/render.yaml` là YAML Blueprint mô tả web service Docker cùng Key Value (Redis-compatible), region, gói free, health check và các biến môi trường. Render Blueprint có thể khai báo hai service trong một file, còn Railway config hiện tại tập trung vào cách build/vận hành agent. Cả hai đều giữ giá trị secret ngoài mã nguồn.

### Exercise 3.3: Pipeline Cloud Run (đọc cấu hình mẫu)

`cloudbuild.yaml` chạy test trước, rồi build Docker image với tag commit SHA và `latest`.
Sau khi test/build thành công, pipeline push image lên registry rồi deploy bản có tag SHA lên Cloud Run.
`service.yaml` mô tả service Cloud Run: giới hạn 1–10 instance, concurrency 80, CPU/RAM và liveness `/health`, startup `/ready`.
Secret được tham chiếu từ Secret Manager thay vì ghi trực tiếp vào file; chưa triển khai GCP trong bài này.

## Part 4: API Security

### Exercise 4.1: API key authentication (bản develop)

`04-api-gateway/develop/app.py` dùng `APIKeyHeader(name="X-API-Key", auto_error=False)` và `verify_api_key()` làm dependency cho `POST /ask`. Bản demo được chạy với `AGENT_API_KEY=secret-key-123`. Kết quả học viên đo bằng `curl -i`:

```text
POST /ask, không gửi X-API-Key
HTTP/1.1 401 Unauthorized
{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

POST /ask, X-API-Key: secret-key-123
HTTP/1.1 200 OK
{"question":"Hello","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

Muốn đổi key thì đặt lại biến môi trường `AGENT_API_KEY` khi khởi động service và cập nhật key cho client; không sửa key trong mã nguồn.

### Exercise 4.2: JWT authentication (bản production)

`POST /auth/token` xác thực tài khoản demo `student` rồi phát JWT HS256, có `sub`, `role`, `iat`, `exp` và hạn 60 phút. Client gửi token trong `Authorization: Bearer <token>`; dependency `verify_token()` kiểm chữ ký và hạn dùng trước khi vào `/ask`. Token được giữ trong biến shell `$TOKEN` và không dán vào bài.

Kết quả `curl -i` của học viên trên bản production:

```text
POST /ask, không có Authorization
HTTP/1.1 401 Unauthorized
www-authenticate: Bearer
{"detail":"Authentication required. Include: Authorization: Bearer <token>"}

POST /ask, Authorization: Bearer <token đã che>
HTTP/1.1 200 OK
{"question":"What is Docker?","answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!","usage":{"requests_remaining":9,"budget_remaining_usd":1.9e-05}}
```

### Exercise 4.3: Rate limiting

`rate_limiter.py` dùng cửa sổ trượt 60 giây: lưu thời điểm request theo từng user trong `deque`, bỏ các mốc cũ rồi kiểm số request còn trong cửa sổ. Role `user` được tối đa **10 request/phút**; role `admin` được **100 request/phút** qua limiter riêng. Admin không hoàn toàn bỏ qua giới hạn, mà có hạn mức cao hơn. Khi vượt, code trả HTTP 429 cùng `Retry-After`, `X-RateLimit-Limit`, `X-RateLimit-Remaining` và `X-RateLimit-Reset`.

Học viên gửi 20 request liên tiếp bằng JWT của `student`: request **01–09 trả 200**, request **10–20 trả 429**. Trước vòng lặp đã có một request thành công bằng cùng token, nên request 10 của vòng lặp chính là request thứ 11 trong cửa sổ. Kết quả này xác nhận giới hạn 10 request/60 giây trên instance đã chạy.

Output `curl -i` riêng của học viên khi vượt giới hạn (đã che token):

```text
POST /ask, Authorization: Bearer <token đã che>
HTTP/1.1 429 Too Many Requests
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
x-ratelimit-reset: 1795683015
retry-after: 59
{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

### Exercise 4.4: Cost guard

Trong `cost_guard.py` hiện có bản demo **in-memory, theo ngày**: tính chi phí input/output token theo đơn giá mẫu, theo dõi mỗi user và tổng toàn hệ thống. `/ask` gọi `check_budget()` trước mock LLM, rồi `record_usage()` sau khi có câu trả lời. Mốc cảnh báo là 80% ngân sách; đạt $1/ngày của user thì trả 402, đạt $10/ngày toàn hệ thống thì trả 503. Token count ở `/ask` hiện là ước lượng từ số từ, chưa phải usage thật từ nhà cung cấp LLM.

Để làm yêu cầu **$10/user/tháng với Redis** của Exercise 4.4: tạo key `budget:<user_id>:<YYYY-MM>`; trước request tính `estimated_cost`, đọc số đã dùng và chỉ cho gọi nếu `used + estimated_cost <= 10`; sau khi biết chi phí thực thì cập nhật số đã dùng, đặt TTL tới đầu tháng sau. Phần kiểm tra và giữ ngân sách phải thực hiện nguyên tử (ví dụ Lua script/transaction trong Redis) để các instance không cùng vượt hạn mức khi nhận request đồng thời. Cần xử lý chênh lệch giữa ước tính và chi phí thực, hoàn lại phần đã giữ khi gọi LLM thất bại. Rate limit chặn tốc độ gọi trong một phút; cost guard chặn tổng chi tiêu dù request được gửi chậm.

Trường `budget_remaining_usd` trong response 200 hiện lấy `usage.total_cost_usd`, tức **chi phí đã dùng**, dù tên trường nói “còn lại”. Muốn xem số dư đúng của bản demo, dùng `GET /me/usage` và trường `budget_remaining_usd` tại endpoint đó.

## Part 5: Scaling & Reliability

### Exercise 5.1: Health checks

Đã chạy `05-scaling-reliability/develop/app.py` trong WSL. Kết quả `curl -i` của học viên:

```text
GET /health
HTTP/1.1 200 OK
{"status":"ok","uptime_seconds":10.8,"version":"1.0.0","environment":"development","timestamp":"2026-11-26T08:51:36.669041+00:00","checks":{"memory":{"status":"ok","used_percent":30.4}}}

GET /ready
HTTP/1.1 200 OK
{"ready":true,"in_flight_requests":1}
```

Liveness (`/health`) báo process còn hoạt động; readiness (`/ready`) báo instance đã sẵn sàng nhận traffic. Giá trị `in_flight_requests: 1` bao gồm chính request đang gọi `/ready` vì middleware tăng bộ đếm trước khi endpoint chạy.

### Exercise 5.2: Graceful shutdown

Lần thử đầu: gửi hai `POST /ask` song song rồi SIGTERM sau 0,5 giây. Một request trả HTTP 200, request thứ hai lỗi `curl: (56) Recv failure: Connection reset by peer`. Kiểm tra mã nguồn thấy mock LLM gọi `time.sleep()` trực tiếp trong route `async`, khiến event loop bị chặn khi xử lý request. Đây là nguyên nhân có khả năng dẫn tới lỗi quan sát được. Đã đổi lời gọi mock sang `await asyncio.to_thread(ask, question)` trong bản develop để hai request có thể xử lý đồng thời.

Lần thử lại: học viên gửi hai request song song, gửi SIGTERM tới process `5703` sau 0,5 giây. **Cả hai request trả HTTP 200**; log server ghi `Waiting for connections to close`, hai dòng `POST /ask ... 200 OK`, rồi mới `Application shutdown complete` và `Finished server process [5703]`. Như vậy hai request đang xử lý đã hoàn thành trước khi process thoát trong lần thử này.

### Exercise 5.3: Stateless design

Nếu lịch sử hội thoại chỉ nằm trong dictionary RAM của instance A, request kế tiếp được Nginx chuyển sang instance B sẽ không thấy lịch sử đó. Mã `05-scaling-reliability/production/app.py` tạo `session_id`, lưu session bằng key `session:<session_id>` trong Redis với TTL 3600 giây và đọc lại bằng cùng key. Vì các agent cùng nối tới Redis qua `REDIS_URL=redis://redis:6379/0`, một session có thể tiếp tục trên instance khác. Mã có fallback sang dictionary RAM khi Redis không kết nối được; khi kiểm chứng Exercise 5.5 phải xác nhận response báo `storage: redis`, nếu không kết quả không chứng minh stateless.

### Exercise 5.4: Load balancing

Học viên chạy Compose project `k5-day14-scaling` với `--scale agent=3`. `docker compose ps` cho thấy ba agent `Up ... (healthy)`, Redis `Up ... (healthy)` và Nginx `Up` tại cổng 8080. Gọi `GET /health` qua Nginx trả HTTP 200, có header `X-Served-By: 172.26.0.5:8000` và body:

```json
{"status":"ok","instance_id":"instance-101cd9","uptime_seconds":102.4,"storage":"redis","redis_connected":true}
```

Nginx chuyển request đến các agent; output `test_stateless.py` cho thấy năm request được phục vụ lần lượt bởi `instance-e5068c`, `instance-7a8cf3`, `instance-101cd9`, `instance-e5068c`, `instance-7a8cf3`. Cả ba instance đều nhận request trong lần thử này.

### Exercise 5.5: Kiểm tra stateless

`python test_stateless.py` gửi năm câu hỏi trong cùng session `17e1ad4c-1953-4b87-9640-2a7c52c1d049`, qua ba instance nói trên. Endpoint history trả `Total messages: 10`, gồm đủ năm message `user` và năm message `assistant` theo thứ tự. Kết hợp với `/health` báo `storage: redis` và `redis_connected: true`, kết quả xác nhận session dùng chung hoạt động qua nhiều instance. Script này không tắt một instance; bằng chứng hiện có là chuyển tiếp session giữa các instance đang chạy.

## Part 6: Final Project

Đã chạy `python check_production_ready.py` **đầy đủ trong WSL** tại `06-lab-complete/`. Script tự chạy agent với hai worker, dùng container Redis tạm thời và build Docker image. Kết quả học viên cung cấp: image **273 MB**, build **19 giây**; rate limit trả 429 sau 5 request thành công và còn hiệu lực sau restart; cost guard trả 402 ở request thứ 2 với budget thử nghiệm; log có 12 dòng JSON hợp lệ; SIGTERM giữ request đang xử lý trả 200, process exit 0; `docker stop` exit 0 trong **0,9 giây**. Các số liệu này lấy từ output script, không phải đo độc lập ngoài script.

Phần **📋 Checklist Deliverable** trong output:

```text
📋 Checklist Deliverable
   ✅ Dockerfile (multi-stage, < 500 MB)
   ✅ docker-compose.yml (agent + redis)
   ✅ .dockerignore
   ✅ Health check endpoint (GET /health)
   ✅ Readiness endpoint (GET /ready)
   ✅ API Key authentication
   ✅ Rate limiting
   ✅ Cost guard
   ✅ Config từ environment variables
   ✅ Structured logging
   ✅ Graceful shutdown
   ✅ Public URL ready (Railway / Render config)
Result: 12/12 tiêu chí đạt · 41/41 checks passed
🎉 PASS 12/12 — PRODUCTION READY!
```

## AI log

| Mục | Nội dung |
| --- | --- |
| Đã hỏi AI | Đọc yêu cầu Day 14, lập kế hoạch và hỗ trợ thực hiện CP1; phân tích mã develop/production và diễn giải kết quả `curl`. |
| AI hỗ trợ | Đề xuất lệnh chạy trong WSL, nhận diện anti-pattern, soạn bảng so sánh và ghi bằng chứng vào file này. |
| Tự chạy và kiểm tra | Học viên chạy agent develop và production trong WSL, rồi gọi `curl`: develop `/ask` 200, `/health` 404; production `/health`, `/ready`, `/ask` đều 200. Response `/ask` production được chép nguyên từ terminal. |

**CP2:** AI giải thích bốn câu Dockerfile của Exercise 2.1 và hỗ trợ chẩn đoán lỗi quyền Docker socket, sau đó lỗi Docker Hub `429 Too Many Requests`. Học viên đã kiểm tra bằng phiên WSL mới: thuộc nhóm `docker`, `docker info` in `29.8.1`; sau khi dùng bản Python Official Image từ ECR, image develop build và trả lời được. Kích thước image được đọc từ `docker image inspect`, response được học viên gửi từ `curl`.

**CP2 tiếp:** AI tính phần trăm giảm image từ hai số byte đo bằng Docker và soạn so sánh multi-stage. Học viên build và chạy `my-agent:advanced`, cung cấp output `docker images`, `inspect`, `/health` và `/ask`; số liệu và response phía trên lấy từ output này.

**CP2 Compose:** AI hướng dẫn dùng project name riêng, chẩn đoán Docker Hub 429 và tìm image Qdrant/Nginx ở registry công khai. Học viên chạy Compose và gửi output hai lệnh `curl` qua Nginx; AI đọc `docker compose ps` để xác nhận trạng thái bốn service. Không sửa Dockerfile hoặc Compose mẫu.

**CP3, Exercise 4.1:** AI xác định đường đi auth trong code và soạn phần giải thích. Học viên chạy hai lệnh `curl -i` ở bản develop, quan sát 401 khi thiếu key và 200 với key demo; các response phía trên lấy từ output học viên gửi.

**CP3, Exercise 4.2–4.4:** AI đọc `auth.py`, `rate_limiter.py`, `cost_guard.py` và diễn giải JWT, giới hạn tốc độ, cách thiết kế ngân sách Redis. Học viên tự lấy JWT trong WSL, chạy `curl -i` quan sát 401/200 và vòng lặp 20 request quan sát 200/429. Không đưa token vào báo cáo; không nhận các con số ngân sách demo là đo lường chi phí LLM thật.

**CP3, bằng chứng 429:** Học viên chạy thêm `curl -i` khi đã dùng hết 10 request trong cửa sổ; AI chép mã 429, các header rate limit và body từ output thật vào Exercise 4.3.

**CP4, Exercise 5.1:** AI hướng dẫn chạy bản develop của Part 5 và kiểm tra hai probe. Học viên gửi output `curl -i` cho `/health` và `/ready`, đều HTTP 200; AI ghi nguyên các giá trị quan sát được ở trên.

**CP4, Exercise 5.2:** Học viên chạy hai request song song rồi SIGTERM, quan sát một HTTP 200 và một lỗi reset. AI phát hiện lời gọi `time.sleep()` trong route `async` chặn event loop và sửa sang `asyncio.to_thread()`. Học viên tự khởi động lại server, thử lần nữa: hai request đều HTTP 200; log ghi hoàn tất response trước khi shutdown.

**CP4, Exercise 5.3–5.5:** AI đọc mã Redis session, Nginx và script test, hướng dẫn Compose project riêng. Học viên chạy stack ba agent và gửi output `docker compose ps`, `/health`, `test_stateless.py`: ba agent healthy, Redis healthy, storage thực là Redis, năm request đi qua ba instance và history đủ 10 message. AI ghi lại số liệu từ output này.

**CP5, chuẩn bị:** AI đọc bảng tiêu chí Part 6 và mã khung, điền các TODO trong `06-lab-complete/`: cấu hình môi trường, auth API key, Redis client, sliding window rate limit bằng Lua, cost guard theo ngày, health/readiness, log JSON, lifespan shutdown, Dockerfile multi-stage, Compose, `.dockerignore`, `.env.example` và Railway config. Không sửa `check_production_ready.py`. Kiểm tra tĩnh bằng `python -X utf8 check_production_ready.py --static-only` trên Windows: **26/26 checks tĩnh đạt**, 3/12 tiêu chí được đánh dấu ✅ ở thời điểm đó; runtime/Docker được kiểm tra ở bước tiếp theo.

**CP5, kiểm tra đầy đủ:** Học viên cài requirements trong WSL và tự chạy `python check_production_ready.py`. Output báo **PASS 12/12, 41/41 checks passed**; AI chép Checklist Deliverable và các số đo runtime/Docker từ output học viên gửi. Chưa deploy cloud hoặc xác nhận public URL.

**CP6, triển khai:** AI đọc file `railway.toml`, mẫu `render.yaml`, Cloud Run pipeline và hướng dẫn Railway hiện hành; soạn so sánh hai nền tảng và tóm tắt pipeline trong Part 3. Học viên thử Railway; project và Redis được tạo nhưng Redis báo Failed, lệnh tạo agent bị từ chối vì workspace bị giới hạn. AI chuẩn bị Render Blueprint cho web service và Key Value gói free; sau thay đổi, kiểm tra tĩnh đạt **28/28 checks**. Học viên triển khai Render và cung cấp URL public `https://k5-day14-agent-dcce.onrender.com`. AI gọi trực tiếp `/health` 200, `/ready` 200, `/ask` thiếu key 401; học viên tự gọi `/ask` có key và gửi mã HTTP 200. AI không nhận giá trị API key. Bằng chứng đầy đủ trong `DEPLOYMENT.md`; ảnh giao diện học viên sẽ tự chụp sau.

**CP7, benchmark local:** AI cài dependencies của Part 7 vào `.venv` trong WSL, chạy agent v1/v2 và các lệnh `load_test.py`, `run_eval.py` với `--out`. Kết quả thô gồm 10 JSON ở `reports/` và `develop/reports/`; AI điền bảng số liệu từ JSON vào `BENCHMARK_REPORT.md`. Eval v2 đầu đạt 21/23, sai `security-02` và `scaling-03`; AI thêm hai entry JWT và Kubernetes HPA trong knowledge base, khởi động lại v2 rồi chạy eval với baseline cũ. Kết quả cuối **23/23, quality gate PASS, không regression**. Ba phép thử slow rate dùng `MOCK_ERROR_RATE=0` để tách riêng tác động của request chậm. Các số đo cost là mô phỏng của mock LLM.

**CP8, observability local:** AI build stack Docker Compose `k5-day14-observability`, sửa Dockerfile Part 7 production vì Python runtime không tìm thấy package đã cài `--user`. AI chạy Locust headless hai lượt 100 users, 2 phút với đúng 1 và 3 agent; phát hiện `docker compose run` tự khôi phục số replica mặc định, nên dùng `run --no-deps` và xác nhận ba agent đều nhận request trước khi lưu CSV cuối. AI truy vấn Jaeger lấy trace chậm, trace lỗi có event `exception` và đối chiếu log JSON cùng `trace_id`. AI bật fault injection trong stack lab, ghi timeline Prometheus API cho `AgentHighErrorRate`, `AgentHighLatencyP95`, `AgentInstanceDown`, `LLMCostBurnRateHigh`; agent bị pause đã được unpause. Thử đổi sang v1 cho thấy eval production chỉ 1/23 dù health 200; v2 production sau đồng bộ KB đạt 23/23, không regression. Các ảnh giao diện chưa có vì học viên sẽ tự chụp sau. Stack được khôi phục về v2, model nhỏ và tỉ lệ lỗi/chậm mặc định.
