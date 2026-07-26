"""Generate the braille portrait set, then freeze it as literal art."""
import sys
sys.path.insert(0, "/Users/matthewkeefe/Documents/Pi-Typing-Tutor")

W, H = 46, 40


def build(head_cy=13, head_rx=17, head_ry=8, head_dx=0.0,
          ear="up", body_top=19, half0=8.0, half1=17.0, floor=37,
          tail="curl", eyes="open", eye_y=11, legs=True, cx=20.0):
    g = [[" "] * W for _ in range(H)]

    def span(r, a, b, ch="#"):
        if 0 <= r < H:
            for x in range(max(0, a), min(W, b + 1)):
                g[r][x] = ch

    def dot(x, y, ch="#"):
        xi, yi = int(round(x)), int(round(y))
        if 0 <= xi < W and 0 <= yi < H:
            g[yi][xi] = ch

    # --- body ---------------------------------------------------------
    for y in range(body_top, floor):
        t = (y - body_top) / float(max(1, floor - 1 - body_top))
        half = half0 + (half1 - half0) * t
        span(y, int(round(cx - half)), int(round(cx + half)))
    span(floor, int(round(cx - half1 + 1)), int(round(cx + half1 - 1)))
    span(floor + 1, int(round(cx - half1 + 2)), int(round(cx + half1 - 2)))

    # --- tail ---------------------------------------------------------
    paths = {
        "curl":   lambda t: (33.0 + 9.0 * t ** 0.5, floor + 0.5 - 14.0 * t - 2.0 * t ** 2),
        "up":     lambda t: (35.0 + 4.0 * t ** 0.7, floor - 1.0 - 25.0 * t),
        "tucked": lambda t: (32.0 + 10.0 * t, floor - 1.0 - 3.0 * t ** 2),
        "flick":  lambda t: (33.0 + 9.0 * t ** 0.4, floor - 2.0 - 10.0 * t + 4.0 * t ** 2),
        # Curled asleep: the tail comes round OUTSIDE the body. Tucked
        # against it, a wide sleeping pose swallows the whole curve
        # and the cat renders with no tail at all.
        "round":  lambda t: (cx + half1 + 1.0 + 4.0 * (1 - t) ** 0.5,
                             floor - 7.0 + 7.0 * t),
    }
    path = paths[tail]
    for i in range(40):
        x, y = path(i / 39.0)
        for dx in (0, 1):
            for dy in (0, 1):
                xi, yi = int(round(x)) + dx, int(round(y)) + dy
                if 0 <= xi < W and 0 <= yi < H and g[yi][xi] == " ":
                    g[yi][xi] = "T"

    # --- ears ---------------------------------------------------------
    hx = cx + head_dx
    for side in (-1, 1):
        ax = hx + side * head_rx * 0.62
        if ear == "up":
            top, half_w = head_cy - 13, 6
        elif ear == "back":
            top, half_w = head_cy - 12, 8
        else:                                   # flat, pinned down
            top, half_w = head_cy - 6, 8
        for y in range(max(0, top), head_cy):
            t = (y - top) / float(max(1, head_cy - top))
            slant = 0 if ear == "up" else side * (1 - t) * 5.0
            c = ax + slant
            span(y, int(round(c - half_w * t)), int(round(c + half_w * t)), "R")

    # --- head ---------------------------------------------------------
    for y in range(H):
        dy = (y - head_cy) / float(head_ry)
        if abs(dy) > 1:
            continue
        half = head_rx * (1 - dy * dy) ** 0.5
        span(y, int(round(hx - half)), int(round(hx + half)))

    # --- face ---------------------------------------------------------
    ex = head_rx * 0.52
    if eyes == "open":
        for y in range(eye_y, eye_y + 4):
            span(y, int(round(hx - ex - 3)), int(round(hx - ex + 2)), "E")
            span(y, int(round(hx + ex - 2)), int(round(hx + ex + 3)), "E")
    else:                                        # closed: two lids
        for side in (-1, 1):
            c = hx + side * ex
            span(eye_y + 2, int(round(c - 3)), int(round(c + 3)))

    # The muzzle: clear a patch of the face, then put a nose and a
    # mouth back into it. Single scattered dots read as dirt at this
    # size, so both are drawn as solid little shapes.
    my = eye_y + 5
    for i, half in enumerate((7, 7, 6, 6, 5)):
        span(my + i, int(round(hx - half)), int(round(hx + half)), " ")
    # nose: a small triangle
    span(my, int(round(hx - 2)), int(round(hx + 2)))
    span(my + 1, int(round(hx - 1)), int(round(hx + 1)))
    # mouth: the two curves of a cat's ".w." , hung off the nose
    dot(hx, my + 2)
    for side in (-1, 1):
        dot(hx + side * 1, my + 3)
        dot(hx + side * 2, my + 4)
        dot(hx + side * 3, my + 4)
        dot(hx + side * 4, my + 3)

    # --- coat zone ----------------------------------------------------
    for y in range(body_top + 4, min(floor - 3, body_top + 15)):
        span(y, int(round(cx - 7)), int(round(cx + 7)), "F")

    # --- front legs ---------------------------------------------------
    if legs:
        for y in range(floor - 6, floor + 2):
            for x in (17, 18, 19, 20, 21, 22):
                if 0 <= y < H and g[y][x] in "#F":
                    g[y][x] = " "

    return ["".join(r).rstrip() for r in g]


POSES = {
    "sit":       dict(),
    "loaf":      dict(head_cy=16, body_top=22, half0=13.0, half1=18.0,
                      tail="tucked", eye_y=14, legs=False),
    "sleep":     dict(head_cy=18, body_top=24, half0=15.0, half1=18.0,
                      tail="round", eyes="closed", eye_y=16, legs=False),
    "pounce":    dict(head_cy=15, body_top=21, half0=11.0, half1=18.0,
                      tail="flick", eye_y=13, legs=True),
    "overjoyed": dict(head_cy=13, tail="up"),
    "groom":     dict(head_cy=14, head_dx=-3.0, tail="curl", eye_y=12),
    "swat":      dict(head_cy=14, head_dx=2.5, tail="flick", eye_y=12),
    "wary":      dict(head_cy=15, ear="back", body_top=21, half0=11.0,
                      tail="tucked", eye_y=13),
}

# Kittens: same poses, smaller everything.
KITTEN_TWEAK = dict(head_rx=14, head_ry=7, half1=13.0, floor=33)


def kitten(kw):
    out = dict(kw)
    out.update(KITTEN_TWEAK)
    for k in ("head_cy", "body_top", "eye_y"):
        if k in out:
            out[k] = max(0, out[k] - 2)
    out.setdefault("head_cy", 11)
    out.setdefault("body_top", 17)
    out.setdefault("eye_y", 9)
    if "half0" in out:
        out["half0"] = min(out["half0"], 10.0)
    return out


def emit(name, table):
    print("%s = {" % name)
    for pose in sorted(table):
        print('    "%s": [' % pose)
        for row in table[pose]:
            print('        "%s",' % row)
        print("    ],")
    print("}")
    print()


if __name__ == "__main__":
    adult = {p: build(**kw) for p, kw in POSES.items()}
    kit = {p: build(**kitten(kw)) for p, kw in POSES.items()}
    if "--show" in sys.argv:
        from core import braille
        Z = {"E": ["####", "#..#", "####"], "F": ["#.#.", "...."],
             "R": ["#"], "T": ["#"]}
        for p in sorted(adult):
            print("\n--- %s ---" % p)
            for r in braille.render(braille.fill_zones(adult[p], Z)):
                print("   " + r)
    else:
        emit("ADULT", adult)
        emit("KITTEN", kit)
