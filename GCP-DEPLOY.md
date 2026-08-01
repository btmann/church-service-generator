# GCP Deployment Starter (Cheapest Path)

For a full click-by-click setup (GCP UI, domain purchase/mapping, and optional DB), see [GCP-PROJECT-SETUP-GUIDE.md](GCP-PROJECT-SETUP-GUIDE.md).
For the exact Namecheap setup of `church-slide-creater-eh.org`, jump to section "10A" in [GCP-PROJECT-SETUP-GUIDE.md](GCP-PROJECT-SETUP-GUIDE.md).

This project now includes:
- Docker image build file: Dockerfile
- Cloud Build config: cloudbuild.yaml
- Direct in-browser downloads for generated PPTX/JSON in the Streamlit UI

## 1) One-time GCP setup

Set your project:

```bash
gcloud config set project YOUR_PROJECT_ID
```

Enable APIs:

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

Create an Artifact Registry repo:

```bash
gcloud artifacts repositories create church-service \
  --repository-format=docker \
  --location=us-central1
```

## 2) Build and push image

Option A: Cloud Build (recommended)

```bash
gcloud builds submit --config cloudbuild.yaml \
  --substitutions _IMAGE_URI=us-central1-docker.pkg.dev/YOUR_PROJECT_ID/church-service/church-service-ui:latest
```

Option B: Windows PC local Docker build + push (PowerShell)

Prerequisites:
- Docker Desktop installed and running
- Google Cloud CLI installed
- You are signed in to gcloud (`gcloud auth login`)

PowerShell commands:

```powershell
$PROJECT_ID="YOUR_PROJECT_ID"
$REGION="us-central1"
$REPO="church-service"
$IMAGE="church-service-ui"
$TAG="latest"
$IMAGE_URI="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/$IMAGE`:$TAG"

gcloud config set project $PROJECT_ID
gcloud auth configure-docker "$REGION-docker.pkg.dev"

docker build -t $IMAGE_URI .
docker push $IMAGE_URI
```

Quick verify that image exists:

```powershell
gcloud artifacts docker images list "$REGION-docker.pkg.dev/$PROJECT_ID/$REPO"
```

## 3) Deploy to Cloud Run (low-cost defaults)

```bash
gcloud run deploy church-service-ui \
  --image us-central1-docker.pkg.dev/YOUR_PROJECT_ID/church-service/church-service-ui:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --min-instances 0 \
  --max-instances 2 \
  --cpu 1 \
  --memory 2Gi \
  --concurrency 1 \
  --timeout 900
```

Notes:
- min-instances=0 keeps idle cost near zero.
- concurrency=1 is safer for heavy PPTX generation jobs.
- Increase max-instances later if Sunday traffic grows.

## 4) Streamlit Cloud Run Compatibility (Required)

The project includes a `.streamlit/config.toml` file that fixes known compatibility issues between Streamlit and Cloud Run:
- Disables CORS and XSRF protection (safe behind Cloud Run's authentication layer).
- **Disables websocket compression** — Cloud Run's HTTP/2 layer can double-compress frames, corrupting Streamlit's dynamic JS imports.
- Disables usage stats gathering.

These settings are also encoded as Docker environment variables in the `Dockerfile` as a fallback if config parsing fails.

**No additional GCP configuration is needed** — the Docker image automatically includes these fixes. If you see `TypeError: error loading dynamically imported module` errors in the browser console, verify that:
1. The `.streamlit/config.toml` file exists in the repo root.
2. The Dockerfile contains the `STREAMLIT_SERVER_ENABLE_WEBSOCKET_COMPRESSION=false` environment variable.
3. Your Cloud Run service has been redeployed after these files were committed.

## 5) Use the web app

When a service is generated, users can click:
- Download Service JSON
- Download PowerPoint

No manual file browsing is required.

Users can also access the **Song Processing** page (sidebar navigation) to add new songs or Spanish translations to the library.

## 6) Next cost-saving improvements

1. Add Cloud Storage uploads and signed links (avoid local-only files).
2. Add lifecycle auto-delete (for example 7-14 days) to control storage costs.
3. Add optional PDF conversion endpoint (only on demand).
