#!/usr/bin/env python3
"""Crea la intro 3D original de JKVAL en Blender.

Uso:
    blender -b --factory-startup --python scripts/build_intro_blender.py -- --preview
    blender -b --factory-startup --python scripts/build_intro_blender.py -- --render

Genera:
    assets/intro/JKVAL_intro.blend
    assets/intro/frames/frame_####.png (temporal)
    assets/intro/JKVAL_intro_preview.mp4 (con ffmpeg, fuera de este script)

La katana, los filos, las chispas y la escena son geometría y materiales
originales creados aquí. No se usan modelos de terceros ni assets de Riot.
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector

BASE = Path(__file__).resolve().parent.parent
INTRO = BASE / "assets" / "intro"
FRAMES = INTRO / "frames"
BLEND = INTRO / "JKVAL_intro.blend"
SEED = 20261028
FPS = 30
FRAME_END = 120
RES_X, RES_Y = 1600, 900


def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = RES_X
    scene.render.resolution_y = RES_Y
    scene.render.resolution_percentage = 100
    scene.render.fps = FPS
    scene.frame_start = 1
    scene.frame_end = FRAME_END
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.render.filepath = str(FRAMES / "frame_")
    try:
        scene.render.use_motion_blur = True
        scene.render.motion_blur_shutter = 0.7
    except Exception:
        pass
    for attr, value in (("taa_render_samples", 32), ("use_gtao", True)):
        if hasattr(scene.eevee, attr):
            setattr(scene.eevee, attr, value)
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = "AgX - Punchy"
    except Exception:
        pass
    scene.world = bpy.data.worlds.new("JKVAL World")
    scene.world.use_nodes = True


def node_mat(name: str, base: tuple, metallic=0.0, roughness=0.4, emission=None, strength=0.0, alpha=1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (340, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (40, 0)
    bsdf.inputs["Base Color"].default_value = (*base, 1)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1)
        bsdf.inputs["Emission Strength"].default_value = strength
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
        try:
            mat.surface_render_method = "BLENDED"
        except Exception:
            pass
        try:
            mat.blend_method = "BLEND"
        except Exception:
            pass
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    return mat


def emissive_mat(name: str, color: tuple, strength: float):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emission = nt.nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (*color, 1)
    emission.inputs["Strength"].default_value = strength
    nt.links.new(emission.outputs[0], out.inputs[0])
    return mat


def build_world() -> None:
    world = bpy.context.scene.world
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    out.location = (500, 0)
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.location = (280, 0)
    bg.inputs["Strength"].default_value = 0.30
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (60, 0)
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.006, 0.003, 0.016, 1)
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = (0.090, 0.036, 0.170, 1)
    mid = ramp.color_ramp.elements.new(0.55)
    mid.color = (0.026, 0.009, 0.060, 1)
    tex = nt.nodes.new("ShaderNodeTexGradient")
    tex.location = (-180, 0)
    tex.gradient_type = "SPHERICAL"
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.location = (-400, 0)
    coord = nt.nodes.new("ShaderNodeTexCoord")
    coord.location = (-600, 0)
    nt.links.new(coord.outputs["Generated"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

    # Plano de fondo con material oscuro y retícula diagonal sutil.
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 6, 3), rotation=(math.radians(90), 0, 0))
    backdrop = bpy.context.object
    backdrop.name = "Backdrop"
    mat = bpy.data.materials.new("Backdrop Material")
    mat.use_nodes = True
    nt2 = mat.node_tree
    nt2.nodes.clear()
    out2 = nt2.nodes.new("ShaderNodeOutputMaterial")
    out2.location = (500, 0)
    bsdf = nt2.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (200, 0)
    bsdf.inputs["Base Color"].default_value = (0.006, 0.003, 0.012, 1)
    bsdf.inputs["Roughness"].default_value = 0.72
    noise = nt2.nodes.new("ShaderNodeTexNoise")
    noise.location = (-420, -80)
    noise.inputs["Scale"].default_value = 7.0
    noise.inputs["Detail"].default_value = 5.0
    ramp2 = nt2.nodes.new("ShaderNodeValToRGB")
    ramp2.location = (-180, -80)
    ramp2.color_ramp.elements[0].color = (0.004, 0.002, 0.010, 1)
    ramp2.color_ramp.elements[1].color = (0.050, 0.015, 0.090, 1)
    nt2.links.new(noise.outputs["Fac"], ramp2.inputs["Fac"])
    nt2.links.new(ramp2.outputs["Color"], bsdf.inputs["Base Color"])
    nt2.links.new(bsdf.outputs[0], out2.inputs[0])
    backdrop.data.materials.append(mat)


def build_katana() -> bpy.types.Object:
    """Katana con hoja curva, filo emisivo, guarda y mango."""
    length = 5.6
    sections = 26
    verts = []
    faces = []
    for i in range(sections + 1):
        t = i / sections
        x = -length / 2 + t * length
        curve = 0.22 * (t ** 2)
        width = 0.085 * (1.0 - 0.62 * t) + 0.008
        thick = 0.016 * (1.0 - 0.5 * t) + 0.002
        # sección romboidal: dos vértices de filo (Y +/-) y dos caras
        verts.extend([
            (x, -thick, curve + width * 0.55),
            (x, 0.0, curve - width * 0.45),
            (x, thick, curve + width * 0.55),
            (x, 0.0, curve + width * 0.55),
        ])
        if i:
            base = (i - 1) * 4
            cur = i * 4
            for k in range(4):
                a = base + k
                b = base + (k + 1) % 4
                c = cur + (k + 1) % 4
                d = cur + k
                faces.append((a, b, c, d))
    faces.append((0, 1, 2, 3))
    last = sections * 4
    faces.append((last + 3, last + 2, last + 1, last))

    mesh = bpy.data.meshes.new("Katana Blade")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    blade = bpy.data.objects.new("Katana_Blade", mesh)
    bpy.context.collection.objects.link(blade)
    blade.data.materials.append(node_mat("Blade Steel", (0.80, 0.78, 0.88), metallic=0.86, roughness=0.22))

    bevel = blade.modifiers.new("Blade Bevel", "BEVEL")
    bevel.width = 0.006
    bevel.segments = 2
    bevel.limit_method = "ANGLE"

    # Filo emisivo: cinta fina sobre el borde superior de la hoja.
    edge_verts = []
    edge_faces = []
    for i in range(sections + 1):
        t = i / sections
        x = -length / 2 + t * length
        curve = 0.22 * (t ** 2)
        width = 0.085 * (1.0 - 0.62 * t) + 0.008
        edge_verts.extend([
            (x, -0.010, curve + width * 0.55 + 0.0015),
            (x, 0.010, curve + width * 0.55 + 0.0015),
        ])
        if i:
            base = (i - 1) * 2
            cur = i * 2
            edge_faces.append((base, base + 1, cur + 1, cur))
    emesh = bpy.data.meshes.new("Katana Edge")
    emesh.from_pydata(edge_verts, [], edge_faces)
    emesh.update()
    edge = bpy.data.objects.new("Katana_Edge", emesh)
    bpy.context.collection.objects.link(edge)
    edge.data.materials.append(emissive_mat("Violet Edge", (0.58, 0.28, 1.0), 4.5))
    edge.parent = blade

    # Guarda (tsuba)
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.20, depth=0.045,
                                        location=(-length / 2 - 0.02, 0, 0.22),
                                        rotation=(0, math.radians(90), 0))
    guard = bpy.context.object
    guard.name = "Katana_Guard"
    guard.data.materials.append(node_mat("Guard Violet", (0.24, 0.10, 0.36), metallic=0.85, roughness=0.28,
                                         emission=(0.35, 0.12, 0.62), strength=0.7))
    guard.parent = blade

    # Mango
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.065, depth=1.0,
                                        location=(-length / 2 - 0.55, 0, 0.24),
                                        rotation=(0, math.radians(90), 0))
    handle = bpy.context.object
    handle.name = "Katana_Handle"
    handle.data.materials.append(node_mat("Handle Wrap", (0.035, 0.018, 0.055), roughness=0.62))
    handle.parent = blade

    for i in range(7):
        x = -length / 2 - 0.15 - i * 0.12
        bpy.ops.mesh.primitive_torus_add(major_radius=0.070, minor_radius=0.010,
                                         location=(x, 0, 0.24),
                                         rotation=(0, math.radians(90), 0))
        ring = bpy.context.object
        ring.name = f"Handle_Ring_{i:02d}"
        ring.data.materials.append(node_mat("Ring Violet", (0.20, 0.08, 0.32), roughness=0.4,
                                            emission=(0.45, 0.18, 0.85), strength=1.4))
        ring.parent = blade

    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.075, depth=0.07,
                                        location=(-length / 2 - 1.08, 0, 0.24),
                                        rotation=(0, math.radians(90), 0))
    pommel = bpy.context.object
    pommel.name = "Katana_Pommel"
    pommel.data.materials.append(node_mat("Pommel", (0.25, 0.18, 0.36), metallic=0.9, roughness=0.25))
    pommel.parent = blade

    # El objeto raíz que se anima.
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0))
    root = bpy.context.object
    root.name = "Katana_Root"
    blade.parent = root
    for child in list(root.children):
        if child.type == "EMPTY":
            child.parent = root
    return root


def build_slash() -> tuple[bpy.types.Object, bpy.types.Object]:
    mat = emissive_mat("Slash Energy", (0.62, 0.34, 1.0), 7.0)
    # Tres cintas con grosores distintos para un corte estilizado.
    objs = []
    for idx, (length, width, offset, angle) in enumerate((
        (12.0, 0.050, 0.0, 47.0),
        (9.2, 0.018, 0.10, 49.0),
        (7.0, 0.10, -0.16, 45.0),
    )):
        bpy.ops.mesh.primitive_plane_add(size=1, location=(0.1, -0.42 - idx * 0.01, 0.45))
        obj = bpy.context.object
        obj.name = f"Slash_Streak_{idx}"
        obj.scale = (length, width, 1)
        obj.rotation_euler = (math.radians(90), 0, 0)
        obj.rotation_euler.rotate_axis("Y", math.radians(angle))
        obj.data.materials.append(mat)
        obj.scale = (0.001, width, 1)
        obj.keyframe_insert("scale", frame=44)
        obj.scale = (length, width, 1)
        obj.keyframe_insert("scale", frame=50)
        obj.scale = (length, width, 1)
        obj.keyframe_insert("scale", frame=61)
        obj.scale = (0.001, width, 1)
        obj.keyframe_insert("scale", frame=72)
        objs.append(obj)

    # Destello del impacto
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1.0,
                                         location=(0.1, -0.7, 0.45))
    flash = bpy.context.object
    flash.name = "Impact_Flash"
    flash.data.materials.append(emissive_mat("Flash", (0.72, 0.48, 1.0), 4.0))
    flash.scale = (0.001, 0.001, 0.001)
    flash.keyframe_insert("scale", frame=46)
    flash.scale = (0.6, 0.6, 0.6)
    flash.keyframe_insert("scale", frame=51)
    flash.scale = (0.001, 0.001, 0.001)
    flash.keyframe_insert("scale", frame=58)
    return objs[0], flash


def build_sparks(rng: random.Random) -> None:
    mat = emissive_mat("Spark", (0.70, 0.45, 1.0), 3.5)
    core = Vector((0.1, -0.5, 0.45))
    direction = Vector((math.cos(math.radians(47)), 0, -math.sin(math.radians(47))))
    perp = Vector((-direction.z, 0, direction.x))
    for i in range(64):
        along = rng.uniform(-4.8, 4.8)
        start = core + direction * along + Vector((rng.uniform(-.05, .05), rng.uniform(-.1, .1), 0))
        spread = perp * rng.uniform(-0.7, 0.9) + Vector((0, rng.uniform(-0.25, 0.25), rng.uniform(0.1, 0.8)))
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=rng.uniform(0.006, 0.020), location=start)
        spark = bpy.context.object
        spark.name = f"Spark_{i:02d}"
        spark.data.materials.append(mat)
        spark.scale = (0.001, 0.001, 0.001)
        spark.keyframe_insert("scale", frame=48)
        spark.scale = (1, 1, 1)
        spark.keyframe_insert("scale", frame=51)
        spark.scale = (1, 1, 1)
        spark.keyframe_insert("scale", frame=62)
        spark.scale = (0.001, 0.001, 0.001)
        spark.keyframe_insert("scale", frame=82)
        spark.location = start
        spark.keyframe_insert("location", frame=49)
        spark.location = start + spread * rng.uniform(1.2, 2.6) + Vector((0, 0, -0.25))
        spark.keyframe_insert("location", frame=82)


def build_dust(rng: random.Random) -> None:
    mat = emissive_mat("Dust", (0.45, 0.22, 0.85), 1.2)
    for i in range(42):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=rng.uniform(0.006, 0.018),
                                              location=(rng.uniform(-6, 6), rng.uniform(3.5, 5.5), rng.uniform(-1.5, 4.5)))
        dust = bpy.context.object
        dust.name = f"Dust_{i:02d}"
        dust.data.materials.append(mat)
        dust.keyframe_insert("location", frame=1)
        dust.location.z += rng.uniform(0.4, 1.4)
        dust.keyframe_insert("location", frame=FRAME_END)


def build_lights() -> dict:
    def area(name, loc, color, energy, size):
        data = bpy.data.lights.new(name, "AREA")
        data.color = color
        data.energy = energy
        data.size = size
        obj = bpy.data.objects.new(name, data)
        obj.location = loc
        bpy.context.collection.objects.link(obj)
        obj.rotation_euler = (Vector((0, 0, 0.6)) - obj.location).to_track_quat("-Z", "Y").to_euler()
        return obj

    key = area("Key Violet", (-3.6, -4.5, 4.2), (0.55, 0.30, 1.0), 1100, 5.0)
    rim = area("Rim Violet", (4.0, 2.0, 3.2), (0.38, 0.16, 0.9), 1500, 4.0)
    fill = area("Fill Cold", (2.5, -4.0, -1.5), (0.45, 0.55, 1.0), 500, 3.0)
    spec = area("Blade Spec", (0.4, 1.4, 3.0), (0.88, 0.78, 1.0), 900, 6.0)
    spec.data.shape = "RECTANGLE"
    spec.data.size_y = 0.9
    spec.rotation_euler = (Vector((0, 0, 0.6)) - spec.location).to_track_quat("-Z", "Y").to_euler()
    return {"key": key, "rim": rim, "fill": fill, "spec": spec}


def build_camera() -> bpy.types.Object:
    data = bpy.data.cameras.new("Intro Camera")
    data.lens = 52
    cam = bpy.data.objects.new("Intro Camera", data)
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam

    def look(location, target=(0, 0, 0.55)):
        cam.location = location
        cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()

    look((0.0, -8.2, 2.7))
    cam.keyframe_insert("location", frame=1)
    cam.keyframe_insert("rotation_euler", frame=1)
    look((0.0, -7.7, 2.45))
    cam.keyframe_insert("location", frame=46)
    cam.keyframe_insert("rotation_euler", frame=46)
    look((0.06, -7.55, 2.55))
    cam.keyframe_insert("location", frame=56)
    cam.keyframe_insert("rotation_euler", frame=56)
    look((0.0, -6.9, 2.3))
    cam.keyframe_insert("location", frame=FRAME_END)
    cam.keyframe_insert("rotation_euler", frame=FRAME_END)
    return cam


def animate_katana(root: bpy.types.Object) -> None:
    # Entrada desde arriba a la izquierda y salida por abajo a la derecha.
    root.rotation_euler = (math.radians(0), math.radians(47), math.radians(-6))
    positions = [
        (1, (-7.2, 0.8, 4.8)),
        (30, (-2.6, 0.4, 2.4)),
        (46, (-0.1, 0.0, 0.6)),
        (54, (0.9, -0.1, -0.2)),
        (78, (2.6, -0.2, -1.3)),
        (FRAME_END, (6.0, -0.3, -3.4)),
    ]
    for frame, loc in positions:
        root.location = loc
        root.keyframe_insert("location", frame=frame)
        root.keyframe_insert("rotation_euler", frame=frame)
    # Un giro extra al impactar.
    root.rotation_euler = (math.radians(-4), math.radians(52), math.radians(-10))
    root.keyframe_insert("rotation_euler", frame=52)
    root.rotation_euler = (math.radians(0), math.radians(47), math.radians(-6))
    root.keyframe_insert("rotation_euler", frame=90)


def build_compositor() -> None:
    """Bloom + dispersión de lente con la API de compositor de Blender 5.x.

    Blender 5 sustituyó ``Scene.node_tree`` por ``Scene.compositing_node_group``;
    el grupo necesita un socket de salida declarado en su interfaz y el nodo
    ``CompositorNodeGlare`` expone su tipo como socket de menú.
    """
    scene = bpy.context.scene
    group = bpy.data.node_groups.new("JKVAL Compositor", "CompositorNodeTree")
    scene.compositing_node_group = group
    group.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")

    rl = group.nodes.new("CompositorNodeRLayers")
    rl.location = (-420, 0)

    glare = group.nodes.new("CompositorNodeGlare")
    glare.location = (-160, 0)
    glare.inputs["Type"].default_value = "Bloom"
    glare.inputs["Quality"].default_value = "High"
    glare.inputs["Threshold"].default_value = 1.0
    glare.inputs["Strength"].default_value = 0.4
    glare.inputs["Size"].default_value = 0.45
    glare.inputs["Saturation"].default_value = 1.0
    glare.inputs["Tint"].default_value = (0.62, 0.34, 1.0, 1.0)

    lens = group.nodes.new("CompositorNodeLensdist")
    lens.location = (140, 0)
    lens.inputs["Distortion"].default_value = 0.012
    lens.inputs["Dispersion"].default_value = 0.02

    out = group.nodes.new("NodeGroupOutput")
    out.location = (380, 0)

    group.links.new(rl.outputs["Image"], glare.inputs["Image"])
    group.links.new(glare.outputs["Image"], lens.inputs["Image"])
    group.links.new(lens.outputs["Image"], out.inputs["Image"])


def main() -> None:
    FRAMES.mkdir(parents=True, exist_ok=True)
    INTRO.mkdir(parents=True, exist_ok=True)
    reset_scene()
    rng = random.Random(SEED)
    build_world()
    root = build_katana()
    build_slash()
    build_sparks(rng)
    build_dust(rng)
    build_lights()
    build_camera()
    animate_katana(root)
    build_compositor()
    bpy.context.scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    print(f"OK blend: {BLEND}")

    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--fast" in argv:
        # Iteración rápida: 25 % de resolución y pocas muestras.
        scene = bpy.context.scene
        scene.render.resolution_percentage = 25
        if hasattr(scene.eevee, "taa_render_samples"):
            scene.eevee.taa_render_samples = 8
    if "--preview" in argv:
        bpy.context.scene.frame_set(58)
        bpy.context.scene.render.filepath = str(INTRO / "preview_frame.png")
        bpy.ops.render.render(write_still=True)
        print("OK preview frame")
    elif "--render" in argv:
        bpy.context.scene.render.filepath = str(FRAMES / "frame_")
        bpy.ops.render.render(animation=True)
        print("OK frames")


if __name__ == "__main__":
    main()
