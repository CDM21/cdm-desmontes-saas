from pathlib import Path
import io
import sys

import cv2
import numpy as np
from PIL import Image, ImageEnhance

cv2.setNumThreads(1)

def process_image(src: Path, dst: Path):
    raw = src.read_bytes()
    pil = Image.open(io.BytesIO(raw)).convert("RGB")
    pil.thumbnail((700, 700), Image.Resampling.LANCZOS)

    rgb = np.array(pil)
    h, w = rgb.shape[:2]
    if h < 40 or w < 40:
        raise RuntimeError("Imagem pequena demais para tratamento")

    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    mask = np.full((h, w), cv2.GC_PR_BGD, dtype=np.uint8)
    border = max(3, int(min(h, w) * 0.025))

    mask[:border, :] = cv2.GC_BGD
    mask[h-border:, :] = cv2.GC_BGD
    mask[:, :border] = cv2.GC_BGD
    mask[:, w-border:] = cv2.GC_BGD

    x1, x2 = int(w * 0.08), int(w * 0.92)
    y1, y2 = int(h * 0.08), int(h * 0.92)
    mask[y1:y2, x1:x2] = cv2.GC_PR_FGD

    fx1, fx2 = int(w * 0.30), int(w * 0.70)
    fy1, fy2 = int(h * 0.30), int(h * 0.70)
    mask[fy1:fy2, fx1:fx2] = cv2.GC_FGD

    bg_model = np.zeros((1, 65), np.float64)
    fg_model = np.zeros((1, 65), np.float64)

    cv2.grabCut(
        bgr,
        mask,
        None,
        bg_model,
        fg_model,
        3,
        cv2.GC_INIT_WITH_MASK,
    )

    alpha = np.where(
        (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD),
        255,
        0,
    ).astype(np.uint8)

    k = max(3, int(min(h, w) * 0.005))
    if k % 2 == 0:
        k += 1
    k = min(k, 9)
    kernel = np.ones((k, k), np.uint8)

    alpha = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, kernel)
    alpha = cv2.morphologyEx(alpha, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    alpha = cv2.GaussianBlur(alpha, (5, 5), 0)

    ys, xs = np.where(alpha > 18)
    if len(xs) < 50 or len(ys) < 50:
        raise RuntimeError("Não foi possível identificar a peça com segurança")

    min_x, max_x = int(xs.min()), int(xs.max())
    min_y, max_y = int(ys.min()), int(ys.max())

    pad = max(8, int(max(w, h) * 0.015))
    min_x = max(0, min_x - pad)
    min_y = max(0, min_y - pad)
    max_x = min(w - 1, max_x + pad)
    max_y = min(h - 1, max_y + pad)

    crop_rgb = rgb[min_y:max_y+1, min_x:max_x+1]
    crop_alpha = alpha[min_y:max_y+1, min_x:max_x+1].astype(np.float32) / 255.0
    crop_alpha = crop_alpha[..., None]

    composite = (
        crop_rgb.astype(np.float32) * crop_alpha
        + 255.0 * (1.0 - crop_alpha)
    )
    composite = np.clip(composite, 0, 255).astype(np.uint8)

    comp = Image.fromarray(composite)
    comp = ImageEnhance.Contrast(comp).enhance(1.06)
    comp = ImageEnhance.Sharpness(comp).enhance(1.12)
    comp = ImageEnhance.Color(comp).enhance(1.02)

    out_size = 1200
    margin = 115
    cw, ch = comp.size
    fit = min(
        (out_size - 2 * margin) / max(cw, 1),
        (out_size - 2 * margin) / max(ch, 1),
    )
    nw = max(1, int(round(cw * fit)))
    nh = max(1, int(round(ch * fit)))

    comp = comp.resize((nw, nh), Image.Resampling.LANCZOS)
    out = Image.new("RGB", (out_size, out_size), "white")
    out.paste(comp, ((out_size - nw) // 2, (out_size - nh) // 2))
    out.save(dst, format="JPEG", quality=94, subsampling=0, optimize=True)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Uso: image_bg_worker.py entrada saida")
    process_image(Path(sys.argv[1]), Path(sys.argv[2]))
