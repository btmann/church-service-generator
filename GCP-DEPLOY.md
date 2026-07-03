# GCP Deployment Starter (Cheapest Path)

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

## 4) Use the web app

When a service is generated, users can click:
- Download Service JSON
- Download PowerPoint

No manual file browsing is required.

## 5) Next cost-saving improvements

1. Add Cloud Storage uploads and signed links (avoid local-only files).
2. Add lifecycle auto-delete (for example 7-14 days) to control storage costs.
3. Add optional PDF conversion endpoint (only on demand).
