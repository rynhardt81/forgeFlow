---
name: build
description: Production build and containerization guidance. Detects the project's stack and points at the right build path — native platform tooling first (Expo/EAS, Vercel, plain bundlers), a Dockerfile only when the deployment target actually needs one. Trigger phrases — production build, containerize, dockerize, build for deploy. NOT FOR CI mirroring (use /preflight-ci) or releasing versions (use /release).
---

# Build

Modern models write correct Dockerfiles, compose files, and CI build steps directly — this skill is deliberately a rules-and-routing card, not a wizard.

## Step 1: Detect the stack and route

| Detected | Build path |
|----------|-----------|
| Expo / React Native (`app.json` + expo dep) | `eas build` — do NOT hand-roll Docker for a store app |
| Next.js / Vercel project (`vercel.json`, `.vercel/`) | `vercel build` / platform deploy — containerize only for self-hosting |
| Supabase edge functions (`supabase/functions/`) | `supabase functions deploy` path |
| Plain Node/Bun service | Dockerfile (multi-stage) when deploying to a container target; otherwise the platform's build command |
| Python service | Dockerfile (multi-stage, uv/pip lockfile respected) |

Confirm the deployment target with the user before generating anything — a Dockerfile nobody deploys is dead weight in the repo.

## Step 2: Generate, then verify

Generate the minimal build setup for the confirmed target, then **verify by running it**: the build command must exit 0 and produce the artifact (image builds, `docker run` responds, bundle exists) before the work is called done. "The Dockerfile looks correct" is forbidden language.

## Key Rules

- Never generate secrets or credentials in build files
- Always use multi-stage builds for compiled languages
- Pin base image versions (never use `latest`)
- Generate `.dockerignore` with every Dockerfile
- Offer multi-arch only when beneficial (K8s, cloud)
- Preserve existing configurations when updating
- Document all environment variables
