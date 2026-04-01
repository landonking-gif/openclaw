#!/usr/bin/env python3
"""Generate OpenClaw Army app icon as .icns"""
import subprocess, os, math
from PIL import Image, ImageDraw, ImageFont

def create_icon(size=1024):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2
    r = size // 2 - 20

    # Background: dark purple gradient circle
    for i in range(r, 0, -1):
        frac = i / r
        red = int(30 + 50 * (1 - frac))
        green = int(5 + 15 * (1 - frac))
        blue = int(60 + 120 * (1 - frac))
        alpha = 255
        draw.ellipse([cx - i, cy - i, cx + i, cy + i], fill=(red, green, blue, alpha))

    # Inner glow ring
    ring_r = int(r * 0.85)
    ring_w = 6
    for angle in range(360):
        rad = math.radians(angle)
        x = cx + int(ring_r * math.cos(rad))
        y = cy + int(ring_r * math.sin(rad))
        glow = int(128 + 127 * math.sin(rad * 3))
        draw.ellipse([x - ring_w, y - ring_w, x + ring_w, y + ring_w],
                      fill=(glow, 50, 255, 180))

    # Ant body (stylized) - center
    body_color = (220, 180, 255, 255)
    # Head
    head_r = int(size * 0.1)
    head_y = cy - int(size * 0.15)
    draw.ellipse([cx - head_r, head_y - head_r, cx + head_r, head_y + head_r],
                 fill=body_color)
    # Thorax
    thorax_r = int(size * 0.08)
    thorax_y = cy
    draw.ellipse([cx - thorax_r, thorax_y - thorax_r, cx + thorax_r, thorax_y + thorax_r],
                 fill=body_color)
    # Abdomen
    abd_rx = int(size * 0.12)
    abd_ry = int(size * 0.14)
    abd_y = cy + int(size * 0.18)
    draw.ellipse([cx - abd_rx, abd_y - abd_ry, cx + abd_rx, abd_y + abd_ry],
                 fill=body_color)

    # Antennae
    ant_w = 4
    for side in [-1, 1]:
        # Base to tip
        bx = cx + side * int(size * 0.02)
        by = head_y - head_r + 5
        tx = cx + side * int(size * 0.12)
        ty = head_y - int(size * 0.2)
        draw.line([(bx, by), (tx, ty)], fill=body_color, width=ant_w)
        # Tip dot
        draw.ellipse([tx - 6, ty - 6, tx + 6, ty + 6], fill=(180, 100, 255, 255))

    # Legs (3 pairs)
    leg_w = 4
    leg_positions = [
        (thorax_y - int(size * 0.04), 0.18, -0.06),
        (thorax_y + int(size * 0.01), 0.22, 0.02),
        (abd_y - int(size * 0.08), 0.20, 0.10),
    ]
    for ypos, xext, yext in leg_positions:
        for side in [-1, 1]:
            sx = cx + side * thorax_r
            ex = cx + side * int(size * xext) + side * int(size * 0.08)
            ey = ypos + int(size * yext)
            # Joint
            jx = cx + side * int(size * xext)
            jy = ypos
            draw.line([(sx, ypos), (jx, jy)], fill=body_color, width=leg_w)
            draw.line([(jx, jy), (ex, ey)], fill=body_color, width=leg_w)

    # Eyes
    eye_r = int(size * 0.025)
    for side in [-1, 1]:
        ex = cx + side * int(size * 0.04)
        ey = head_y - int(size * 0.01)
        draw.ellipse([ex - eye_r, ey - eye_r, ex + eye_r, ey + eye_r],
                     fill=(100, 255, 200, 255))

    # Crown on head (the King)
    crown_color = (255, 215, 0, 255)
    crown_y = head_y - head_r - int(size * 0.02)
    crown_h = int(size * 0.08)
    crown_w = int(size * 0.12)
    points = [
        (cx - crown_w, crown_y),
        (cx - crown_w, crown_y - crown_h * 0.5),
        (cx - crown_w * 0.5, crown_y - crown_h * 0.3),
        (cx - crown_w * 0.2, crown_y - crown_h),
        (cx, crown_y - crown_h * 0.4),
        (cx + crown_w * 0.2, crown_y - crown_h),
        (cx + crown_w * 0.5, crown_y - crown_h * 0.3),
        (cx + crown_w, crown_y - crown_h * 0.5),
        (cx + crown_w, crown_y),
    ]
    draw.polygon(points, fill=crown_color)
    # Crown gems
    for xoff in [-0.2, 0, 0.2]:
        gx = cx + int(crown_w * xoff)
        gy = crown_y - int(crown_h * 0.7) if xoff != 0 else crown_y - crown_h
        draw.ellipse([gx - 5, gy - 5, gx + 5, gy + 5], fill=(255, 50, 100, 255))

    # "AI" text below ant
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(size * 0.08))
    except:
        font = ImageFont.load_default()
    text = "ARMY"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    tx = cx - tw // 2
    ty = abd_y + abd_ry + int(size * 0.02)
    draw.text((tx, ty), text, fill=(200, 180, 255, 220), font=font)

    return img

def make_icns(icon_img, output_path):
    """Create .icns file using iconutil"""
    iconset_dir = "/tmp/OpenClawArmy.iconset"
    os.makedirs(iconset_dir, exist_ok=True)

    sizes = [16, 32, 64, 128, 256, 512, 1024]
    for s in sizes:
        resized = icon_img.resize((s, s), Image.LANCZOS)
        resized.save(os.path.join(iconset_dir, f"icon_{s}x{s}.png"))
        if s <= 512:
            resized2x = icon_img.resize((s * 2, s * 2), Image.LANCZOS)
            resized2x.save(os.path.join(iconset_dir, f"icon_{s}x{s}@2x.png"))

    subprocess.run(["iconutil", "-c", "icns", iconset_dir, "-o", output_path], check=True)
    print(f"Created: {output_path}")

if __name__ == "__main__":
    icon = create_icon(1024)
    icon.save("/tmp/openclaw_army_icon.png")
    print("Saved PNG preview")
    
    icns_path = "/Users/landonking/openclaw-army/app/OpenClawArmy/AppIcon.icns"
    make_icns(icon, icns_path)
    
    # Also put in bundle
    bundle_icns = "/Users/landonking/openclaw-army/app/build/OpenClaw Army.app/Contents/Resources/AppIcon.icns"
    make_icns(icon, bundle_icns)
