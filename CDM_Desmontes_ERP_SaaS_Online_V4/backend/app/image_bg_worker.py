from pathlib import Path
import io
import threading
import sys

import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

# CDM FUNDO BRANCO PRO V47
OUTPUT_SIZE = 1600
TARGET_OBJECT_SIZE = 1080
PROXY_MAX = 760
MODEL_INPUT = 320
MODEL_PATH = Path(__file__).resolve().parent / "models" / "u2netp.onnx"

_SESSION = None
_SESSION_LOCK = threading.Lock()
cv2.setNumThreads(1)


def _get_session():
    global _SESSION
    if _SESSION is not None:
        return _SESSION
    with _SESSION_LOCK:
        if _SESSION is not None:
            return _SESSION
        if not MODEL_PATH.exists():
            raise RuntimeError("Modelo local do Fundo Branco CDM Pro não encontrado")
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        _SESSION = ort.InferenceSession(
            str(MODEL_PATH),
            sess_options=opts,
            providers=["CPUExecutionProvider"],
        )
        return _SESSION


def _resize_proxy(rgb):
    h, w = rgb.shape[:2]
    scale = min(1.0, PROXY_MAX / max(h, w))
    if scale >= 0.999:
        return rgb.copy()
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    return cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA)


def _clean_components(binary):
    binary = (binary > 0).astype(np.uint8)
    h, w = binary.shape
    k = max(3, int(round(min(h, w) * 0.004)))
    if k % 2 == 0:
        k += 1
    k = min(k, 7)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8), iterations=1)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    if count <= 1:
        return binary
    areas = stats[1:, cv2.CC_STAT_AREA]
    largest = int(areas.max()) if len(areas) else 0
    keep_min = max(8, int(largest * 0.00055))
    cleaned = np.zeros_like(binary)
    for idx in range(1, count):
        if int(stats[idx, cv2.CC_STAT_AREA]) >= keep_min:
            cleaned[labels == idx] = 1
    return cleaned if cleaned.any() else binary


def _u2net_alpha(proxy_rgb):
    session = _get_session()
    small = cv2.resize(proxy_rgb, (MODEL_INPUT, MODEL_INPUT), interpolation=cv2.INTER_AREA)
    arr = small.astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(1, 1, 3)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(1, 1, 3)
    arr = (arr - mean) / std
    tensor = np.transpose(arr, (2, 0, 1))[None, ...].astype(np.float32)
    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: tensor})
    if not outputs:
        raise RuntimeError("Modelo local não retornou máscara")
    pred = np.asarray(outputs[0], dtype=np.float32)
    if pred.ndim == 4:
        pred = pred[:, 0, :, :]
    pred = np.squeeze(pred)
    if pred.ndim != 2:
        raise RuntimeError("Máscara local inválida")
    lo = float(pred.min())
    hi = float(pred.max())
    if hi - lo < 1e-7:
        raise RuntimeError("Máscara local sem contraste")
    pred = (pred - lo) / (hi - lo)
    h, w = proxy_rgb.shape[:2]
    alpha = cv2.resize(pred, (w, h), interpolation=cv2.INTER_CUBIC)
    return np.clip(alpha * 255.0, 0, 255).astype(np.uint8)


def _refine_alpha(proxy_rgb, alpha):
    h, w = alpha.shape
    support = _clean_components((alpha >= 20).astype(np.uint8))
    alpha = alpha.copy()
    alpha[support == 0] = 0
    coverage = float((alpha >= 40).mean())
    if coverage < 0.004:
        raise RuntimeError("Não foi possível identificar a peça com segurança")
    if coverage > 0.94:
        raise RuntimeError("Fundo muito complexo para recorte automático")
    try:
        gc = np.full((h, w), cv2.GC_PR_BGD, dtype=np.uint8)
        gc[alpha <= 12] = cv2.GC_BGD
        gc[(alpha > 12) & (alpha < 92)] = cv2.GC_PR_BGD
        gc[(alpha >= 92) & (alpha < 220)] = cv2.GC_PR_FGD
        gc[alpha >= 220] = cv2.GC_FGD
        border = max(2, int(round(min(h, w) * 0.006)))
        gc[:border, :] = cv2.GC_BGD
        gc[-border:, :] = cv2.GC_BGD
        gc[:, :border] = cv2.GC_BGD
        gc[:, -border:] = cv2.GC_BGD
        bg_model = np.zeros((1, 65), np.float64)
        fg_model = np.zeros((1, 65), np.float64)
        cv2.grabCut(cv2.cvtColor(proxy_rgb, cv2.COLOR_RGB2BGR), gc, None, bg_model, fg_model, 1, cv2.GC_INIT_WITH_MASK)
        grab = np.where((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD), 1, 0).astype(np.uint8)
        grab = _clean_components(grab)
        allowed = cv2.dilate(grab, np.ones((3, 3), np.uint8), iterations=1)
        core = cv2.erode(grab, np.ones((3, 3), np.uint8), iterations=1)
        alpha[allowed == 0] = 0
        alpha[core > 0] = np.maximum(alpha[core > 0], 238)
    except Exception:
        pass
    alpha[alpha < 13] = 0
    alpha[alpha > 244] = 255
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0.48)
    alpha[alpha < 8] = 0
    alpha[alpha > 250] = 255
    return alpha


def _safe_bbox(alpha):
    ys, xs = np.where(alpha > 18)
    if len(xs) < 40 or len(ys) < 40:
        return None
    h, w = alpha.shape
    x1, x2 = int(xs.min()), int(xs.max())
    y1, y2 = int(ys.min()), int(ys.max())
    obj_w = x2 - x1 + 1
    obj_h = y2 - y1 + 1
    px = max(5, int(round(obj_w * 0.022)))
    py = max(5, int(round(obj_h * 0.022)))
    return (max(0, x1 - px), max(0, y1 - py), min(w - 1, x2 + px), min(h - 1, y2 + py))


def _enhance_object(obj):
    alpha = obj.getchannel("A")
    rgb = obj.convert("RGB")
    rgb = ImageEnhance.Contrast(rgb).enhance(1.035)
    rgb = ImageEnhance.Color(rgb).enhance(1.012)
    rgb = ImageEnhance.Brightness(rgb).enhance(1.008)
    rgb = rgb.filter(ImageFilter.UnsharpMask(radius=0.85, percent=90, threshold=4))
    out = rgb.convert("RGBA")
    out.putalpha(alpha)
    return out


def process_image(src, dst):
    raw = src.read_bytes()
    pil = Image.open(io.BytesIO(raw))
    pil = ImageOps.exif_transpose(pil).convert("RGB")
    max_source = 2600
    if max(pil.size) > max_source:
        scale = max_source / max(pil.size)
        pil = pil.resize((max(1, int(round(pil.width * scale))), max(1, int(round(pil.height * scale)))), Image.Resampling.LANCZOS)
    rgb = np.array(pil)
    h, w = rgb.shape[:2]
    if h < 80 or w < 80:
        raise RuntimeError("Imagem pequena demais para tratamento")
    proxy = _resize_proxy(rgb)
    proxy_alpha = _u2net_alpha(proxy)
    proxy_alpha = _refine_alpha(proxy, proxy_alpha)
    alpha = cv2.resize(proxy_alpha, (w, h), interpolation=cv2.INTER_CUBIC)
    alpha = np.clip(alpha, 0, 255).astype(np.uint8)
    alpha[alpha < 8] = 0
    alpha[alpha > 250] = 255
    bbox = _safe_bbox(alpha)
    if bbox is None:
        raise RuntimeError("Não foi possível identificar a peça com segurança")
    x1, y1, x2, y2 = bbox
    crop_rgb = rgb[y1:y2 + 1, x1:x2 + 1]
    crop_alpha = alpha[y1:y2 + 1, x1:x2 + 1]
    obj = Image.fromarray(crop_rgb, "RGB").convert("RGBA")
    obj.putalpha(Image.fromarray(crop_alpha, "L"))
    obj = _enhance_object(obj)
    ow, oh = obj.size
    fit = min(TARGET_OBJECT_SIZE / max(ow, 1), TARGET_OBJECT_SIZE / max(oh, 1), 2.10)
    nw = max(1, int(round(ow * fit)))
    nh = max(1, int(round(oh * fit)))
    obj = obj.resize((nw, nh), Image.Resampling.LANCZOS)
    out = Image.new("RGB", (OUTPUT_SIZE, OUTPUT_SIZE), "#FFFFFF")
    x = (OUTPUT_SIZE - nw) // 2
    y = (OUTPUT_SIZE - nh) // 2
    out.paste(obj, (x, y), obj)
    out.save(dst, format="JPEG", quality=95, subsampling=0, optimize=True)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Uso: image_bg_worker.py entrada saida")
    process_image(Path(sys.argv[1]), Path(sys.argv[2]))
