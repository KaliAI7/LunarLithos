# LunarLithos Rock Detection API

The project detects rock types with a YOLO model, reports the number of
detections for each model class, and stores observations for later comparison
with manually collected reference data.

## Setup

1. On Jetson, create the project environment with Python 3.10:

   ```bash
   python3.10 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements-jetson.txt
   ```

   The Jetson lock matches the reported working environment versions,
   including PyTorch 2.14.1, CUDA toolkit 13.0.3.0, and Triton 3.8.0. The
   generic `requirements.txt` may resolve a newer PyTorch/CUDA combination.
2. Verify the environment with `python --version`, `python -m pip check`, and
   `python -m pip show torch torchvision`.
3. Copy `.env.example` to `.env` and set `MODEL_PATH` if needed.
4. Start both the website and API with `./run.sh`. By default the launcher
   uses this project's `.venv`; set `VENV_PATH` only if you explicitly want
   another environment.

The bundled `model.pt` is used when `MODEL_PATH` is not set. The API is
available at `http://localhost:8080`; interactive API documentation is at
`http://localhost:8080/docs`.
The website and API run together in the same server process; `run.sh` does not
force CPU or GPU, so the `DEVICE` setting in `.env` is respected (`DEVICE=0`
selects the configured GPU).

To test the API from a browser, serve `api_test.html` from an allowed local
origin such as `http://localhost:3000` with
`python3 -m http.server 3000`. Open `http://localhost:3000/api_test.html`.
The image upload endpoint stores an observation; the other checks are
read-only.

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

## Jetson GPU troubleshooting

The failing environment was Python 3.12 with PyTorch 2.15.0, CUDA toolkit
13.2.2, and Triton 3.9.0. The working environment was Python 3.10.22 with
PyTorch 2.14.1, CUDA toolkit 13.0.3.0, and Triton 3.8.0. Recreate this
project's `.venv` with Python 3.10 and install `requirements-jetson.txt` to
match the working stack. Do not use the generic requirements file for that
Jetson GPU environment.
