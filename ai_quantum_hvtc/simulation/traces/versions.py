"""Version identifiers for trace contracts shared by Python, Unreal, and frontend UI."""

SIMULATION_TRACE_FRAME_SCHEMA_VERSION = "simulation_trace_frame.v1"
GEOMETRY_MANIFEST_SCHEMA_VERSION = "geometry_manifest.v1"
VEHICLE_TRACE_SCHEMA_VERSION = "vehicle_trace.v2"
VISIBILITY_TRACE_SCHEMA_VERSION = "visibility_trace.v1"
TRAFFIC_LIGHT_TRACE_SCHEMA_VERSION = "traffic_light_trace.v1"
SEMANTIC_OVERLAY_SCHEMA_VERSION = "semantic_overlay.v2"
EVENT_TRACE_SCHEMA_VERSION = "event_trace.v1"
RENDER_RUN_MANIFEST_SCHEMA_VERSION = "render_run_manifest.v1"
SENSOR_DATASET_MANIFEST_SCHEMA_VERSION = "sensor_dataset_manifest.v1"

RENDER_BRIDGE_SCHEMA_VERSIONS = {
    "geometry_manifest": GEOMETRY_MANIFEST_SCHEMA_VERSION,
    "vehicle_trace": VEHICLE_TRACE_SCHEMA_VERSION,
    "visibility_trace": VISIBILITY_TRACE_SCHEMA_VERSION,
    "traffic_light_trace": TRAFFIC_LIGHT_TRACE_SCHEMA_VERSION,
    "semantic_overlay": SEMANTIC_OVERLAY_SCHEMA_VERSION,
    "event_trace": EVENT_TRACE_SCHEMA_VERSION,
    "render_run_manifest": RENDER_RUN_MANIFEST_SCHEMA_VERSION,
    "sensor_dataset_manifest": SENSOR_DATASET_MANIFEST_SCHEMA_VERSION,
}
