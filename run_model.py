#!/usr/bin/env python3
"""
Analog Finder - Rock ID Station (NASA Space Apps 2026)

Detecta rocas con YOLO en la webcam, calcula un puntaje de parecido
"lunar" y "marciano" y guarda muestras (foto + CSV) para el mapa.

Teclas:
  s = guardar muestra      n = cambiar de sitio
  + / - = subir/bajar confianza      q = salir
"""

import csv
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
from ultralytics import YOLO

# ----------------------------------------------------------------------
# CONFIGURACION
# ----------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
MODEL_PATH = os.getenv("MODEL_PATH", str(PROJECT_ROOT / "model.pt"))
# Cuando exportes a TensorRT, cambia a ".../best.engine"

CAMERA_INDEX = 0
FRAME_W, FRAME_H = 1280, 720
CONF = 0.40
IMGSZ = 640

# Sitios de muestreo (nombre, latitud, longitud). Edita a tu gusto.
SITES = [
    ("Pinacate", 31.77, -113.50),
    ("Medanos de Samalayuca", 31.35, -106.48),
    ("Laboratorio UTD", 31.69, -106.42),
]

# Clases del dataset
LUNAR = {"lunar_basalt", "anorthosite", "lunar_breccia"}
MARS = {"hematite"}
# obsidian y pumice_scoria = volcanico terrestre (no suman a ninguno)

OUT_DIR = "samples"
CSV_PATH = os.path.join(OUT_DIR, "samples.csv")
CSV_HEADER = [
    "timestamp", "site", "lat", "lon",
    "lunar_pct", "mars_pct", "n_rocks", "detections", "image",
]
WINDOW = "Analog Finder - Rock ID"


# ----------------------------------------------------------------------
# FUNCIONES AUXILIARES
# ----------------------------------------------------------------------
def draw_text(img, text, pos, scale=0.8, color=(255, 255, 255)):
    """Texto con borde negro para que se lea sobre cualquier fondo."""
    cv2.putText(img, text, pos, cv2.FONT_HERSHEY_SIMPLEX,
                scale, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(img, text, pos, cv2.FONT_HERSHEY_SIMPLEX,
                scale, color, 2, cv2.LINE_AA)


def open_camera(index):
    backends = [cv2.CAP_V4L2, cv2.CAP_ANY]
    last_error = None
    for backend in backends:
        try:
            cap = cv2.VideoCapture(index, backend)
        except Exception as exc:  # pragma: no cover - backend-dependent
            last_error = exc
            continue
        if cap is None or not cap.isOpened():
            last_error = RuntimeError(f"No se pudo abrir la camara con backend {backend}")
            continue
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)
        cap.set(cv2.CAP_PROP_FPS, 30)
        return cap
    if last_error is not None:
        raise last_error
    return cv2.VideoCapture(index)


def init_csv():
    os.makedirs(OUT_DIR, exist_ok=True)
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, "w", newline="") as f:
            csv.writer(f).writerow(CSV_HEADER)


def compute_scores(result, names):
    """Devuelve (lunar_pct, mars_pct, n_rocks, lista_de_etiquetas)."""
    total = lunar = mars = 0.0
    labels = []
    for box in result.boxes:
        cls_name = names[int(box.cls)]
        conf = float(box.conf)
        total += conf
        if cls_name in LUNAR:
            lunar += conf
        if cls_name in MARS:
            mars += conf
        labels.append(f"{cls_name}:{conf:.2f}")
    if total == 0:
        return 0.0, 0.0, 0, labels
    return 100 * lunar / total, 100 * mars / total, len(labels), labels


def save_sample(frame, site, lunar_pct, mars_pct, n_rocks, labels):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    img_path = os.path.join(OUT_DIR, f"{ts}.jpg")
    cv2.imwrite(img_path, frame)
    name, lat, lon = site
    with open(CSV_PATH, "a", newline="") as f:
        csv.writer(f).writerow([
            ts, name, lat, lon,
            f"{lunar_pct:.1f}", f"{mars_pct:.1f}",
            n_rocks, ";".join(labels), img_path,
        ])
    return img_path


# ----------------------------------------------------------------------
# PROGRAMA PRINCIPAL
# ----------------------------------------------------------------------
def main():
    if not os.path.exists(MODEL_PATH):
        print(f"[ERROR] No existe el modelo: {MODEL_PATH}")
        sys.exit(1)

    print("[INFO] Cargando modelo...")
    model = YOLO(MODEL_PATH)
    names = model.names

    init_csv()

    cap = open_camera(CAMERA_INDEX)
    if not cap.isOpened():
        print(f"[ERROR] No se pudo abrir la camara (indice {CAMERA_INDEX}).")
        print("        Revisa con: ls /dev/video*")
        sys.exit(1)

    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW, FRAME_W, FRAME_H)

    conf = CONF
    site_idx = 0
    prev = time.time()
    fps = 0.0
    flash_until = 0.0
    flash_msg = ""

    print("[INFO] Listo. s=guardar  n=sitio  +/-=confianza  q=salir")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("[ERROR] No se recibe video de la camara.")
                break

            result = model.predict(
                frame, conf=conf, imgsz=IMGSZ, device=0, verbose=False
            )[0]
            annotated = result.plot()

            lunar_pct, mars_pct, n_rocks, labels = compute_scores(result, names)

            # FPS suavizado
            now = time.time()
            inst = 1.0 / max(now - prev, 1e-6)
            fps = inst if fps == 0 else 0.9 * fps + 0.1 * inst
            prev = now

            site = SITES[site_idx]

            # Panel de informacion
            draw_text(annotated, f"FPS {fps:.1f}   Conf >= {conf:.2f}",
                      (20, 40), 0.8, (0, 255, 0))
            draw_text(annotated, f"Rocas: {n_rocks}", (20, 80), 0.8)
            draw_text(annotated,
                      f"Lunar: {lunar_pct:.0f}%   Marte: {mars_pct:.0f}%",
                      (20, 120), 0.9, (0, 255, 255))
            draw_text(annotated, f"Sitio: {site[0]}", (20, 160), 0.7)
            draw_text(annotated,
                      "[s] guardar  [n] sitio  [+/-] conf  [q] salir",
                      (20, FRAME_H - 20), 0.6)

            if now < flash_until:
                draw_text(annotated, flash_msg, (20, 205), 0.8, (0, 200, 255))

            cv2.imshow(WINDOW, annotated)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("s"):
                if n_rocks == 0:
                    flash_msg = "Sin rocas detectadas, no se guardo"
                else:
                    path = save_sample(annotated, site, lunar_pct,
                                       mars_pct, n_rocks, labels)
                    flash_msg = f"Guardada: {os.path.basename(path)}"
                    print(f"[OK] {path}")
                flash_until = now + 2.0
            elif key == ord("n"):
                site_idx = (site_idx + 1) % len(SITES)
            elif key in (ord("+"), ord("=")):
                conf = min(0.95, conf + 0.05)
            elif key in (ord("-"), ord("_")):
                conf = max(0.05, conf - 0.05)
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
