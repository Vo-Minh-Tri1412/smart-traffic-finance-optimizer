# Synthetic visual sensor dataset contract

This specifies the intended Unreal RGB/depth/instance dataset and existing renderer-neutral dataset
layout/validation. It does not claim a completed UE exporter or trained YOLO model.
See [implementation status](../04_STATUS/IMPLEMENTATION_STATUS.md) and
[delivery plan](SYSTEM_DELIVERY_PLAN.md).

## Source and observation boundary

SUMO run → versioned vehicle/TLS trace → calibrated UE camera → synchronized RGB/depth/instance →
labels and visibility → optional detector → lane features with uncertainty → policy.
Ground truth may generate labels/reward/evaluation, but a detector receives pixels and a camera-based
policy receives observed features, never hidden IDs/counts or economic trip intent.

Geometry visibility is currently an offline surrogate, not an integrated RL environment.
A future online adapter must consume canonical dimensions and the current SUMO state. A prerecorded baseline trace cannot represent the traffic changed
by another policy. Offline replay is appropriate for dataset generation and detector evaluation.

## Geometry sensor và observation (hợp nhất sau audit 2026-09-20)

CV là mở rộng tùy chọn; oracle baseline không bị chặn bởi capture hay YOLO.
Geometry camera hiện rasterize canonical cuboids thành depth/instance buffer.
Pose, FOV/intrinsics, near/far, image size, cadence và target lanes thuộc camera_calibration.v1.
Đơn vị SUMO mét → UE centimet (100); x/y front bumper phải đổi về tâm cuboid.

GeometryObservationAdapter hiện lấy class/lane từ truth, confidence bằng mean visible_fraction,
unknown_count=0. Đây là surrogate chưa hiệu chỉnh, không phải detector/tracker.
Exact hidden visibility chỉ dùng label/evaluation; camera policy không được nhận nó như
confidence đo được từ ảnh. Cần tracker, queue/wait/downstream estimates, uncertainty và
time-since-last-observed; phải công bố feature availability theo sensor mode.

Occlusion phụ thuộc hình học/camera/depth; noise bổ sung sau visibility, có tương quan thời gian
và lane/camera, không chỉ xoá xe ngẫu nhiên độc lập. Chưa có calibrated noise model.
So memoryless, frame-stack 4 và recurrent theo RL protocol; không bắt buộc graph/CTDE.
Báo detection/count/queue error, tracking continuity, control degradation và safety riêng.
Camera cadence và control interval có aggregation rule rõ ràng.

## Dataset layout and provenance

Use data/processed/cv_yolo/<dataset_id>/ with images/train, images/val, labels/train, labels/val,
data.yaml, dataset_manifest.json, render_manifest.json and camera configuration.
Add depth/instance artifacts and per-frame metadata when the verified capture producer exists.
Dataset IDs, train/validation/test run membership and source checksums must be stable.

Record source SUMO run, map/demand hashes, renderer version, camera calibration, timestamp, image
size, class mapping, asset snapshot, weather/preset, visibility method and known limitations.
Split by run/day/scenario/camera, not adjacent random frames. Generated images/models stay out of
Git and use the DVC/Drive data workflow.

## Labels and physical visibility

Separate physical visual classes from simulation/economic roles. Vehicle-type metadata may include
motorbike, car, bus, truck, ambulance, worker shuttle, taxi/ride-hailing and delivery bike, but the
detector's class mapping must merge visually indistinguishable roles or mark them unknown.
Do not label an unmarked car by an invisible passenger purpose.

The camera_calibration.v1 artifact owns pose, intrinsics, image size, clipping and capture interval.
The sensor is not a free-fly camera. Use front-bumper-to-center conversion and canonical dimensions,
ground clearance and available road elevation. Missing elevation stays a declared flat assumption.

Instance identities must be stable across pooling/seek and support more than 255 active identities.
Use depth-correct visible masks; projected rectangles are not occlusion labels. Export amodal bounds
separately if needed. Test bus/truck occlusion, image-edge truncation, fully hidden objects and empty
frames. Presentation LOD must not discard sensor occluders. Noise comes after visibility.

## Unreal capture design

UE-only camera/label/assets are configured through Data Assets and scene profiles, with exported
read-only metadata snapshots. Sensor RGB and masks must agree on time and geometry; incompatible
motion blur/antialiasing must not silently contaminate labels. Start with Editor batch capture;
Movie Render Queue Object IDs are Editor-only, not promised in shipping builds.
See [asset pipeline](UNREAL_ASSET_PIPELINE.md).

## Existing template tooling

From repository root:

```powershell
uv run python scripts/data/prepare_synthetic_cv_dataset.py --dataset-id SYNTH-CV-UE-V0 --output-root data/processed/cv_yolo --init-template --validate
uv run python scripts/data/prepare_synthetic_cv_dataset.py --dataset-root data/processed/cv_yolo/SYNTH-CV-UE-V0 --validate
```

Template validation is not rendering. An empty template can pass with a warning; it is not a
training-ready dataset. Actual frames require image/label pairing, bounds, provenance and visual QA.
Use scripts/cloud/drive_desktop_sync.py push-dataset in dry-run mode before --apply, with the
configured Data Hub, stream cv_yolo, dataset ID and source directory.

The old renderer image smoke command has been retired. UE depth/instance capture, dataset-scale QA,
YOLO training and detector-error calibration remain future work. No real-camera equivalence or
closed-loop detector-control result is implied by creating a dataset folder.
