# Data and Artifact Workflow

The project uses GitHub for code and Google Drive for data/model/output artifacts.

```text
local code -> GitHub -> Colab/Kaggle
local or Drive Desktop data -> preprocess -> Google Drive Data Hub
Colab/Kaggle -> train/evaluate -> Google Drive Data Hub -> local via Drive Desktop
```

## Why this split exists

Git is good for code, small specs, tests, notebooks, and documentation. It is bad for videos,
large datasets, model weights, training logs, TensorBoard runs, and generated reports.

Google Drive is the artifact store. It holds raw data, processed data, training runs, model
artifacts, metrics, logs, and reports.

## Drive Data Hub

The CS Workspace contains:

```text
00_Data_Management/
├── 00_Registry/
├── 01_Raw_Data/
├── 02_Processed_Data/
├── 03_Training_Runs/
├── 04_Model_Artifacts/
├── 05_Reports_For_Team/
├── 06_Colab_Kaggle_Workspace/
└── 99_Archive/
```

Registry sheet:

<https://docs.google.com/spreadsheets/d/1srINZhdV7w1f6AHJ49F6IS81CvzdVtV8LQQ-Fhnw80M/edit>

## Three managed streams

| Stream | Data | Training/run output | Model/artifact |
| --- | --- | --- | --- |
| `cv_yolo` | images, videos, labels, `data.yaml` | YOLO logs, predictions, metrics | `.pt` weights, sample predictions |
| `rl_sumo` | district spec, SUMO generated files, scenarios | rollout traces, traffic metrics | RL policy checkpoint |
| `public_finance` | cost, budget, public-value assumptions | sensitivity results, investment ranking | optimizer config/report |

## Minimum run folder

Each run should have:

```text
run_config.json
metrics.json or metrics.placeholder.json
logs/
artifacts/
reports/
```

Create a local run folder:

```powershell
uv run python scripts/artifacts/prepare_run_dir.py --stream yolo --run-id RUN-YOLO-V0-001
```

TASK-096: run creation reserves the ID exclusively. A duplicate or partially created directory
fails without overwriting metadata/results. IDs must be portable single path components; API and
CLI both validate streams. A failed write keeps its reservation for inspection; choose a new ID,
since resume is not yet supported. `artifact_kind=management_scaffold` and placeholder metrics
explicitly mean this folder is not a research manifest or completed run.

## Experiment/run identity (TASK-098, M0 đang triển khai)

CLI mới nằm dưới `uv run python -m ai_quantum_hvtc experiments`: `create` tạo experiment,
`prepare-run` đóng băng một run từ request JSON, `prepare-debug` chuẩn bị run SUMO debug,
`verify-experiment` và `verify-run` kiểm tra manifest/input/output, còn `run-debug` chạy executor
fixed-time hiện có. Dùng `--help` để xem tham số từng lệnh.

`experiment_manifest.v1` và `experiment_run.v1` lưu schema, ID, đường dẫn nguồn, kích thước và
SHA-256; chúng kiểm tra project snapshot, protocol, source/config, shared profiles và input của
run. Protocol khóa version contract cùng seed/case theo các split độc lập
(`rl_train`, `rl_validation`, `coefficient_fit`, `surrogate_validation`, `final_test`). Bindings
ghim demand/routes và settings cho cặp case/seed, dữ liệu vào split, cùng checkpoint cho
controller/reward; output manifest cũng rehash artifact đã seal. Đây là kiểm tra danh tính và
toàn vẹn byte, không phải nghiệm thu khoa học.

Manifest chỉ giữ path/hash của source và data, không archive hoặc copy chúng; verifier cần các
tệp nguồn vẫn tồn tại tại đường dẫn đó. Experiment/run ID dùng reservation độc quyền, không ghi
đè. Nếu reservation thất bại hoặc dang dở, giữ lại để kiểm tra và dùng ID mới; chưa hỗ trợ resume.
Protocol có thể mô tả `research_synthetic`, nhưng execution gate hiện chỉ cho phép `debug` vì
existing-net runner chưa có intended-demand ledger và runtime safety đã xác minh. `run-debug`
chỉ chạy fixed-time debug, không chạy nghiên cứu.

Debug có thể sinh `geometry_manifest.v1` và `render_run_manifest.v1` gắn experiment/run ID.
Chúng chỉ là metadata đầu vào render: `render_executed=false`, còn thiếu traffic-light/event
traces; không khởi chạy Unreal và không chứng minh ảnh đã render.

Trong objective manifest, R0 và R1 là các reward profile riêng nhưng dùng chung evaluator profile;
reward runtime hiện tại chưa thay đổi.

Push it to Drive Desktop after training:

```powershell
uv run python scripts/cloud/drive_desktop_sync.py --drive-root "<Data Hub local path>" --apply push-run --stream yolo --run-id RUN-YOLO-V0-001 --source artifacts/runs/yolo/RUN-YOLO-V0-001
```

Without `--apply`, the sync script is a dry run.

## Colab/Kaggle pattern

1. Clone the GitHub repo.
2. Install `requirements-colab.txt`.
3. Mount or attach Google Drive/Kaggle dataset.
4. Read data from Drive Data Hub.
5. Write run outputs back to Drive Data Hub.
6. Update the registry sheet.

## DVC và quyền sở hữu dữ liệu (hợp nhất)

Git giữ code/config/docs, tiny fixtures và .dvc pointers. Git LFS giữ UE packages nhỏ.
DVC giữ hashes/version pointers cho map, traces, dataset, checkpoints và outputs lớn.
Drive Desktop có thể là storage backing; không sửa tay object store.

Repo có pointer cho raw/prepared district7_osm_seed_20260702. Giữ nguyên map này.
Remote local từng dùng D:\\AIQ_HVTC_DVC_STORE, nhưng trạng thái junction/Drive/cloud
**chưa xác minh lại ngày audit**. Collaborator dùng local path của mình, không mặc định G: tồn tại.

```powershell
dvc status
dvc remote modify --local drive_desktop url "<local Data Hub>\\00_DVC_Store"
dvc pull
dvc push --no-run-cache
```

Pull/push chỉ chạy khi cần đồng bộ, không chạy chỉ để audit docs.
Không gọi local copy hoàn tất là cloud sync đã xác nhận.

## Current limitation

M0, cập nhật 2026-09-27: TASK-096 chặn ghi đè run ID tại helper; TASK-098 thêm shared
experiment/run identity, hashes, split/pairing bindings và verifier. Hạ tầng này vẫn là identity
scaffold: source/data không được lưu trữ cùng manifest, reservation lỗi không resume, `run-debug`
chỉ là debug, và verified outputs không xác nhận chất lượng khoa học. Chưa nghiệm thu M0.
Identity retained-map đã được tạo/verify ở `artifacts/tmp/m0_identity_098/experiments/` với
98 source files và net/overlay giữ nguyên; experiment có 0 run do descriptor không có demand flows.
SUMO end-to-end test dùng toy fixture để kiểm tra lifecycle, không thay map nghiên cứu hay tạo
evidence lợi ích.
Run CLI quản lý cũ dùng yolo/rl/finance_optimizer; dataset streams dùng
cv_yolo/rl_sumo/public_finance: không hoán đổi tên tuỳ ý.

The Drive registry workflow above remains a management scaffold. Experiment manifests add artifact
identity; the first real YOLO/RL/optimizer runs will still determine useful metrics, logs, model
files, and reports. Until then, the registry rows are examples.
