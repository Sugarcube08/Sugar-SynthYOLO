import os
from datetime import datetime
import random
from PIL import Image, ImageDraw, ImageFont

# ---------- CONFIG ----------
CANVAS_SIZE = (1024, 1024)      # final canvas size
FONT_DIR = "fonts"              # folder with .ttf/.otf/.ttc fonts
INPUT_IMAGE = "input.png"       # your clean template
N_SAMPLES = int(input("Enter N-Sample: "))                  # how many samples to generate
MAX_ROT = 15                    # rotation range (-MAX_ROT .. +MAX_ROT)
# ----------------------------

# YOLO-style boxes defined relative to the *placed input image* (normalized 0..1)
BOXES = [
    (0, 0.23, 0.7, 0.35, 0.35),  # Qty
    (1, 0.70, 0.7, 0.5,  0.35)   # Price
]


def get_all_fonts():
    """Return list of font file paths supporting common extensions."""
    if not os.path.isdir(FONT_DIR):
        return []
    exts = (".ttf", ".otf", ".ttc")
    return [os.path.join(FONT_DIR, f) for f in os.listdir(FONT_DIR) if f.lower().endswith(exts)]


def validate_font(path):
    """Quick check that the font can be loaded and draws digits (avoid symbol-only fonts)."""
    try:
        font = ImageFont.truetype(path, 40)
        img = Image.new("RGB", (200, 80), (255, 255, 255))
        d = ImageDraw.Draw(img)
        bbox = d.textbbox((0, 0), "0123456789", font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        return (w > 0 and h > 0)
    except Exception:
        return False


# load & filter fonts
ALL_FONTS = [f for f in get_all_fonts() if validate_font(f)]
if len(ALL_FONTS) == 0:
    if os.path.exists("jah.ttf"):
        ALL_FONTS = ["jah.ttf"]
    else:
        ALL_FONTS = []


def choose_font_for_size(font_path_hint, size):
    """Return an ImageFont instance. If font_path_hint is None pick random from ALL_FONTS."""
    if font_path_hint:
        try:
            return ImageFont.truetype(font_path_hint, size)
        except Exception:
            pass
    if len(ALL_FONTS) > 0:
        return ImageFont.truetype(random.choice(ALL_FONTS), size)
    else:
        return ImageFont.load_default()


def random_int_value():
    """Return integer between 1 and 9999 (no decimals)."""
    return str(random.randint(1, 9999))


def yolo_to_pixel(box, base_w, base_h, offset_x=0, offset_y=0):
    """Convert YOLO (class_id, xc, yc, w, h) relative to base image to pixel bbox on canvas."""
    class_id, xc, yc, w, h = box
    xc_px = xc * base_w
    yc_px = yc * base_h
    w_px = w * base_w
    h_px = h * base_h

    xmin = int(xc_px - w_px / 2) + offset_x
    ymin = int(yc_px - h_px / 2) + offset_y
    xmax = int(xc_px + w_px / 2) + offset_x
    ymax = int(yc_px + h_px / 2) + offset_y

    xmin = max(0, xmin)
    ymin = max(0, ymin)
    xmax = min(CANVAS_SIZE[0] - 1, xmax)
    ymax = min(CANVAS_SIZE[1] - 1, ymax)

    return int(class_id), (xmin, ymin, xmax, ymax)


def create_rotated_text_image(text, box_w, box_h, font_path=None, angle=0):
    """Create RGBA image of text rotated by `angle` that fits inside (box_w, box_h)."""
    font_size = max(10, int(box_h * random.uniform(0.5, 0.9)))
    used_font_path = font_path if font_path else (random.choice(ALL_FONTS) if ALL_FONTS else None)

    while font_size >= 10:
        try:
            font = choose_font_for_size(used_font_path, font_size)
        except Exception:
            used_font_path = random.choice(ALL_FONTS) if ALL_FONTS else None
            font = choose_font_for_size(used_font_path, font_size)

        tmp_img = Image.new("RGBA", (2000, 2000), (0, 0, 0, 0))
        tmp_draw = ImageDraw.Draw(tmp_img)
        bbox = tmp_draw.textbbox((0, 0), text, font=font)
        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

        if text_w <= 0 or text_h <= 0:
            font_size -= 2
            continue

        txt_img = Image.new("RGBA", (text_w, text_h), (0, 0, 0, 0))
        txt_draw = ImageDraw.Draw(txt_img)
        txt_draw.text((-bbox[0], -bbox[1]), text, font=font, fill=(0, 0, 0, 255))

        rotated = txt_img.rotate(angle, expand=True, resample=Image.BICUBIC)
        rot_w, rot_h = rotated.size

        if rot_w <= box_w and rot_h <= box_h:
            return rotated, used_font_path, font_size

        font_size -= 2

    font = choose_font_for_size(used_font_path, max(10, font_size))
    tmp_img = Image.new("RGBA", (2000, 2000), (0, 0, 0, 0))
    tmp_draw = ImageDraw.Draw(tmp_img)
    bbox = tmp_draw.textbbox((0, 0), text, font=font)
    text_w, text_h = max(1, bbox[2] - bbox[0]), max(1, bbox[3] - bbox[1])
    txt_img = Image.new("RGBA", (text_w, text_h), (0, 0, 0, 0))
    txt_draw = ImageDraw.Draw(txt_img)
    txt_draw.text((-bbox[0], -bbox[1]), text, font=font, fill=(0, 0, 0, 255))
    rotated = txt_img.rotate(angle, expand=True, resample=Image.BICUBIC)
    return rotated, used_font_path, max(10, font_size)


def ensure_dir(d):
    if not os.path.exists(d):
        os.makedirs(d)


def generate_dataset(input_img_path, n_samples=10):
    ensure_dir("dataset/images")
    ensure_dir("dataset/labels")
    ensure_dir("dataset/debug")
    
    base = Image.open(input_img_path).convert("RGB")
    base_w, base_h = base.size

    if base_w > CANVAS_SIZE[0] or base_h > CANVAS_SIZE[1]:
        scale = min(CANVAS_SIZE[0] / base_w, CANVAS_SIZE[1] / base_h)
        base_w, base_h = int(base_w * scale), int(base_h * scale)
        base = base.resize((base_w, base_h), resample=Image.BICUBIC)

    for i in range(n_samples):
        start = datetime.now()

        canvas_clean = Image.new("RGB", CANVAS_SIZE, (255, 255, 255))
        canvas_debug = Image.new("RGB", CANVAS_SIZE, (255, 255, 255))

        max_x = CANVAS_SIZE[0] - base_w
        max_y = CANVAS_SIZE[1] - base_h
        offset_x = random.randint(0, max_x) if max_x > 0 else 0
        offset_y = random.randint(0, max_y) if max_y > 0 else 0

        canvas_clean.paste(base, (offset_x, offset_y))
        canvas_debug.paste(base, (offset_x, offset_y))

        label_lines = []
        qty_val = price_val = None

        same_font = random.choice([True, False])
        shared_font = random.choice(ALL_FONTS) if (same_font and ALL_FONTS) else None

        for box in BOXES:
            class_id, pixel_box = yolo_to_pixel(box, base_w, base_h, offset_x, offset_y)
            xmin, ymin, xmax, ymax = pixel_box
            box_w, box_h = xmax - xmin, ymax - ymin

            number = random_int_value()
            if class_id == 0:
                qty_val = number
            else:
                price_val = number

            font_for_field = shared_font if shared_font else (random.choice(ALL_FONTS) if ALL_FONTS else None)
            angle = random.randint(-MAX_ROT, MAX_ROT)

            rotated_txt_img, _, _ = create_rotated_text_image(number, box_w, box_h, font_for_field, angle)
            tw, th = rotated_txt_img.size

            paste_x = xmin + (box_w - tw) // 2
            paste_y = ymin + (box_h - th) // 2

            canvas_clean.paste(rotated_txt_img, (paste_x, paste_y), rotated_txt_img)
            canvas_debug.paste(rotated_txt_img, (paste_x, paste_y), rotated_txt_img)

            draw_dbg = ImageDraw.Draw(canvas_debug)
            draw_dbg.rectangle([xmin, ymin, xmax, ymax], outline="red", width=2)

            xc = (xmin + xmax) / 2.0 / CANVAS_SIZE[0]
            yc = (ymin + ymax) / 2.0 / CANVAS_SIZE[1]
            w_norm = (xmax - xmin) / CANVAS_SIZE[0]
            h_norm = (ymax - ymin) / CANVAS_SIZE[1]

            label_lines.append(f"{class_id} {xc:.6f} {yc:.6f} {w_norm:.6f} {h_norm:.6f} {number}")

        img_name = f"sample_{i}.png"
        canvas_clean.save(os.path.join("dataset/images", img_name))
        canvas_debug.save(os.path.join("dataset/debug", img_name))

        with open(os.path.join("dataset/labels", f"sample_{i}.txt"), "w") as lf:
            lf.write("\n".join(label_lines))
            lf.write(f"\nQty={qty_val} Price={price_val}")

        end = datetime.now()
        print(f"Generating sample {i+1}/{n_samples} in {end-start}", end="\r")

    print(f"✅ Generated {n_samples} samples")
    print(" - dataset/images/   -> clean images")
    print(" - dataset/labels/   -> yolo .txt with appended numbers")
    print(" - dataset/debug/    -> debug images")


if __name__ == "__main__":
    generate_dataset(INPUT_IMAGE, n_samples=N_SAMPLES)
