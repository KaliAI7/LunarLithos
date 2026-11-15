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
4. Start the Python detection API in one terminal with `python web.py` from
   the project directory and activated environment.
5. In a second terminal, start the Express website with `npm install` and
   `npm start`. The website is available at `http://localhost:3000`.

The bundled `model.pt` is used when `MODEL_PATH` is not set. The Python API is
available at `http://localhost:8080`; interactive API documentation is at
`http://localhost:8080/docs`. Express serves the existing `website-app` and
proxies its `/api` requests to the Python API. Configure the Express proxy in
`.env` with `API_HOST` and `API_PORT` (defaults: `127.0.0.1` and `8080`).
`API_HOST` must be an address reachable from the Express server. If the Python
API runs on another machine, set it to that machine's LAN IP and make sure
the Python API binds to a reachable interface. Set `WEB_PORT` to change the
website port; `PORT` remains the Python API port. `API_PROTOCOL` can be set to
`https` when the API uses TLS.

On the website, click a point on the world map, enter a site name, and choose
an image. The image is analyzed by the YOLO API; the site name and selected
coordinates are saved with the observation and shown as a labeled map marker.
Map coordinates are selected from the displayed equirectangular Earth map.
The `DEVICE` setting in `.env` is respected (`DEVICE=0` selects the configured
GPU).

Open `/view/` on the Express website to see saved class totals and each
observation's location on the rotating Earth globe. The view refreshes saved
data automatically. The material panel shows counts for every model class;
the globe labels each saved, located observation with its site name and total
detections. NASA-referenced analog sites are shown as a separate reference
layer and do not affect observation counts or mineral totals.

To import the 30 reference sites on Jetson, run this from the project directory
with the project's Python environment activated:

```bash
python scripts/seed_nasa_analog_sites.py
```

The import is safe to repeat and writes to the database selected by
`DATABASE_PATH` in `.env`. The website API must be restarted if it was already
running when the code was updated. The site descriptions link to official NASA
sources, including NASA's [planetary analog overview](https://science.nasa.gov/solar-system/planetary-analogs/),
[NASA Artemis field training in Iceland](https://science.nasa.gov/missions/artemis/nasas-artemis-ii-crew-uses-iceland-terrain-for-lunar-training/),
[NASA's Arizona lunar simulation](https://science.nasa.gov/missions/artemis/behind-the-scenes-of-a-nasa-moonwalk-in-the-arizona-desert/),
and [NASA's overview of planetary analogs](https://science.nasa.gov/solar-system/planetary-analogs/10-things-to-know-about-planetary-analogs/).
NASA describes some named training regions and terrain classes, but does not
publish surveyed coordinates for 30 sites. The map pins are representative
coordinates for the named features; they are not exact NASA survey points, and
the list does not imply that NASA officially designated every example as an
analog site.

Open `/camera/` for the live YOLO camera station. It displays the annotated
camera feed, per-class counts from the latest frame, and controls for saving a
sample, changing the field site, and adjusting confidence. The station marks
five or more detections as "Potentially viable" using a screening heuristic;
this is not a scientific assessment of habitability or resources.

To test the API from a browser, open `http://localhost:3000/api_test.html`
while the Express website and Python API are running. The image upload
endpoint stores an observation; the other checks are read-only.

Set `CAMERA_ENABLED=false` in `.env` to run the image API without opening a
camera. The camera viewer is available at the Python API root, with its MJPEG
stream at `/api/video`.

## API

- `GET /api/health`: model and camera status.
- `GET /api/classes`: model class names and configured categories.
- `POST /api/detect`: upload an image as multipart form field `file`. Optional
  fields: `site`, `latitude`, and `longitude`. Returns individual detections,
  bounding boxes, confidence scores, and counts for every model class.
- `GET /api/observations`: list saved detections. Optional filters: `site`,
  `class_name`, `since`, `until`, `limit`, and `offset`.
- `GET /api/analog-sites`: list the separately stored planetary-analog
  reference sites. Import/update them locally with
  `python scripts/seed_nasa_analog_sites.py`.
- `DELETE /api/observations/{observation_id}`: delete one saved observation
  and its class counts. The website confirms before deleting and then refreshes
  location markers and aggregate counts.
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
