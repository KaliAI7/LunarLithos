import sys
import time
from pathlib import Path

import cv2

from rock_api.camera import SITES, draw_text, open_camera
from rock_api.config import get_settings
from rock_api.detector import RockDetector
from rock_api.storage import ObservationStore


def main():
    settings = get_settings()
    detector = RockDetector(settings)
    store = ObservationStore(settings.database_path)
    capture = open_camera(settings)
    if not capture.isOpened():
        capture.release()
        print(f"[ERROR] Could not open camera index {settings.camera_index}.")
        sys.exit(1)

    window = "LunarLens - Rock ID"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, settings.frame_width, settings.frame_height)
    confidence = settings.confidence
    site_index = 0
    previous_frame_time = time.time()
    fps = 0.0
    flash_message = ""
    flash_until = 0.0
    print("[INFO] Ready. Press s to save, n to change site, q to quit.")

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                print("[ERROR] No camera frame received.")
                break

            inference = detector.predict(frame, confidence)
            annotated = detector.annotate(frame, inference)
            now = time.time()
            instant_fps = 1.0 / max(now - previous_frame_time, 1e-6)
            fps = instant_fps if fps == 0 else 0.9 * fps + 0.1 * instant_fps
            previous_frame_time = now
            site = SITES[site_index]

            draw_text(
                annotated,
                f"FPS {fps:.1f}   Confidence >= {confidence:.2f}",
                (20, 40),
                0.8,
                (0, 255, 0),
            )
            draw_text(
                annotated,
                f"Detections: {inference.total_detections}",
                (20, 80),
            )
            draw_text(
                annotated,
                f"Lunar: {inference.lunar_pct:.0f}%   Mars: {inference.mars_pct:.0f}%",
                (20, 120),
                0.9,
                (0, 255, 255),
            )
            draw_text(annotated, f"Site: {site[0]}", (20, 160), 0.7)
            draw_text(
                annotated,
                "[s] save  [n] site  [+/-] confidence  [q] quit",
                (20, settings.frame_height - 20),
                0.6,
            )
            if now < flash_until:
                draw_text(annotated, flash_message, (20, 205), 0.8, (0, 200, 255))

            cv2.imshow(window, annotated)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("s"):
                if inference.total_detections == 0:
                    flash_message = "No rocks detected; sample was not saved"
                else:
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    settings.samples_dir.mkdir(parents=True, exist_ok=True)
                    image_path = settings.samples_dir / f"{timestamp}.jpg"
                    if not cv2.imwrite(str(image_path), annotated):
                        raise OSError(f"Could not save sample image: {image_path}")
                    record = store.add_observation(
                        inference,
                        source="desktop",
                        site=site[0],
                        latitude=site[1],
                        longitude=site[2],
                    )
                    flash_message = (
                        f"Saved {Path(image_path).name} "
                        f"(observation {record['observation_id']})"
                    )
                    print(f"[INFO] {image_path}")
                flash_until = now + 2.0
            elif key == ord("n"):
                site_index = (site_index + 1) % len(SITES)
            elif key in (ord("+"), ord("=")):
                confidence = min(0.95, confidence + 0.05)
            elif key in (ord("-"), ord("_")):
                confidence = max(0.05, confidence - 0.05)
    finally:
        capture.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
