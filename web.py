#!/usr/bin/env python3
"""
LunarLens - Web Viewer (NASA Space Apps 2026)

Servidor web simple: abre la camara, corre YOLO y muestra el video con
las detecciones y los puntajes lunar/marciano en una pagina web.
Sin API JSON: solo una pagina y el video.

Uso:
    python web.py
    Abre en el navegador:  http://<IP-de-la-Jetson>:8080

Atajos en la pagina:  s = guardar   n = cambiar sitio   + / - = confianza
"""

import csv
import os
import sys
import threading
import time
from datetime import datetime

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, PlainTextResponse, StreamingResponse
from ultralytics import YOLO

# ----------------------------------------------------------------------
# CONFIGURACION (se puede cambiar con variables de entorno)
# ----------------------------------------------------------------------
MODEL_PATH = os.getenv(
    "MODEL_PATH",
    "/home/jetson/Desktop/UTD/NASA/rock-dataset/runs/detect/"
    "runs_rocks/prototipo_cautivo/weights/best.pt",
)
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
FRAME_W = int(os.getenv("FRAME_W", "1280"))
FRAME_H = int(os.getenv("FRAME_H", "720"))
CONF = float(os.getenv("CONF", "0.40"))
IMGSZ = int(os.getenv("IMGSZ", "640"))
DEVICE = os.getenv("DEVICE", "0")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "80"))

SITES = [
    ("Pinacate", 31.77, -113.50),
    ("Medanos de Samalayuca", 31.35, -106.48),
    ("Laboratorio UTD", 31.69, -106.42),
]

LUNAR = {"lunar_basalt", "anorthosite", "lunar_breccia"}
MARS = {"hematite"}
# obsidian y pumice_scoria = volcanico terrestre

OUT_DIR = os.getenv("OUT_DIR", "samples")
CSV_PATH = os.path.join(OUT_DIR, "samples.csv")
CSV_HEADER = [
    "timestamp", "site", "lat", "lon",
    "lunar_pct", "mars_pct", "n_rocks", "detections", "image",
]
os.makedirs(OUT_DIR, exist_ok=True)


# ----------------------------------------------------------------------
# AUXILIARES
# ----------------------------------------------------------------------
def draw_text(img, text, pos, scale=0.8, color=(255, 255, 255)):
    cv2.putText(img, text, pos, cv2.FONT_HERSHEY_SIMPLEX,
                scale, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(img, text, pos, cv2.FONT_HERSHEY_SIMPLEX,
                scale, color, 2, cv2.LINE_AA)


def encode_jpeg(img) -> bytes:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    return buf.tobytes() if ok else b""


def compute_scores(result, names):
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


def placeholder_frame(msg: str) -> bytes:
    img = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    draw_text(img, msg, (40, FRAME_H // 2), 1.0, (0, 200, 255))
    return encode_jpeg(img)


# ----------------------------------------------------------------------
# DETECTOR EN SEGUNDO PLANO
# ----------------------------------------------------------------------
class Rig:
    def __init__(self):
        if not os.path.exists(MODEL_PATH):
            print(f"[ERROR] No existe el modelo: {MODEL_PATH}")
            sys.exit(1)
        print("[INFO] Cargando modelo...")
        self.model = YOLO(MODEL_PATH)
        self.names = self.model.names
        self.device = int(DEVICE) if DEVICE.isdigit() else DEVICE

        self.cond = threading.Condition()   # avisa cuando hay frame nuevo
        self.lock = threading.Lock()        # protege conf / sitio / ultimo estado
        self.conf = CONF
        self.site_idx = 0

        self.frame_id = 0
        self.jpeg = placeholder_frame("Iniciando camara...")
        self.last_frame = None              # ultimo frame anotado (para guardar)
        self.last_scores = (0.0, 0.0, 0, [])

        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=3)

    @staticmethod
    def _open_camera():
        cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)
        cap.set(cv2.CAP_PROP_FPS, 30)
        return cap

    def _publish(self, jpeg: bytes):
        with self.cond:
            self.jpeg = jpeg
            self.frame_id += 1
            self.cond.notify_all()

    def _run(self):
        cap = None
        failures = 0
        prev = time.time()
        fps = 0.0

        while not self._stop.is_set():
            if cap is None or not cap.isOpened():
                cap = self._open_camera()
                if not cap.isOpened():
                    cap.release()
                    cap = None
                    self._publish(placeholder_frame(
                        f"Camara no disponible (indice {CAMERA_INDEX})"))
                    time.sleep(2)
                    continue
                print("[INFO] Camara abierta.")
                failures = 0

            ok, frame = cap.read()
            if not ok:
                failures += 1
                if failures > 30:
                    cap.release()
                    cap = None
                time.sleep(0.03)
                continue
            failures = 0

            with self.lock:
                conf = self.conf
                site = SITES[self.site_idx]

            result = self.model.predict(
                frame, conf=conf, imgsz=IMGSZ,
                device=self.device, verbose=False,
            )[0]
            annotated = result.plot()
            lunar_pct, mars_pct, n_rocks, labels = compute_scores(result, self.names)

            now = time.time()
            inst = 1.0 / max(now - prev, 1e-6)
            fps = inst if fps == 0 else 0.9 * fps + 0.1 * inst
            prev = now

            # Panel informativo sobre el video
            draw_text(annotated, f"FPS {fps:.1f}   Conf >= {conf:.2f}",
                      (20, 40), 0.8, (0, 255, 0))
            draw_text(annotated, f"Rocas: {n_rocks}", (20, 80), 0.8)
            draw_text(annotated,
                      f"Lunar: {lunar_pct:.0f}%   Marte: {mars_pct:.0f}%",
                      (20, 120), 0.9, (0, 255, 255))
            draw_text(annotated, f"Sitio: {site[0]}", (20, 160), 0.7)

            with self.lock:
                self.last_frame = annotated.copy()
                self.last_scores = (lunar_pct, mars_pct, n_rocks, labels)

            self._publish(encode_jpeg(annotated))

        if cap is not None:
            cap.release()

    # ---- acciones desde la pagina -------------------------------------
    def save_sample(self) -> str:
        with self.lock:
            frame = None if self.last_frame is None else self.last_frame.copy()
            lunar_pct, mars_pct, n_rocks, labels = self.last_scores
            site = SITES[self.site_idx]
        if frame is None:
            return "Aun no hay video para guardar"
        if n_rocks == 0:
            return "Sin rocas detectadas, no se guardo"

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        img_path = os.path.join(OUT_DIR, f"{ts}.jpg")
        cv2.imwrite(img_path, frame)
        new_file = not os.path.exists(CSV_PATH)
        with open(CSV_PATH, "a", newline="") as f:
            w = csv.writer(f)
            if new_file:
                w.writerow(CSV_HEADER)
            w.writerow([ts, site[0], site[1], site[2],
                        f"{lunar_pct:.1f}", f"{mars_pct:.1f}",
                        n_rocks, ";".join(labels), img_path])
        print(f"[OK] {img_path}")
        return f"Guardada: {ts}.jpg ({site[0]}, lunar {lunar_pct:.0f}%)"

    def next_site(self) -> str:
        with self.lock:
            self.site_idx = (self.site_idx + 1) % len(SITES)
            return f"Sitio: {SITES[self.site_idx][0]}"

    def change_conf(self, delta: float) -> str:
        with self.lock:
            self.conf = round(min(0.95, max(0.05, self.conf + delta)), 2)
            return f"Confianza: {self.conf:.2f}"


rig = Rig()
rig.start()

# ----------------------------------------------------------------------
# PAGINA WEB
# ----------------------------------------------------------------------
PAGE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LunarLens - Rock ID</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 16px; background: #0b0f17; color: #e6edf3;
    font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    display: flex; flex-direction: column; align-items: center; gap: 14px;
  }
  h1 { margin: 0; font-size: 1.3rem; letter-spacing: .5px; }
  h1 span { color: #7dd3fc; }
  .video {
    width: 100%; max-width: 1100px; border-radius: 12px;
    border: 1px solid #243044; background: #000; display: block;
  }
  .bar { display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; }
  button {
    background: #1f6feb; color: #fff; border: 0; border-radius: 8px;
    padding: 12px 18px; font-size: 1rem; cursor: pointer;
  }
  button.alt { background: #243044; }
  button:active { transform: scale(.97); }
  #toast { min-height: 1.4em; color: #7dd3fc; font-size: .95rem; }
  .hint { color: #8b98a9; font-size: .85rem; }
</style>
</head>
<body>
  <h1>Lunar<span>Lens</span> - Rock ID Station</h1>
  <img class="video" src="/video" alt="Video en vivo">
  <div class="bar">
    <button onclick="act('save')">Guardar muestra (s)</button>
    <button class="alt" onclick="act('site')">Cambiar sitio (n)</button>
    <button class="alt" onclick="act('conf_down')">Confianza -</button>
    <button class="alt" onclick="act('conf_up')">Confianza +</button>
  </div>
  <div id="toast"></div>
  <div class="hint">Atajos: s guardar, n sitio, + / - confianza</div>
<script>
  const toast = document.getElementById("toast");
  async function act(name) {
    try {
      const r = await fetch("/do/" + name, { method: "POST" });
      toast.textContent = await r.text();
    } catch (e) {
      toast.textContent = "Sin conexion con el servidor";
    }
  }
  document.addEventListener("keydown", (e) => {
    if (e.key === "s") act("save");
    else if (e.key === "n") act("site");
    else if (e.key === "+" || e.key === "=") act("conf_up");
    else if (e.key === "-" || e.key === "_") act("conf_down");
  });
</script>
</body>
</html>
"""

app = FastAPI(title="LunarLens Web Viewer", docs_url=None, redoc_url=None)


@app.get("/", response_class=HTMLResponse)
def index():
    return PAGE


@app.get("/video")
def video():
    def gen():
        last = -1
        while True:
            with rig.cond:
                rig.cond.wait_for(lambda: rig.frame_id != last, timeout=5)
                jpeg, last = rig.jpeg, rig.frame_id
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                   + jpeg + b"\r\n")
    return StreamingResponse(
        gen(), media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store"},
    )


@app.post("/do/{action}", response_class=PlainTextResponse)
def do_action(action: str):
    if action == "save":
        return rig.save_sample()
    if action == "site":
        return rig.next_site()
    if action == "conf_up":
        return rig.change_conf(+0.05)
    if action == "conf_down":
        return rig.change_conf(-0.05)
    return PlainTextResponse("Accion desconocida", status_code=404)


@app.on_event("shutdown")
def shutdown():
    rig.stop()


if __name__ == "__main__":
    print(f"[INFO] Abre en el navegador: http://<IP-de-la-Jetson>:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
