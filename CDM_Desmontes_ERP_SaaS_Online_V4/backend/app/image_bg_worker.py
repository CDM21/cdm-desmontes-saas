from pathlib import Path
import io
import sys

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

cv2.setNumThreads(2)

OUTPUT_SIZE = 1600
SAFE_OBJECT_SIZE = 1240
PROXY_MAX = 560


def _resize_proxy(rgb: np.ndarray):
    h, w = rgb.shape[:2]
    scale = min(1.0, PROXY_MAX / max(h, w))
    if scale >= 0.999:
        return rgb.copy()
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    return cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA)


def _clean_mask(binary: np.ndarray):
    binary = (binary > 0).astype(np.uint8)
    h, w = binary.shape

    k = max(3, int(round(min(h, w) * 0.006)))
    if k % 2 == 0:
        k += 1
    k = min(k, 7)
    binary = cv2.morphologyEx(
        binary,
        cv2.MORPH_CLOSE,
        np.ones((k, k), np.uint8),
    )

    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    if count <= 1:
        return binary

    areas = stats[1:, cv2.CC_STAT_AREA]
    largest = int(areas.max()) if len(areas) else 0
    keep_min = max(14, int(largest * 0.0012))

    cleaned = np.zeros_like(binary)
    for idx in range(1, count):
        if int(stats[idx, cv2.CC_STAT_AREA]) >= keep_min:
            cleaned[labels == idx] = 1

    return cleaned if cleaned.any() else binary


def _recover_object_edges(proxy_rgb: np.ndarray, grab: np.ndarray):
    h, w = grab.shape

    border = max(2, int(round(min(h, w) * 0.025)))
    samples = np.concatenate([
        proxy_rgb[:border, :, :].reshape(-1, 3),
        proxy_rgb[-border:, :, :].reshape(-1, 3),
        proxy_rgb[:, :border, :].reshape(-1, 3),
        proxy_rgb[:, -border:, :].reshape(-1, 3),
    ], axis=0)

    if len(samples) < 8:
        return grab

    bg = np.median(samples.astype(np.float32), axis=0)
    diff = proxy_rgb.astype(np.float32) - bg.reshape(1, 1, 3)
    dist = np.sqrt(np.sum(diff * diff, axis=2))

    dilate_k = max(9, int(round(min(h, w) * 0.055)))
    if dilate_k % 2 == 0:
        dilate_k += 1
    near = cv2.dilate(
        grab,
        np.ones((dilate_k, dilate_k), np.uint8),
        iterations=1,
    )

    color_candidate = (dist > 30.0).astype(np.uint8)

    gray = cv2.cvtColor(proxy_rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 55, 145)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
    edge_candidate = (edges > 0).astype(np.uint8)

    recovered = near & np.maximum(color_candidate, edge_candidate)
    combined = np.maximum(grab, recovered)
    return _clean_mask(combined)


def _segment_piece(proxy_rgb: np.ndarray):
    h, w = proxy_rgb.shape[:2]
    bgr = cv2.cvtColor(proxy_rgb, cv2.COLOR_RGB2BGR)

    inset = max(2, int(round(min(h, w) * 0.012)))
    rect = (
        inset,
        inset,
        max(2, w - inset * 2),
        max(2, h - inset * 2),
    )

    mask = np.zeros((h, w), np.uint8)
    bg_model = np.zeros((1, 65), np.float64)
    fg_model = np.zeros((1, 65), np.float64)

    cv2.grabCut(
        bgr,
        mask,
        rect,
        bg_model,
        fg_model,
        2,
        cv2.GC_INIT_WITH_RECT,
    )

    grab = np.where(
        (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD),
        1,
        0,
    ).astype(np.uint8)
    grab = _clean_mask(grab)
    grab = _recover_object_edges(proxy_rgb, grab)

    coverage = float(grab.mean())
    if coverage < 0.006:
        raise RuntimeError("Não foi possível identificar a peça com segurança")
    if coverage > 0.96:
        raise RuntimeError("Fundo muito complexo para recorte automático. Tente outra foto ou refaça o tratamento.")

    alpha = (grab * 255).astype(np.uint8)
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0.5)
    return alpha


def _safe_bbox(alpha: np.ndarray):
    ys, xs = np.where(alpha > 10)
    if len(xs) < 50 or len(ys) < 50:
        return None

    h, w = alpha.shape
    x1, x2 = int(xs.min()), int(xs.max())
    y1, y2 = int(ys.min()), int(ys.max())

    obj_w = x2 - x1 + 1
    obj_h = y2 - y1 + 1

    px = max(10, int(round(obj_w * 0.065)))
    py = max(10, int(round(obj_h * 0.065)))

    return (
        max(0, x1 - px),
        max(0, y1 - py),
        min(w - 1, x2 + px),
        min(h - 1, y2 + py),
    )


def process_image(src: Path, dst: Path):
    raw = src.read_bytes()
    pil = Image.open(io.BytesIO(raw))
    pil = ImageOps.exif_transpose(pil).convert("RGB")

    max_source = 2200
    if max(pil.size) > max_source:
        scale = max_source / max(pil.size)
        pil = pil.resize(
            (
                max(1, int(round(pil.width * scale))),
                max(1, int(round(pil.height * scale))),
            ),
            Image.Resampling.LANCZOS,
        )

    rgb = np.array(pil)
    h, w = rgb.shape[:2]
    if h < 80 or w < 80:
        raise RuntimeError("Imagem pequena demais para tratamento")

    proxy = _resize_proxy(rgb)
    proxy_alpha = _segment_piece(proxy)

    alpha = cv2.resize(proxy_alpha, (w, h), interpolation=cv2.INTER_LINEAR)
    alpha = np.clip(alpha, 0, 255).astype(np.uint8)

    bbox = _safe_bbox(alpha)
    if bbox is None:
        raise RuntimeError("Não foi possível identificar a peça com segurança")

    x1, y1, x2, y2 = bbox
    crop_rgb = rgb[y1:y2 + 1, x1:x2 + 1]
    crop_alpha = alpha[y1:y2 + 1, x1:x2 + 1]

    obj = Image.fromarray(crop_rgb, "RGB").convert("RGBA")
    obj.putalpha(Image.fromarray(crop_alpha, "L"))

    ow, oh = obj.size
    fit = min(
        SAFE_OBJECT_SIZE / max(ow, 1),
        SAFE_OBJECT_SIZE / max(oh, 1),
        1.60,
    )
    nw = max(1, int(round(ow * fit)))
    nh = max(1, int(round(oh * fit)))
    obj = obj.resize((nw, nh), Image.Resampling.LANCZOS)

    alpha_obj = obj.getchannel("A")
    rgb_obj = obj.convert("RGB")
    rgb_obj = ImageEnhance.Contrast(rgb_obj).enhance(1.025)
    rgb_obj = rgb_obj.filter(ImageFilter.UnsharpMask(radius=0.8, percent=85, threshold=4))
    obj = rgb_obj.convert("RGBA")
    obj.putalpha(alpha_obj)

    out = Image.new("RGB", (OUTPUT_SIZE, OUTPUT_SIZE), "#FFFFFF")
    x = (OUTPUT_SIZE - nw) // 2
    y = (OUTPUT_SIZE - nh) // 2
    out.paste(obj, (x, y), obj)

    out.save(dst, format="JPEG", quality=93, subsampling=0)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Uso: image_bg_worker.py entrada saida")
    process_image(Path(sys.argv[1]), Path(sys.argv[2]))
