"""Run inside UE Editor: build and photograph an illustrative signal-corner set.

Uses real UE geometry, PBR materials, lights and GPU SceneCapture2D. No AI image
generation. All vehicles/lighting are staged, not calibrated SUMO observations.
Generated assets stay in /Game/Demo092 and the screenshot in artifacts/unreal_demo.
"""

import json
import math
import random
import time
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/unreal_demo"
OUT.mkdir(parents=True, exist_ok=True)
ASSET_DIR = "/Game/Demo092"
RNG = random.Random(92)
ACTORS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
LEVELS = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
MATS = unreal.MaterialEditingLibrary
V = unreal.Vector
R = unreal.Rotator
unreal.EditorPythonScripting.set_keep_python_script_alive(True)


def prop(obj, key, value):
    """Optional photographic settings vary slightly across engine minor versions."""
    try:
        obj.set_editor_property(key, value)
    except Exception as exc:
        unreal.log_warning(f"DEMO optional {key}: {exc}")


def material(name, color, rough=0.5, metal=0.0, emissive=0.0):
    path = ASSET_DIR + "/Materials/" + name
    mat = unreal.load_asset(path)
    if mat:
        return mat
    mat = TOOLS.create_asset(
        name, ASSET_DIR + "/Materials", unreal.Material, unreal.MaterialFactoryNew()
    )
    rgb = MATS.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector)
    rgb.set_editor_property("constant", unreal.LinearColor(*color, 1))
    MATS.connect_material_property(rgb, "", unreal.MaterialProperty.MP_BASE_COLOR)
    for val, slot in [
        (rough, unreal.MaterialProperty.MP_ROUGHNESS),
        (metal, unreal.MaterialProperty.MP_METALLIC),
    ]:
        scalar = MATS.create_material_expression(mat, unreal.MaterialExpressionConstant)
        scalar.set_editor_property("r", val)
        MATS.connect_material_property(scalar, "", slot)
    if emissive:
        glow = MATS.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector)
        glow.set_editor_property(
            "constant",
            unreal.LinearColor(color[0] * emissive, color[1] * emissive, color[2] * emissive, 1),
        )
        MATS.connect_material_property(glow, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MATS.recompile_material(mat)
    return mat


def spawn(cls, name, loc, rot=(0, 0, 0)):
    actor = ACTORS.spawn_actor_from_class(cls, V(*loc), R(*rot))
    actor.set_actor_label(name)
    return actor


def shape(name, mesh_name, loc, size, mat, rot=(0, 0, 0)):
    actor = spawn(unreal.StaticMeshActor, name, loc, rot)
    comp = actor.static_mesh_component
    comp.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/" + mesh_name))
    comp.set_material(0, mat)
    actor.set_actor_scale3d(V(*(s / 100 for s in size)))
    return actor


def box(name, loc, size, mat, rot=(0, 0, 0)):
    return shape(name, "Cube", loc, size, mat, rot)


def cylinder(name, loc, diameter, height, mat, rot=(0, 0, 0)):
    return shape(name, "Cylinder", loc, (diameter, diameter, height), mat, rot)


def lamp(name, loc, color, intensity, radius=700):
    actor = spawn(unreal.PointLight, name, loc)
    comp = actor.point_light_component
    comp.set_mobility(unreal.ComponentMobility.MOVABLE)
    comp.set_light_color(unreal.LinearColor(*color, 1))
    prop(comp, "intensity_units", unreal.LightUnits.LUMENS)
    comp.set_intensity(intensity)
    comp.set_attenuation_radius(radius)
    prop(comp, "source_radius", 18)
    prop(comp, "cast_shadows", False)
    return actor


def imported_vehicle(filename, loc, yaw, desired_length=430):
    folder = ASSET_DIR + "/Vehicles/" + filename
    assets = unreal.EditorAssetLibrary.list_assets(folder, recursive=True, include_folder=False)
    meshes = [unreal.load_asset(p) for p in assets]
    meshes = [m for m in meshes if isinstance(m, unreal.StaticMesh)]
    if not meshes:
        task = unreal.AssetImportTask()
        task.set_editor_property(
            "filename", str(ROOT / "render_assets/vehicles" / (filename + ".glb"))
        )
        task.set_editor_property("destination_path", folder)
        task.set_editor_property("automated", True)
        task.set_editor_property("save", True)
        task.set_editor_property("replace_existing", False)
        TOOLS.import_asset_tasks([task])
        assets = unreal.EditorAssetLibrary.list_assets(folder, True, False)
        meshes = [unreal.load_asset(p) for p in assets]
        meshes = [m for m in meshes if isinstance(m, unreal.StaticMesh)]
    if not meshes:
        raise RuntimeError("GLB import did not yield a mesh: " + filename)
    # Interchange bBakeMeshes=True preserves glTF node transforms in separate mesh assets.
    # Normalize the full body and place ALL parts together, including the four wheels.
    mesh = max(meshes, key=lambda m: m.get_bounds().box_extent.length())
    bounds = mesh.get_bounds()
    scale = desired_length / (2 * max(bounds.box_extent.x, bounds.box_extent.y))
    floor = min(m.get_bounds().origin.z - m.get_bounds().box_extent.z for m in meshes)
    for part in meshes:
        actor = spawn(
            unreal.StaticMeshActor,
            "Staged_" + filename + "_" + part.get_name(),
            (loc[0], loc[1], 5 - floor * scale),
            (0, yaw, 0),
        )
        actor.static_mesh_component.set_static_mesh(part)
        actor.set_actor_scale3d(V(scale, scale, scale))
        for slot in range(actor.static_mesh_component.get_num_materials()):
            actor.static_mesh_component.set_material(slot, CAR_PALETTE)
    return actor


def signal(x, y, yaw, active):
    angle = math.radians(yaw)

    def pos(a, b, z):
        return (
            x + a * math.cos(angle) - b * math.sin(angle),
            y + a * math.sin(angle) + b * math.cos(angle),
            z,
        )

    cylinder("Signal footing", (x, y, 14), 58, 28, CONCRETE)
    cylinder("Galvanized signal mast", (x, y, 295), 14, 565, STEEL)
    box("Signal backplate", pos(0, 0, 530), (76, 18, 174), BLACK, (0, yaw, 0))
    box("Signal housing", pos(0, -13, 530), (58, 34, 151), GRAPHITE, (0, yaw, 0))
    for state, z in [("red", 579), ("amber", 530), ("green", 481)]:
        mat = {"red": RED, "amber": AMBER, "green": GREEN}[state] if state == active else OFF
        cylinder("Signal optic " + state, pos(0, -34, z), 33, 8, mat, (0, yaw, 90))
        box("Signal sun visor", pos(0, -41, z + 21), (44, 48, 6), BLACK, (0, yaw, 0))
        if state == active:
            lamp(
                "Signal spill",
                pos(0, -55, z),
                (1, 0.025, 0.006) if state == "red" else (0.015, 1, 0.22),
                110,
                170,
            )
    box("Controller", pos(40, 20, 120), (40, 27, 65), STEEL, (0, yaw, 0))
    for z in (65, 115, 165):
        cylinder("Mast reflective band", (x, y, z), 14.7, 13, WHITE)


def tree(x, y, height=650):
    cylinder("Tree planter", (x, y, 18), 210, 36, CONCRETE)
    cylinder("Tree trunk", (x, y, height * 0.34), 25, height * 0.65, BARK)
    for dx, dy, dz, size in [
        (0, 0, 0, 300),
        (-110, 30, -60, 230),
        (95, 55, -35, 255),
        (30, -90, 55, 220),
    ]:
        shape(
            "Tree canopy", "Sphere", (x + dx, y + dy, height + dz), (size, size, size * 1.2), LEAF
        )


LEVELS.new_level(ASSET_DIR + "/SignalCorner_" + str(int(time.time())))
WORLD = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
ASPHALT = material("Asphalt", (0.026, 0.036, 0.047), 0.28, 0.1)
CONCRETE = material("Concrete", (0.32, 0.34, 0.33), 0.72)
WHITE = material("WarmPaint", (0.72, 0.73, 0.64), 0.45)
YELLOW = material("YellowPaint", (0.94, 0.5, 0.015), 0.4)
STEEL = material("BrushedSteel", (0.25, 0.29, 0.31), 0.28, 0.75)
BLACK = material("RubberBlack", (0.006, 0.008, 0.011), 0.55)
GRAPHITE = material("SignalHousing", (0.018, 0.024, 0.027), 0.32, 0.45)
RED = material("SignalRed", (1, 0.012, 0.003), 0.2, 0, 12)
AMBER = material("SignalAmber", (1, 0.34, 0.004), 0.2, 0, 10)
GREEN = material("SignalGreen", (0.008, 1, 0.2), 0.2, 0, 10)
OFF = material("SignalUnlitLens", (0.014, 0.022, 0.024), 0.22)
GLASS = material("BlueGlass", (0.022, 0.079, 0.11), 0.14, 0.48)
FACADE = material("WarmStone", (0.48, 0.4, 0.31), 0.65)
TEAL = material("TealFacade", (0.065, 0.15, 0.16), 0.6)
WINDOW = material("WindowGlow", (1, 0.51, 0.19), 0.25, 0, 1.8)
BARK = material("TreeBark", (0.08, 0.043, 0.02), 0.9)
LEAF = material("LeafGreen", (0.022, 0.115, 0.053), 0.8)

# The curated GLBs refer to Textures/colormap.png; use the repository's actual
# licensed palette instead of modifying source files or accepting missing texture imports.
palette_task = unreal.AssetImportTask()
palette_task.set_editor_property(
    "filename", str(ROOT / "render_assets/textures/kenney_car/colormap.png")
)
palette_task.set_editor_property("destination_path", ASSET_DIR + "/Palette")
palette_task.set_editor_property("automated", True)
palette_task.set_editor_property("save", True)
TOOLS.import_asset_tasks([palette_task])
texture = unreal.load_asset(ASSET_DIR + "/Palette/colormap")
CAR_PALETTE = material("VehiclePalette", (1, 1, 1), 0.32, 0.12)
sample = MATS.create_material_expression(CAR_PALETTE, unreal.MaterialExpressionTextureSample)
sample.set_editor_property("texture", texture)
MATS.connect_material_property(sample, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
MATS.recompile_material(CAR_PALETTE)

box("Road surface", (0, 0, -13), (18000, 18000, 26), ASPHALT)
# Four raised pedestrian corners leave a 20m x 16m intersection.
for sx in (-1, 1):
    for sy in (-1, 1):
        box("Corner sidewalk", (sx * 3400, sy * 3200, 10), (4800, 4800, 20), CONCRETE)
        for n in range(12):
            box("Curb groove", (sx * 1050, sy * (1000 + n * 340), 22), (75, 5, 4), GRAPHITE)
        for n in range(8):
            if sy == 1:
                box("Pedestrian crossing", (sx * (1180 + n * 85), 0, 2), (43, 1350, 3), WHITE)
            if sx == 1:
                box("Pedestrian crossing", (0, sy * (980 + n * 85), 2), (1770, 43, 3), WHITE)
        box("Stop line", (sx * 1920, -sy * 405, 2), (30, 745, 3), WHITE)
# Lane paint, double yellow centre and broken white lane dividers.
for side in (-1, 1):
    for offset in (-12, 12):
        box("Centre yellow", (side * 4400, offset, 2), (4300, 7, 3), YELLOW)
        box("Centre yellow", (offset, side * 4400, 2), (7, 4500, 3), YELLOW)
    for n in range(8):
        d = side * (2300 + n * 560)
        for lane in (-410, 410):
            box("Lane dash", (d, lane, 2), (220, 10, 3), WHITE)
            box("Lane dash", (lane, d, 2), (10, 220, 3), WHITE)

signal(-1090, -1030, -16, "red")
signal(1110, 1010, 164, "red")
signal(1120, -1040, 76, "green")
signal(-1120, 1040, -104, "green")

# Human-scaled street furniture, planted edges, and a warm urban backdrop.
for x, y in [
    (-1400, 1450),
    (1450, 1450),
    (1400, -1800),
    (-1500, 2800),
    (1500, 3400),
    (2900, 1250),
    (-3300, 1250),
]:
    tree(x, y, RNG.randint(480, 640))
for x, y in [(1300, 2200), (-1300, 2200), (2400, -1050), (-3300, -1050)]:
    cylinder("Street lamp pole", (x, y, 420), 12, 840, STEEL)
    box("Street lamp head", (x, y - 70, 840), (70, 150, 15), GRAPHITE)
    box("Street lamp diffuser", (x, y - 70, 831), (56, 120, 3), WINDOW)
    lamp("Warm pool", (x, y - 80, 740), (1, 0.6, 0.29), 2000, 1500)

for bx, by, width, depth, floors, facade in [
    (-2800, 2900, 1900, 1900, 6, FACADE),
    (2650, 3000, 2100, 2300, 9, TEAL),
    (5500, 2600, 1800, 2100, 6, FACADE),
    (-5300, 2800, 1800, 2000, 9, TEAL),
    (2800, 6100, 2000, 1700, 14, FACADE),
    (-2600, 6500, 1800, 1600, 12, TEAL),
]:
    height = floors * 330
    box("City building", (bx, by, height / 2 + 20), (width, depth, height), facade)
    box("Roof coping", (bx, by, height + 30), (width + 50, depth + 50, 35), WHITE)
    for floor in range(floors):
        z = 210 + floor * 330
        box(
            "Storey shadow reveal", (bx, by - depth / 2 - 2, z + 145), (width + 8, 15, 12), GRAPHITE
        )
        for col in range(int(width / 290)):
            wx = bx - width / 2 + 180 + col * 290
            mat = WINDOW if RNG.random() < 0.32 else GLASS
            box("Window frame", (wx, by - depth / 2 - 8, z), (195, 14, 215), GRAPHITE)
            box("Window glazing", (wx, by - depth / 2 - 17, z), (175, 3, 195), mat)
    # Side glazing gives depth when viewed down the cross street.
    side = -1 if bx > 0 else 1
    for floor in range(floors):
        for col in range(int(depth / 330)):
            yy = by - depth / 2 + 190 + col * 330
            box(
                "Side glazing",
                (bx + side * (width / 2 + 3), yy, 210 + floor * 330),
                (8, 195, 205),
                WINDOW if RNG.random() < 0.2 else GLASS,
            )
    box("Shopfront canopy", (bx, by - depth / 2 - 160, 310), (width + 70, 320, 28), TEAL)

for fname, loc, yaw, length in [
    ("sedan", (-530, -1870, 0), 0, 450),
    ("taxi", (-540, -2640, 0), 0, 430),
    ("van", (-510, -3530, 0), 0, 500),
    ("suv", (560, 2350, 0), 180, 460),
    ("hatchback-sports", (2060, -370, 0), -90, 400),
    ("delivery", (-2880, 370, 0), 90, 520),
]:
    imported_vehicle(fname, loc, yaw, length)

sun = spawn(unreal.DirectionalLight, "Dusk key", (0, 0, 4000), (-18, -125, 0))
sun.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
sun.light_component.set_intensity(5.0)
sun.light_component.set_light_color(unreal.LinearColor(1, 0.67, 0.41, 1))
prop(sun.light_component, "light_source_angle", 4.0)
spawn(unreal.SkyAtmosphere, "Evening atmosphere", (0, 0, 0))
sky = spawn(unreal.SkyLight, "Soft blue skylight", (0, 0, 500))
sky.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
sky.light_component.set_intensity(2.0)
prop(sky.light_component, "source_type", unreal.SkyLightSourceType.SLS_SPECIFIED_CUBEMAP)
sky_cube = unreal.load_asset("/Engine/MapTemplates/Sky/SunsetAmbientCubemap")
prop(sky.light_component, "cubemap", sky_cube)
prop(sky.light_component, "real_time_capture", False)
fill = spawn(unreal.DirectionalLight, "Cool cinematic fill", (0, 0, 3000), (-35, 52, 0))
fill.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
fill.light_component.set_intensity(1.8)
fill.light_component.set_light_color(unreal.LinearColor(0.45, 0.67, 1, 1))
prop(fill.light_component, "cast_shadows", False)
prop(fill.light_component, "atmosphere_sun_light", False)
# A real HDR sky texture distributed with the engine supplies the photographed backdrop.
sky_mat = material("SunsetBackdrop", (0, 0, 0), 1)
prop(sky_mat, "two_sided", True)
prop(sky_mat, "shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
sky_tex = MATS.create_material_expression(sky_mat, unreal.MaterialExpressionTextureSample)
sky_tex.set_editor_property("texture", sky_cube)
camera_vec = MATS.create_material_expression(sky_mat, unreal.MaterialExpressionCameraVectorWS)
negative = MATS.create_material_expression(sky_mat, unreal.MaterialExpressionMultiply)
negative.set_editor_property("const_b", -1.0)
MATS.connect_material_expressions(camera_vec, "", negative, "A")
MATS.connect_material_expressions(negative, "", sky_tex, "UVs")
MATS.connect_material_property(sky_tex, "RGB", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
MATS.recompile_material(sky_mat)
dome = shape("HDR sky dome", "Sphere", (0, 0, 0), (160000, 160000, 160000), sky_mat)
prop(dome.static_mesh_component, "cast_shadow", False)
fog = spawn(unreal.ExponentialHeightFog, "Atmospheric depth", (0, 0, -500))
prop(fog.component, "fog_density", 0.015)
prop(fog.component, "fog_height_falloff", 0.25)

camera_loc = V(-1600, -2300, 720)
camera_target = V(500, 900, 350)
camera_rot = unreal.MathLibrary.find_look_at_rotation(camera_loc, camera_target)
camera = ACTORS.spawn_actor_from_class(unreal.CameraActor, camera_loc, camera_rot)
camera.set_actor_label("DEMO_HeroCamera")
camera.camera_component.set_field_of_view(64)
LEVELS.pilot_level_actor(camera)
LEVELS.editor_set_game_view(True)

capture = ACTORS.spawn_actor_from_class(unreal.SceneCapture2D, camera_loc, camera_rot)
capture.set_actor_label("DEMO_GPU_Capture")
comp = capture.capture_component2d
target = unreal.RenderingLibrary.create_render_target2d(
    WORLD, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8
)
comp.set_editor_property("texture_target", target)
comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
comp.set_editor_property("fov_angle", 64.0)
comp.set_editor_property("capture_every_frame", True)
comp.set_editor_property("always_persist_rendering_state", True)
settings = unreal.PostProcessSettings()
for key, value in {
    "auto_exposure_min_brightness": 1.0,
    "auto_exposure_max_brightness": 1.0,
    "auto_exposure_bias": 0.5,
    "bloom_intensity": 0.35,
    "vignette_intensity": 0.2,
    "motion_blur_amount": 0.0,
    "ambient_occlusion_intensity": 0.8,
    "ambient_occlusion_radius": 120.0,
}.items():
    prop(settings, "override_" + key, True)
    prop(settings, key, value)
comp.set_editor_property("post_process_settings", settings)
comp.set_editor_property("post_process_blend_weight", 1.0)
camera.camera_component.set_editor_property("post_process_settings", settings)
for command in [
    "r.ScreenPercentage 100",
    "r.SSR.Quality 3",
    "r.BloomQuality 5",
    "r.ShadowQuality 4",
    "r.AmbientOcclusionLevels 2",
    "r.Streaming.PoolSize 1400",
]:
    unreal.SystemLibrary.execute_console_command(WORLD, command)
unreal.EditorAssetLibrary.save_directory(ASSET_DIR)
LEVELS.save_current_level()
unreal.log("DEMO_SCENE_READY waiting for GPU warmup")
START = time.monotonic()
STATE = {"frames": 0, "captured": False}


def tick(_dt):
    STATE["frames"] += 1
    elapsed = time.monotonic() - START
    if not STATE["captured"] and STATE["frames"] > 180 and elapsed > 35:
        unreal.AutomationLibrary.finish_loading_before_screenshot()
        comp.capture_scene()
        STATE["captured"] = True
        STATE["capture_frame"] = STATE["frames"]
    elif STATE["captured"] and STATE["frames"] > STATE["capture_frame"] + 15:
        unreal.RenderingLibrary.export_render_target(WORLD, target, str(OUT), "signal_corner.png")
        (OUT / "capture_manifest.json").write_text(
            json.dumps(
                {
                    "renderer": "Unreal Engine 5.8 GPU SceneCapture2D",
                    "resolution": [1920, 1080],
                    "claim": "Art-directed illustrative scene; not calibrated traffic or map geometry.",
                    "assets": "Existing Kenney CC0 vehicle GLBs plus procedural geometry",
                    "camera_location_cm": [camera_loc.x, camera_loc.y, camera_loc.z],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        unreal.log("DEMO_CAPTURE_COMPLETE " + str(OUT / "signal_corner.png"))
        unreal.unregister_slate_post_tick_callback(TICK_HANDLE)
        unreal.EditorPythonScripting.set_keep_python_script_alive(False)


TICK_HANDLE = unreal.register_slate_post_tick_callback(tick)
