# GCP Project Setup Guide (UI + Domain + DB)

This guide walks through everything end-to-end:
- GCP Console setup (what to click)
- Deploying this app on Cloud Run
- Buying and connecting a domain
- Setting up a database (optional, only if needed)

This is written for the current project and the lowest-cost path.

## 0. Recommended Architecture for This App

Use this first:
1. Cloud Run for the web app
2. Cloud Storage for generated files (PPTX/PDF/JSON)
3. Secret Manager for secrets
4. No DB initially (cheapest and simplest)

Add Cloud SQL later only if you need persistent app data like users, job history, templates, audit logs, etc.

## 1. Create GCP Project in Console (UI)

1. Open Google Cloud Console.
2. Top bar project picker > New Project.
3. Name it something like `church-service-prod`.
4. Select billing account.
5. Click Create.

### Attach Billing

1. Left menu > Billing.
2. Link billing account to your new project.
3. Confirm billing is active.

### Set Budget Alerts (important)

1. Billing > Budgets & alerts > Create budget.
2. Scope: this project.
3. Budget amount (example: $20/month for early phase).
4. Alert thresholds: 50%, 80%, 100%.
5. Save.

## 2. Enable Required APIs (UI)

1. Left menu > APIs & Services > Library.
2. Enable these APIs:
- Cloud Run Admin API
- Cloud Build API
- Artifact Registry API
- Secret Manager API
- Cloud Storage API
- Cloud Logging API

If adding DB later, also enable:
- Cloud SQL Admin API

## 3. Create Artifact Registry Repo (UI)

1. Left menu > Artifact Registry.
2. Click Create Repository.
3. Name: `church-service`.
4. Format: Docker.
5. Region: `us-central1` (or your preferred single region).
6. Click Create.

## 4. Create Storage Bucket (UI)

1. Left menu > Cloud Storage > Buckets > Create.
2. Name: globally unique, e.g. `church-service-prod-files-<random>`.
3. Location type: Region.
4. Region: same as Cloud Run (for lower latency and egress).
5. Default storage class: Standard.
6. Access control: Uniform.
7. Create.

### Add lifecycle rule to control cost

1. Open bucket > Lifecycle > Add rule.
2. Condition: Age > 14 days (or 7 days).
3. Action: Delete object.
4. Save.

## 5. Create Service Accounts + IAM (UI)

### Runtime service account for Cloud Run

1. IAM & Admin > Service Accounts > Create Service Account.
2. Name: `church-service-runner`.
3. Grant roles:
- Storage Object Admin (or narrower custom role)
- Secret Manager Secret Accessor (if using secrets)
- Logs Writer
4. Create.

### Build service account permissions

Cloud Build default SA usually works, but ensure it can:
- push to Artifact Registry
- deploy to Cloud Run

Roles typically needed:
- Cloud Run Admin
- Service Account User
- Artifact Registry Writer

## 6. Add Secrets (UI)

1. Security > Secret Manager > Create Secret.
2. Add secrets like API keys/tokens used by the app.
3. Use environment variables in Cloud Run to reference secrets.

Do not hardcode secrets in source files.

## 7. Build and Push Container

Use the files already in this repo:
- [Dockerfile](Dockerfile)
- [cloudbuild.yaml](cloudbuild.yaml)

From your local machine:

```bash
gcloud config set project YOUR_PROJECT_ID
gcloud builds submit --config cloudbuild.yaml \
  --substitutions _IMAGE_URI=us-central1-docker.pkg.dev/YOUR_PROJECT_ID/church-service/church-service-ui:latest
```

## 8. Deploy Cloud Run (Cheapest Baseline)

Console path:
1. Cloud Run > Create Service.
2. Deploy one revision from existing container image.
3. Image URL:
`us-central1-docker.pkg.dev/YOUR_PROJECT_ID/church-service/church-service-ui:latest`
4. Service name: `church-service-ui`.
5. Region: `us-central1`.
6. Authentication: allow unauthenticated (or require auth if internal only).
7. Container port: `8080`.

In service settings, set:
- CPU: 1
- Memory: 2 GiB (adjust after testing)
- Min instances: 0
- Max instances: 2 (start low)
- Concurrency: 1
- Request timeout: 900s
- Service account: `church-service-runner`

Click Deploy.

## 9. Buy a Domain

Buy from any registrar (Cloudflare, Squarespace Domains, Namecheap, etc.).

Tips:
- Prefer `.org` or your church’s existing domain.
- Buy for multiple years if this is long-term.
- Turn on registrar lock and 2FA.

## 10. Map Custom Domain to Cloud Run

### In GCP Console

1. Cloud Run > your service > Manage Custom Domains.
2. Add Mapping.
3. Enter domain/subdomain (example: `slides.yourchurch.org`).
4. Follow domain verification flow if prompted.
5. Cloud Run shows required DNS records.

### At your domain registrar DNS

1. Open DNS management.
2. Add the exact records provided by Cloud Run.
3. Save and wait for DNS propagation (minutes to 24h).

Cloud Run provisions TLS certificate automatically after DNS validates.

## 10A. Exact Domain Steps for church-slide-creater-eh.org (Namecheap)

Use this exact plan after your Cloud Run service is deployed.

### Recommended hostname

Use a subdomain for the app:
- `slides.church-slide-creater-eh.org`

Why:
- easiest DNS setup
- easiest TLS setup
- keeps root domain available for redirects/site later

### Part 1: Add domain mapping in GCP

1. Open Cloud Run.
2. Click service `church-service-ui`.
3. Open Manage Custom Domains.
4. Click Add Mapping.
5. Enter `slides.church-slide-creater-eh.org`.
6. Complete ownership verification if Google asks.
7. Keep this page open; it will show the DNS records you must add.

### Part 2: Add records in Namecheap

1. Sign in to Namecheap.
2. Domain List > Manage for `church-slide-creater-eh.org`.
3. Open Advanced DNS.
4. Add the exact records from Cloud Run mapping.

Common pattern (example only; always trust GCP values):
- Type: CNAME Record
- Host: `slides`
- Value/Target: the `ghs.googlehosted.com` value Cloud Run gives you
- TTL: Automatic

If verification TXT records are shown in Cloud Run, add those too:
- Type: TXT Record
- Host: usually `@` or `_acme-challenge` (exactly as shown)
- Value: exact token/value from Cloud Run
- TTL: Automatic

### Part 3: Validate activation

1. Return to Cloud Run domain mapping page.
2. Wait for status to move to Active/Ready.
3. Test in browser:
- `https://slides.church-slide-creater-eh.org`

Notes:
- DNS may propagate in minutes, but can take up to 24 hours.
- TLS certificate issuance starts after DNS records are correct.

### Optional root-domain redirect in Namecheap

If you want visitors at the root domain to go to your app:

1. In Namecheap Advanced DNS, add URL Redirect Record.
2. Host: `@`
3. Value: `https://slides.church-slide-creater-eh.org`
4. Redirect type: Permanent (301)

Also add a redirect for `www` if needed.

### Troubleshooting checklist

If mapping is stuck in pending:
1. Confirm each DNS record exactly matches Cloud Run page (no typos).
2. Remove conflicting CNAME/A records for host `slides`.
3. Keep TTL at Automatic.
4. Wait and recheck after 15-30 minutes.
5. Verify domain ownership in Search Console if prompted.

## 11. Database Setup (Optional)

For this app, DB is optional at first.

Use DB only if you need:
- Saved service plans by user
- User accounts/roles
- Job queue tracking/history
- Audit logs and reporting

### Cheapest DB choice on GCP

If DB is needed, start with Cloud SQL for PostgreSQL.

UI steps:
1. SQL > Create Instance > PostgreSQL.
2. Choose region same as Cloud Run.
3. Machine: smallest shared-core option available.
4. Storage: small SSD, auto-increase on.
5. High availability: off (for cost, at first).
6. Backups: on (daily).
7. Create instance.

Then:
1. Create database (example: `church_service`).
2. Create app user.
3. In Cloud Run, add Cloud SQL connection and env vars.
4. Store DB password in Secret Manager.

### Suggested minimal schema

- `services` (service metadata by date/time/template)
- `service_items` (ordered items for each service)
- `generation_jobs` (status, output links, timestamps)
- `users` (optional)

## 12. Production Hardening Checklist

1. Turn on Cloud Armor only if you need WAF controls.
2. Restrict IAM to least privilege.
3. Enable object lifecycle deletion in storage bucket.
4. Enable Error Reporting and alerting.
5. Keep min instances at 0 for low idle cost.
6. Review billing weekly in first month.

## 13. Monthly Cost Control Tips

1. Keep one Cloud Run service.
2. Keep min instances at 0.
3. Keep max instances low until traffic proves otherwise.
4. Delete old generated files automatically.
5. Do not add Cloud SQL until truly needed.

## 14. What You Already Have in This Repo

Deployment starter files are already present:
- [GCP-DEPLOY.md](GCP-DEPLOY.md)
- [Dockerfile](Dockerfile)
- [cloudbuild.yaml](cloudbuild.yaml)
- [.dockerignore](.dockerignore)

The UI now supports browser downloads for generated files, including PowerPoint.

## 15. Suggested Rollout Plan

1. Deploy to a test project/domain first.
2. Have 2-3 users test full workflow.
3. Confirm downloads and file generation speed.
4. Move to production project + domain.
5. Add DB only after real usage confirms need.
