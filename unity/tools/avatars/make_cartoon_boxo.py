"""Original boxy cartoon warehouse worker ("Boxo"), built from simple shapes.

T-pose, Y up, facing +Z, metres. Output: OBJ + MTL for Mixamo's auto-rigger.
Separate fingers (thumb + 3) so the rig gets finger bones.
"""
import math
import os

OUT = "/home/claude/boxo"
os.makedirs(OUT, exist_ok=True)

COLORS = {
    "body": (0.16, 0.62, 0.66),      # teal
    "vest": (0.98, 0.45, 0.10),      # safety orange
    "stripe": (0.92, 0.92, 0.88),    # reflective stripe
    "helmet": (0.95, 0.95, 0.95),    # white hard hat
    "eye_white": (1.0, 1.0, 1.0),
    "pupil": (0.05, 0.05, 0.08),
    "mouth": (0.35, 0.08, 0.10),
    "limb": (0.16, 0.62, 0.66),      # same teal as body
    "glove": (0.20, 0.20, 0.22),     # dark grey gloves
    "trousers": (0.18, 0.22, 0.40),  # navy work trousers
    "boot": (0.25, 0.18, 0.12),      # brown boots
}

verts, faces = [], []          # faces: (material, [vertex indices 1-based])
parts = []                     # (first face index, centre) per primitive


def add_face(mat, idx):
    faces.append((mat, idx))


def box(cx, cy, cz, sx, sy, sz, mat):
    parts.append((len(faces), (cx, cy, cz)))
    base = len(verts)
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    for dx in (-hx, hx):
        for dy in (-hy, hy):
            for dz in (-hz, hz):
                verts.append((cx + dx, cy + dy, cz + dz))
    v = lambda i: base + i + 1
    # index = ix*4 + iy*2 + iz
    quads = [
        (0, 1, 3, 2), (4, 6, 7, 5),   # -x, +x
        (0, 4, 5, 1), (2, 3, 7, 6),   # -y, +y
        (0, 2, 6, 4), (1, 5, 7, 3),   # -z, +z
    ]
    for q in quads:
        add_face(mat, [v(i) for i in q])


def rounded_box(cx, cy, cz, sx, sy, sz, r, mat, seg=3):
    """Box with bevelled vertical edges (a cheap rounded look)."""
    parts.append((len(faces), (cx, cy, cz)))
    base = len(verts)
    hx, hz = sx / 2 - r, sz / 2 - r
    ring = []
    for k, (ox, oz, a0) in enumerate([(hx, hz, 0), (-hx, hz, 90),
                                      (-hx, -hz, 180), (hx, -hz, 270)]):
        for s in range(seg + 1):
            a = math.radians(a0 + 90 * s / seg)
            ring.append((ox + r * math.cos(a), oz + r * math.sin(a)))
    n = len(ring)
    for y in (cy - sy / 2, cy + sy / 2):
        for (x, z) in ring:
            verts.append((cx + x, y, cz + z))
    bot = [base + i + 1 for i in range(n)]
    top = [base + n + i + 1 for i in range(n)]
    for i in range(n):
        j = (i + 1) % n
        add_face(mat, [bot[i], bot[j], top[j], top[i]])
    add_face(mat, top)
    add_face(mat, list(reversed(bot)))


def cylinder(p0, p1, rad, mat, seg=10):
    parts.append((len(faces), tuple((p0[i] + p1[i]) / 2 for i in range(3))))
    ax = [p1[i] - p0[i] for i in range(3)]
    L = math.sqrt(sum(a * a for a in ax))
    ax = [a / L for a in ax]
    ref = (0, 1, 0) if abs(ax[1]) < 0.9 else (1, 0, 0)
    u = [ax[1] * ref[2] - ax[2] * ref[1], ax[2] * ref[0] - ax[0] * ref[2],
         ax[0] * ref[1] - ax[1] * ref[0]]
    ul = math.sqrt(sum(a * a for a in u))
    u = [a / ul for a in u]
    w = [ax[1] * u[2] - ax[2] * u[1], ax[2] * u[0] - ax[0] * u[2],
         ax[0] * u[1] - ax[1] * u[0]]
    base = len(verts)
    for p in (p0, p1):
        for s in range(seg):
            a = 2 * math.pi * s / seg
            verts.append(tuple(p[i] + rad * (math.cos(a) * u[i] + math.sin(a) * w[i])
                               for i in range(3)))
    b = [base + i + 1 for i in range(seg)]
    t = [base + seg + i + 1 for i in range(seg)]
    for i in range(seg):
        j = (i + 1) % seg
        add_face(mat, [b[i], b[j], t[j], t[i]])
    add_face(mat, list(reversed(b)))
    add_face(mat, t)


def sphere(c, r, mat, seg=12, rings=8, squash=(1, 1, 1)):
    parts.append((len(faces), tuple(c)))
    base = len(verts)
    for i in range(rings + 1):
        th = math.pi * i / rings
        for j in range(seg):
            ph = 2 * math.pi * j / seg
            verts.append((c[0] + r * squash[0] * math.sin(th) * math.cos(ph),
                          c[1] + r * squash[1] * math.cos(th),
                          c[2] + r * squash[2] * math.sin(th) * math.sin(ph)))
    for i in range(rings):
        for j in range(seg):
            a = base + i * seg + j + 1
            b = base + i * seg + (j + 1) % seg + 1
            cc = base + (i + 1) * seg + (j + 1) % seg + 1
            d = base + (i + 1) * seg + j + 1
            add_face(mat, [a, b, cc, d])


# ---- proportions (metres) ----
H_LEG = 0.62           # hip height
BODY_W, BODY_H, BODY_D = 0.62, 0.72, 0.34
BODY_Y0 = H_LEG
BODY_CY = BODY_Y0 + BODY_H / 2
SHOULDER_Y = BODY_Y0 + BODY_H - 0.14
FRONT_Z = BODY_D / 2

# body: boxy, rounded vertical edges
rounded_box(0, BODY_CY, 0, BODY_W, BODY_H, BODY_D, 0.07, "body")

# safety vest panels (front and back, lower part of the body)
for zs in (1, -1):
    box(0, BODY_Y0 + 0.24, zs * (FRONT_Z + 0.006), BODY_W * 0.92, 0.40, 0.012, "vest")
    box(0, BODY_Y0 + 0.18, zs * (FRONT_Z + 0.013), BODY_W * 0.92, 0.035, 0.006, "stripe")
    box(0, BODY_Y0 + 0.30, zs * (FRONT_Z + 0.013), BODY_W * 0.92, 0.035, 0.006, "stripe")

# face on the upper front: two round eyes and a small smile
EYE_Y = BODY_Y0 + BODY_H - 0.20
for xs in (-1, 1):
    sphere((xs * 0.13, EYE_Y, FRONT_Z + 0.005), 0.09, "eye_white",
           squash=(1, 1, 0.35))
    sphere((xs * 0.12, EYE_Y - 0.005, FRONT_Z + 0.034), 0.04, "pupil",
           squash=(1, 1, 0.4))
box(0, EYE_Y - 0.13, FRONT_Z + 0.008, 0.16, 0.025, 0.014, "mouth")

# hard hat on top
HAT_Y = BODY_Y0 + BODY_H
rounded_box(0, HAT_Y + 0.06, 0, BODY_W * 0.80, 0.12, BODY_D * 0.95, 0.10, "helmet")
box(0, HAT_Y + 0.008, 0.04, BODY_W * 0.95, 0.016, BODY_D * 1.25, "helmet")

# arms in T-pose: thin limbs, gloves with thumb + 3 fingers
ARM_R = 0.045
for xs in (-1, 1):
    sh = (xs * (BODY_W / 2 - 0.02), SHOULDER_Y, 0)
    el = (xs * (BODY_W / 2 + 0.24), SHOULDER_Y, 0)
    wr = (xs * (BODY_W / 2 + 0.48), SHOULDER_Y, 0)
    cylinder(sh, el, ARM_R, "limb")
    cylinder(el, wr, ARM_R * 0.92, "limb")
    sphere(el, ARM_R * 1.05, "limb", seg=10, rings=6)
    # palm
    px = xs * (BODY_W / 2 + 0.53)
    box(px, SHOULDER_Y, 0, 0.12, 0.04, 0.12, "glove")
    # three fingers, pointing outward along x, separated along z
    for fz in (-0.04, 0.0, 0.04):
        f0 = (xs * (BODY_W / 2 + 0.585), SHOULDER_Y, fz)
        f1 = (xs * (BODY_W / 2 + 0.70), SHOULDER_Y, fz)
        cylinder(f0, f1, 0.016, "glove", seg=6)
    # thumb, forward (+z) and slightly out
    cylinder((px, SHOULDER_Y, 0.06), (xs * (BODY_W / 2 + 0.57), SHOULDER_Y, 0.13),
             0.017, "glove", seg=6)

# legs: trousers, thin, apart; boots
for xs in (-1, 1):
    hip = (xs * 0.15, BODY_Y0 + 0.02, 0)
    knee = (xs * 0.17, H_LEG * 0.52, 0)
    ank = (xs * 0.18, 0.09, 0)
    cylinder(hip, knee, 0.055, "trousers")
    cylinder(knee, ank, 0.05, "trousers")
    sphere(knee, 0.056, "trousers", seg=10, rings=6)
    box(xs * 0.18, 0.045, 0.04, 0.13, 0.09, 0.22, "boot")


# ---- orient every face outward and triangulate (fixes see-through faces) ----
def newell(pts):
    n = [0.0, 0.0, 0.0]
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return n

bounds = [p[0] for p in parts[1:]] + [len(faces)]
flipped, out = 0, []
for (start, centre), end in zip(parts, bounds):
    for mat, idx in faces[start:end]:
        # remove repeated vertices (sphere poles) so faces are valid
        clean = []
        for i in idx:
            if not clean or verts[i - 1] != verts[clean[-1] - 1]:
                clean.append(i)
        if len(clean) > 1 and verts[clean[0] - 1] == verts[clean[-1] - 1]:
            clean.pop()
        if len(clean) < 3:
            continue
        pts = [verts[i - 1] for i in clean]
        n = newell(pts)
        c = [sum(p[k] for p in pts) / len(pts) for k in range(3)]
        if sum(n[k] * (c[k] - centre[k]) for k in range(3)) < 0:
            clean.reverse()
            flipped += 1
        for t in range(1, len(clean) - 1):
            out.append((mat, [clean[0], clean[t], clean[t + 1]]))
faces = out
print(f"faces flipped outward: {flipped}; triangles: {len(faces)}")

# ---- write OBJ + MTL ----
obj = os.path.join(OUT, "boxo_worker.obj")
mtl = os.path.join(OUT, "boxo_worker.mtl")
with open(mtl, "w") as f:
    for name, (r, g, b) in COLORS.items():
        f.write(f"newmtl {name}\nKd {r:.3f} {g:.3f} {b:.3f}\nKa 0 0 0\nKs 0.05 0.05 0.05\nd 1\nillum 2\n\n")
with open(obj, "w") as f:
    f.write("# Boxo: original boxy cartoon warehouse worker, T-pose, Y up, +Z front, metres\n")
    f.write("mtllib boxo_worker.mtl\no Boxo\n")
    for v in verts:
        f.write(f"v {v[0]:.5f} {v[1]:.5f} {v[2]:.5f}\n")
    cur = None
    for mat, idx in faces:
        if mat != cur:
            f.write(f"usemtl {mat}\n")
            cur = mat
        f.write("f " + " ".join(str(i) for i in idx) + "\n")

ys = [v[1] for v in verts]
xs_ = [v[0] for v in verts]
print(f"vertices {len(verts)}, faces {len(faces)}, height {max(ys) - min(ys):.2f} m, "
      f"arm span {max(xs_) - min(xs_):.2f} m")

# ---- preview render ----
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

fig = plt.figure(figsize=(10, 6), dpi=110)
for k, (elev, azim, title) in enumerate([(12, 60, "front-left"), (6, 90, "front")]):
    ax = fig.add_subplot(1, 2, k + 1, projection="3d")
    polys, cols = [], []
    for mat, idx in faces:
        pts = [verts[i - 1] for i in idx]
        polys.append([(p[0], p[2], p[1]) for p in pts])   # plot z as depth, y up
        cols.append(COLORS[mat])
    pc = Poly3DCollection(polys, facecolors=cols, edgecolors=(0, 0, 0, 0.15), linewidths=0.2)
    ax.add_collection3d(pc)
    ax.set_xlim(-0.8, 0.8); ax.set_ylim(-0.8, 0.8); ax.set_zlim(0, 1.6)
    ax.set_box_aspect((1, 1, 1))
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()
    ax.set_title(title)
plt.tight_layout()
plt.savefig(os.path.join(OUT, "boxo_preview.png"))
print("written", obj, mtl)
