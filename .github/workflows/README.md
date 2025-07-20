# GitHub Actions Setup

This workflow automatically builds and pushes Docker images to Docker Hub when you push to the main branch or create releases.

## Required Secrets

You need to set up the following secrets in your GitHub repository:

1. Go to your repository settings
2. Navigate to "Secrets and variables" → "Actions"
3. Add the following secrets:

### DOCKER_HUB_USERNAME
Your Docker Hub username (e.g., `nickborgers`)

### DOCKER_HUB_PAT
Your Docker Hub Personal Access Token:
1. Go to https://hub.docker.com/settings/security
2. Click "New Access Token"
3. Give it a name (e.g., "GitHub Actions")
4. Copy the token and save it as `DOCKER_HUB_PAT`

## Workflow Behavior

- **Push to main branch**: Builds and pushes with tag `main-<sha>`
- **Pull Request**: Builds but doesn't push (for testing)
- **Release tags (v*)** : Builds and pushes with semantic version tags

## Image Tags

The workflow creates multiple tags:
- `nickborgers/notion-home-task-manager:main-<sha>` (for main branch pushes)
- `nickborgers/notion-home-task-manager:v1.0.0` (for releases)
- `nickborgers/notion-home-task-manager:1.0` (for releases)
- `nickborgers/notion-home-task-manager:latest` (for main branch)

## Multi-platform Support

The workflow builds for both:
- `linux/amd64` (Intel/AMD processors)
- `linux/arm64` (Apple Silicon, ARM servers) 