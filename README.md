# Federated Healthcare — Phase 1

A working academic Django prototype for **Federated Machine Learning for Chronic Disease Prediction**.

## Phase-1 workflow

### Patient
- Proper username/password authentication.
- Patient self-registration.
- Patient dashboard with the latest human-readable prediction.
- Previous Records table with date/time and View More details.
- New Prediction form with backend validation and human-friendly fields.
- Patient UI never exposes `N`, `HY`, `DI`, `DI_HY`, tree counts, or model accuracy.
- New predictions use the model that the Admin has marked **ACTIVE**.

### Hospitals
Three predefined hospital clients:

| Hospital | Username | Password |
|---|---|---|
| Hospital 1 | `hospital1` | `hospital123` |
| Hospital 2 | `hospital2` | `hospital123` |
| Hospital 3 | `hospital3` | `hospital123` |

Each hospital can:
1. Upload a CSV.
2. Validate the schema.
3. Split its data into **80% training / 10% validation / 10% testing**.
4. Train a **60-tree local Random Forest**.
5. View row counts, disease-class distribution and local test accuracy.
6. Submit the local model update to the current federated round.
7. View its own submission history and details.

### Admin
- Admin authentication.
- Latest global model and creation time.
- Pending hospital submissions.
- A global-model creation screen where the Admin selects **exactly one submission from Hospital 1, Hospital 2 and Hospital 3**.
- Backend rejects invalid selections, so duplicate submissions from one hospital cannot become extra clients.
- Selected 60-tree hospital forests are combined into a **180-tree global Random Forest artifact**.
- Every generated model is stored as a version (`v2.0.0`, `v3.0.0`, ...); earlier versions remain in history.
- Admin can select any available global version as the **ACTIVE Patient Portal model**.
- Patient inference automatically follows that active registry entry.

## Important implementation note
This is a **simulated federated Random Forest workflow** for the academic project. Raw uploaded hospital rows are used by the Django service to train each local model in this Phase-1 web demo; the aggregation function receives model artifacts/tree estimators rather than raw hospital rows. It is not cryptographic secure aggregation or differential privacy.

The Random Forest aggregation is tree-level ensemble combination. It does not claim that a standard sklearn RandomForest can be initialized from an arbitrary previous global forest in the same way as a weight-based neural model.

## Bundled benchmark

The repository contains:
- `data/Synthetic_Chronic_Disease_4Class_90_93pct.csv`
- `ml_models/chronic_disease_rf.joblib`

The bundled model is the initial **v1.0.0** active model. It has 180 trees and the previously verified benchmark accuracy of 92.68% on the project's synthetic test split. The application does not hard-code 92.68% into dashboards; model metrics shown for new hospital submissions come from actual training/evaluation results.

## Local setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py collectstatic --noinput
python manage.py runserver
```

Open `http://127.0.0.1:8000/`.

Admin: `admin / admin123`

## Database
SQLite is the default for local development. PostgreSQL is supported through `DATABASE_URL`.

The important persistent records are:
- Django users/profiles
- Patient predictions
- Hospital submissions
- Federated rounds
- Global model versions and their active/available status

## Model registry behavior
The Patient Portal does not guess which file to load. `GlobalModel(status='ACTIVE')` is the source of truth. The ML service loads that artifact and caches it until the artifact changes.

Runtime global artifacts are written under `media/`. For production, durable object storage/model registry should be used because many cloud service filesystems are ephemeral.
