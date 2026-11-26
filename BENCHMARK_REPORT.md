# Benchmark & Observability Report — Day 14

> Số liệu CP7 lấy từ các JSON trong `reports/`. Các mục observability và scaling production sẽ điền từ CSV, trace, log và screenshot của CP8.

**Họ tên:** Nguyễn Văn Hiếu
**Ngày chạy:** 26/11/2026
**Môi trường:** Windows + WSL, Python 3.11.18 trong `.venv`; agent local qua `127.0.0.1:8001` (v1) và `:8002` (v2). Mock LLM, không gọi API trả phí.

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | ≤ 500 ms | Ngưỡng mặc định của `load_test.py`; giới hạn thời gian chờ của phần lớn request. |
| Error rate `/ask` | ≤ 2% | Ngưỡng mặc định của `load_test.py`; dành error budget nhỏ cho lỗi thoáng qua. |
| Accuracy trên golden dataset | 100% sau sửa KB | CP7 yêu cầu quality gate cuối đạt 23/23 câu và không regression. |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.39 | 188.1 | 219.6 | 1684.9 | 0.33% | PASS |
| 10 | 36.62 | 187.7 | 221.6 | 1678.4 | 0% | PASS |
| 50 | 98.99 | 218.1 | 457.6 | 1723.1 | 1.00% | PASS |
| 100 | 52.81 | 568.0 | 3923.9 | 4493.9 | 2.33% | FAIL |

**Nhận xét:** RPS tăng từ 4.39 ở concurrency 1 lên 98.99 ở 50, rồi giảm còn 52.81 ở 100. Vì vậy throughput không tăng tuyến tính: ở mức 100, request xếp hàng và tail latency khiến p95 lên 3923.9 ms; error rate 2.33% cũng vượt SLO 2%. Mỗi mức dùng 300 request, `MOCK_SLOW_RATE=0.03` và `MOCK_ERROR_RATE=0.01` (mặc định), nên số đo có biến động ngẫu nhiên. JSON gốc: `reports/load_v2_c*.json`.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 189.3 | 217.5 | 239.7 |
| 0.03 (mặc định) | 215.6 | 221.5 | 1665.6 |
| 0.1 | 333.5 | 1680.7 | 1704.9 |

**Nhận xét:** Ba lượt cùng concurrency 20, 300 request và `MOCK_ERROR_RATE=0` để tách riêng tác động của slow rate. Khi tăng từ 0 lên 0.03, p99 nhảy từ 239.7 lên 1665.6 ms trong khi avg chỉ tăng 26.3 ms. Khi tăng lên 0.1, p95 cũng nhảy lên 1680.7 ms, vượt SLO 500 ms; p50 vẫn quanh 190 ms. Average che khuất nhóm người dùng chịu request rất chậm; p95/p99 phản ánh nhóm đó rõ hơn. JSON gốc: `reports/load_v2_slow_*.json`.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.35% (1/23) | 91.30% (21/23) | 100% (23/23) |
| Avg tokens / câu | 57.0 | 109.1 | 114.3 |
| Tổng cost (USD) | 0.000402 | 0.000762 | 0.000796 |
| Cost / câu đúng (USD) | 0.00040215 | 0.00003627 | 0.00003462 |
| Quality gate | FAIL (≥80%) | PASS (≥80%) | PASS (≥100%, 0 regression) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm entry JWT/API key: token JWT có hạn sử dụng và cần kiểm tra chữ ký. |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm entry Kubernetes HPA: scale theo CPU, memory hoặc custom metrics. |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:** V2 thêm retrieval nên p95 eval từ 189.8 lên 217.9 ms, tổng cost từ 0.000402 lên 0.000762 USD. Đổi lại, số câu đúng tăng từ 1 lên 21; cost/câu đúng giảm khoảng 11 lần. Sau sửa KB, số câu đúng đạt 23/23, p95 222.9 ms và không có regression so với v2 ban đầu. Đây là cost mô phỏng dựa trên token ước lượng trong mock, không phải hóa đơn API. Eval cuối chạy với `MOCK_ERROR_RATE=0` để loại nhiễu lỗi ngẫu nhiên. JSON gốc: `reports/eval_v1.json`, `eval_v2.json`, `eval_v2_fixed.json`.

**Quality gate trong CI:** Khởi động agent v2 rồi chạy `python eval/run_eval.py --url http://127.0.0.1:8002 --min-accuracy 1.0 --baseline reports/eval_v2.json --out reports/eval_v2_fixed.json`. Job phải kiểm tra exit code: `0` cho merge, `1` thì chặn merge. Baseline là kết quả v2 trước khi sửa KB; script so sánh từng ID đã đúng trước đó và chặn nếu câu nào bị regression. Không chạy CI thực tế trong lượt đo này.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] `screenshots/grafana-dashboard.png`: Dashboard Grafana khi đang có tải (Golden Signals).
- [x] `screenshots/jaeger-slow-trace.png`: trace chậm `70d885ec363a3a6d3451c42ec1cb54ad`.
- [x] `screenshots/jaeger-error-trace.png`: trace lỗi `9dd14e4c6eb555d6493b17842edb0549`, phần Details hiển thị event `exception` và upstream mock 503.
- [x] `screenshots/prometheus-alert-firing.png`: trang Prometheus Alerts hiển thị đồng thời `AgentHighErrorRate` và `AgentHighLatencyP95` ở trạng thái Firing. API cũng xác nhận cả hai cùng firing trong lượt đo lúc 20:44:06 (GMT+7).

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | 92 giây từ lúc đổi config đến lần đầu quan sát firing | Error rate `/ask` |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | 152 giây từ lúc đổi config đến lần đầu quan sát firing | Latency p95 `/ask` |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` | 166 giây từ lúc đổi config đến lần đầu quan sát firing | Cost burn rate; LLM latency |
| D | `docker pause` 1 instance | `AgentInstanceDown` | 45 giây từ lúc pause đến lần đầu quan sát firing | Instances up |
| E | `AGENT_VERSION=v1` | Không có alert chất lượng; alert cost từ C còn firing vì cửa sổ 5 phút | Không áp dụng | Retrieval hit ratio; phiên bản đang chạy |

**Phương pháp:** A/B bật đồng thời trên ba agent lab lúc 20:41:23 (GMT+7), giữ Locust 30 users trong 3 phút. Prometheus API ghi cả hai `pending` lúc 20:42:20; A `firing` lúc 20:42:55, B lúc 20:43:55. Lúc 20:44:06, API báo error rate 20.67% và p95 1.878 giây. Các mốc firing là lần đầu polling 5 giây quan sát được, không phải thời điểm Prometheus nội bộ chuyển trạng thái chính xác. D dùng một agent bị pause lúc 20:45:37, `pending` lúc 20:45:52, `firing` lúc 20:46:22 rồi đã unpause. Timeline gốc: `reports/alert_timeline.jsonl`, `reports/instance_alert_timeline.jsonl`.

C đổi model lúc 20:48:01, giữ Locust 20 users trong 3 phút; alert cost `pending` lúc 20:48:52, `firing` lúc 20:50:47. API sau đó báo burn rate 10.95 USD/giờ theo **giá mô phỏng**. Timeline: `reports/cost_alert_timeline.jsonl`. E chạy agent v1 production trên cùng golden dataset: **1/23**, quality gate 100% FAIL, dù `/health` vẫn 200. Đổi lại v2 với KB đã sửa: **23/23**, 0 regression, quality gate PASS. JSON: `reports/eval_prod_v1.json`, `reports/eval_prod_v2_fixed.json`. Sau thí nghiệm, stack đã được khôi phục về v2, model nhỏ, `MOCK_ERROR_RATE=0.01`, `MOCK_SLOW_RATE=0.03`.

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Chạy eval golden dataset theo lịch và trước deploy; chặn release khi accuracy giảm hoặc có regression theo từng ID. Metric hạ tầng như latency, error rate hay CPU không đo được chất lượng câu trả lời. Có thể theo dõi retrieval hit ratio để phát hiện tín hiệu bất thường, nhưng phải xác nhận bằng eval chất lượng.

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: `70d885ec363a3a6d3451c42ec1cb54ad`
- Tổng thời gian: 1756.0 ms
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (1727.3 ms, 98.4%). Span retrieval chỉ 22.7 ms.
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts":"2026-11-26T13:36:06.147983+00:00","level":"INFO","service":"observable-agent","instance":"5e216a190a78","event":"llm_call","trace_id":"70d885ec363a3a6d3451c42ec1cb54ad","span_id":"4058ca4904bc2c54","request_id":"fd654b556b57","model":"mock-llm-small","agent_version":"v2","input_tokens":83,"output_tokens":44,"cost_usd":3.9e-05,"llm_ms":1691.6}
```

Trace lỗi `9dd14e4c6eb555d6493b17842edb0549` có status error trên `chat mock-llm-small` và `agent.run`, event `exception` ở cả hai span. Log tương ứng ghi `event=llm_error`, lỗi upstream mock 503.

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 60.03 | 200 | 320 | 1700 | 71/7171 `/ask` |
| 3 | 60.61 | 190 | 230 | 1700 | 86/7237 `/ask` |

**Giải thích kết quả:** Ba instance cải thiện p95 `/ask` từ 320 xuống 230 ms (giảm 28.1%), nhưng RPS chỉ từ 60.03 lên 60.61 (tăng khoảng 1%). Nút thắt chính là thời gian mock LLM và nhịp nghỉ 0.5–2 giây của người dùng Locust, chứ không phải số process phục vụ HTTP. Trace chậm cho thấy span LLM chiếm 98.4% thời gian. Cả hai lượt dùng 100 users, ramp 10 users/s, 2 phút, cùng mock mặc định. Lượt ba instance dùng `docker compose run --no-deps` để Compose không đưa số agent về mặc định; log từng instance xác nhận cả ba đã phục vụ request. Bảng lấy trực tiếp từ `benchmark-results/scale_1_stats.csv` và `scale_3_stats.csv`; Locust có thể in vài request cuối sau lúc CSV flush nên số trong console lệch nhẹ.

---

## 6. Kết luận

- 3 điều rút ra:
  1. p99 phát hiện request chậm khi tỉ lệ slow mới 3%, còn p95 chỉ tăng mạnh khi slow rate lên 10%.
  2. V2 tốn thêm token và latency nhưng cost trên mỗi câu đúng thấp hơn rõ rệt; quality gate bắt được hai lỗ hổng KB trước deploy.
  3. Scale ba instance giảm p95 trong phép đo này, nhưng throughput gần như giữ nguyên; trace chỉ ra latency mock LLM là phần lớn thời gian xử lý.
- Với production thật, thêm synthetic check từ ngoài load balancer, đo tỉ lệ 502/504 ở Nginx và cảnh báo khi eval accuracy giảm. Metrics chỉ đếm request mà agent nhìn thấy nên không đủ để phát hiện lỗi ở gateway hay chất lượng câu trả lời.
