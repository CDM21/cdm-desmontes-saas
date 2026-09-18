from pathlib import Path
import io
import sys

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

cv2.setNumThreads(2)

OUTPUT_SIZE = 1600
SAFE_OBJECT_SIZE = 1260
PROXY_MAX = 960


def _resize_proxy(rgb: np.ndarray):
    h, w = rgb.shape[:2]
    scale = min(1.0, PROXY_MAX / max(h, w))
    if scale >= 0.999:
        return rgb.copy(), 1.0
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    return cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA), scale


def _clean_mask(mask: np.ndarray):
    binary = (mask > 0).astype(np.uint8)
    h, w = binary.shape

    # Fecha pequenas falhas sem "comer" extremidades finas da peça.
    close_k = max(3, int(round(min(h, w) * 0.006)))
    if close_k % 2 == 0:
        close_k += 1
    close_k = min(close_k, 9)
    binary = cv2.morphologyEx(
        binary,
        cv2.MORPH_CLOSE,
        np.ones((close_k, close_k), np.uint8),
    )

    # Remove apenas sujeira muito pequena. Componentes reais da peça são preservados.
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    if count > 1:
        areas = stats[1:, cv2.CC_STAT_AREA]
        largest = int(areas.max()) if len(areas) else 0
        keep_min = max(18, int(largest * 0.0015))
        cleaned = np.zeros_like(binary)
        for idx in range(1, count):
            if int(stats[idx, cv2.CC_STAT_AREA]) >= keep_min:
                cleaned[labels == idx] = 1
        if cleaned.any():
            binary = cleaned

    return binary


def _segment_piece(proxy_rgb: np.ndarray):
    h, w = proxy_rgb.shape[:2]
    bgr = cv2.cvtColor(proxy_rgb, cv2.COLOR_RGB2BGR)

    # 1) GrabCut com borda mínima. Diferente da versão antiga, não força
    # grandes faixas laterais nem o centro da imagem, evitando cortar a peça.
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
        3,
        cv2.GC_INIT_WITH_RECT,
    )

    grab = np.where(
        (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD),
        1,
        0,
    ).astype(np.uint8)
    grab = _clean_mask(grab)

    # 2) Recuperação de extremidades: usa flood-fill partindo dos cantos
    # para identificar fundo contínuo e recuperar regiões próximas ao objeto
    # que o GrabCut tenha classificado como fundo por engano.
    flood_bg = np.zeros((h, w), np.uint8)
    flood_src = bgr.copy()
    flood_mask = np.zeros((h + 2, w + 2), np.uint8)
    lo = (24, 24, 24)
    hi = (24, 24, 24)
    for point in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        local_mask = flood_mask.copy()
        work = flood_src.copy()
        try:
            cv2.floodFill(
                work,
                local_mask,
                point,
                (0, 0, 0),
                loDiff=lo,
                upDiff=hi,
                flags=8 | cv2.FLOODFILL_MASK_ONLY | (255 << 8),
            )
            flood_bg = np.maximum(flood_bg, (local_mask[1:-1, 1:-1] > 0).astype(np.uint8))
        except cv2.error:
            pass

    if grab.any():
        recover_k = max(7, int(round(min(h, w) * 0.035)))
        if recover_k % 2 == 0:
            recover_k += 1
        near_piece = cv2.dilate(
            grab,
            np.ones((recover_k, recover_k), np.uint8),
            iterations=1,
        )
        non_corner_background = (flood_bg == 0).astype(np.uint8)
        recovered = non_corner_background & near_piece
        combined = np.maximum(grab, recovered)
    else:
        combined = (flood_bg == 0).astype(np.uint8)

    combined = _clean_mask(combined)

    coverage = float(combined.mean())
    if coverage < 0.008:
        raise RuntimeError("Não foi possível identificar a peça com segurança")

    # Se o fundo for tão complexo que quase tudo virou primeiro plano,
    # tenta uma segunda passagem mais conservadora em vez de gerar um recorte ruim.
    if coverage > 0.92:
        mask2 = np.zeros((h, w), np.uint8)
        inset2 = max(3, int(round(min(h, w) * 0.025)))
        rect2 = (
            inset2,
            inset2,
            max(2, w - inset2 * 2),
            max(2, h - inset2 * 2),
        )
        bg2 = np.zeros((1, 65), np.float64)
        fg2 = np.zeros((1, 65), np.float64)
        cv2.grabCut(bgr, mask2, rect2, bg2, fg2, 5, cv2.GC_INIT_WITH_RECT)
        second = np.where(
            (mask2 == cv2.GC_FGD) | (mask2 == cv2.GC_PR_FGD),
            1,
            0,
        ).astype(np.uint8)
        second = _clean_mask(second)
        second_cov = float(second.mean())
        if 0.008 <= second_cov < coverage:
            combined = second

    # Feather leve apenas na borda para manter aparência natural e nítida.
    alpha = (combined * 255).astype(np.uint8)
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0.55)
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

    # Margem de segurança generosa: a peça nunca fica "colada" ao recorte.
    px = max(8, int(round(obj_w * 0.055)))
    py = max(8, int(round(obj_h * 0.055)))

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

    # Preserva muito mais detalhe que a versão antiga (que reduzia para 420 px).
    max_source = 2600
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

    proxy, proxy_scale = _resize_proxy(rgb)
    proxy_alpha = _segment_piece(proxy)

    # Leva a máscara de volta para a resolução real da foto.
    alpha = cv2.resize(
        proxy_alpha,
        (w, h),
        interpolation=cv2.INTER_LINEAR,
    )
    alpha = np.clip(alpha, 0, 255).astype(np.uint8)

    bbox = _safe_bbox(alpha)
    if bbox is None:
        raise RuntimeError("Não foi possível identificar a peça com segurança")

    x1, y1, x2, y2 = bbox
    crop_rgb = rgb[y1:y2 + 1, x1:x2 + 1]
    crop_alpha = alpha[y1:y2 + 1, x1:x2 + 1]

    obj = Image.fromarray(crop_rgb, "RGB").convert("RGBA")
    obj.putalpha(Image.fromarray(crop_alpha, "L"))

    # Tratamento leve: melhora nitidez sem inventar textura nem alterar a peça.
    rgb_obj = obj.convert("RGB")
    rgb_obj = ImageEnhance.Contrast(rgb_obj).enhance(1.035)
    rgb_obj = ImageEnhance.Brightness(rgb_obj).enhance(1.008)
    rgb_obj = rgb_obj.filter(ImageFilter.UnsharpMask(radius=1.15, percent=115, threshold=3))
    rgb_obj = rgb_obj.convert("RGBA")
    rgb_obj.putalpha(obj.getchannel("A"))
    obj = rgb_obj

    ow, oh = obj.size
    fit = min(
        SAFE_OBJECT_SIZE / max(ow, 1),
        SAFE_OBJECT_SIZE / max(oh, 1),
        1.75,  # evita ampliação exagerada de fotos pequenas
    )
    nw = max(1, int(round(ow * fit)))
    nh = max(1, int(round(oh * fit)))
    obj = obj.resize((nw, nh), Image.Resampling.LANCZOS)

    canvas = Image.new("RGB", (OUTPUT_SIZE, OUTPUT_SIZE), "#FFFFFF")

    # Sombra de estúdio muito discreta. Ajuda a destacar a peça sem "editar" seu formato.
    alpha_obj = obj.getchannel("A")
    shadow_alpha = alpha_obj.filter(ImageFilter.GaussianBlur(radius=max(5, int(OUTPUT_SIZE * 0.007))))
    shadow = Image.new("RGBA", obj.size, (32, 39, 48, 0))
    shadow.putalpha(shadow_alpha.point(lambda p: int(p * 0.13)))

    x = (OUTPUT_SIZE - nw) // 2
    y = (OUTPUT_SIZE - nh) // 2
    shadow_layer = Image.new("RGBA", (OUTPUT_SIZE, OUTPUT_SIZE), (255, 255, 255, 0))
    shadow_layer.alpha_composite(shadow, (x + 5, y + 11))

    result = canvas.convert("RGBA")
    result = Image.alpha_composite(result, shadow_layer)
    result.alpha_composite(obj, (x, y))
    result = result.convert("RGB")

    result.save(
        dst,
        format="JPEG",
        quality=95,
        subsampling=0,
        optimize=True,
    )


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Uso: image_bg_worker.py entrada saida")
    process_image(Path(sys.argv[1]), Path(sys.argv[2]))
