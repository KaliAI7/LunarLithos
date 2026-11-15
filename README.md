# LunarLithos Rock Detection API

The project detects rock types with a YOLO model, reports the number of
detections for each model class, and stores observations for later comparison
with manually collected reference data.

## Setup

1. Create a Python environment and install `requirements.txt`.
2. Copy `.env.example` to `.env`.
3. Set `MODEL_PATH` in `.env` to the model weights file.
4. Start the API with `python web.py`.

The bundled `model.pt` is used when `MODEL_PATH` is not set. The API is
available at `http://localhost:8080`; interactive API documentation is at
`http://localhost:8080/docs`.

Set `CAMERA_ENABLED=false` in `.env` to run the image API without opening a
camera. The camera viewer is available at `/`, with its MJPEG stream at
`/api/video`.

## API

- `GET /api/health`: model and camera status.
- `GET /api/classes`: model class names and configured categories.
- `POST /api/detect`: upload an image as multipart form field `file`. Optional
  fields: `site`, `latitude`, and `longitude`. Returns individual detections,
  bounding boxes, confidence scores, and counts for every model class.
- `GET /api/observations`: list saved detections. Optional filters: `site`,
  `class_name`, `since`, `until`, and `limit`.
- `GET /api/summary`: aggregate class counts across model observations. Optional
  filters: `site`, `since`, and `until`.
- `POST /api/reference-data`: add counts from an external dataset. The JSON
  body includes `dataset_name`, a `counts` object keyed by class name, and
  optional `site`, `observed_at`, coordinates, and notes.
- `GET /api/compare`: compare total model detections with registered reference
  counts by class. Optional filters: `site`, `dataset_name`, `since`, and
  `until`.
- `GET /api/latest`: latest live camera inference.

Reference data is not bundled with the project. Add a trusted dataset through
`POST /api/reference-data` before using `/api/compare`. The comparison is a
count comparison, not a scientific estimate of rock composition or model
accuracy; class names in both datasets must match.

Observations are stored in SQLite at `samples/observations.sqlite3` by
default. Upload inference records include counts and detections; camera samples
also save their annotated image under `samples/`.

## Configuration

Configuration is loaded from `.env`. See `.env.example` for available options,
including the model path, inference confidence, camera, storage paths, and
allowed browser origins. `LUNAR_CLASSES`, `MARS_CLASSES`, and `EARTH_CLASSES`
set class categories; all model classes are returned even when their count is
zero.

The confidence-weighted lunar and Mars percentages are detection scores, not
geological composition percentages.
