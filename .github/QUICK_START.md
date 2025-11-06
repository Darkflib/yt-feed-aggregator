# GitHub CI/CD Quick Start

This is a quick reference for the most common CI/CD operations.

## First Time Setup

### 1. Enable GitHub Actions
```
Settings → Actions → General
✓ Allow all actions and reusable workflows
✓ Read and write permissions
✓ Allow GitHub Actions to create and approve pull requests
```

### 2. Make Container Images Public (Optional)
```
After first build:
Profile → Packages → yt-feed-aggregator
→ Package settings → Change visibility → Public
```

### 3. Enable Branch Protection
```
Settings → Branches → Add rule
Branch: main
✓ Require pull request before merging
✓ Require status checks to pass
```

## Common Commands

### Create a Release
```bash
# 1. Update version
vim pyproject.toml  # Update version = "1.0.0"
vim CHANGELOG.md    # Add release notes

# 2. Commit and tag
git add -A
git commit -m "chore: release v1.0.0"
git tag v1.0.0
git push origin main --tags

# Release workflow runs automatically
```

### Deploy Container
```bash
# Pull and run latest
podman pull ghcr.io/darkflib/yt-feed-aggregator:latest
podman run -d --name yt-aggregator \
  -p 8080:8080 \
  --env-file .env \
  ghcr.io/darkflib/yt-feed-aggregator:latest
```

### View Workflow Status
```
GitHub → Actions tab
or
gh run list --workflow=ci.yml
```

### Manual Workflow Trigger
```bash
# Via GitHub UI: Actions → CI/CD Pipeline → Run workflow
# Via CLI:
gh workflow run ci.yml
```

## Troubleshooting

### Workflow Fails
1. Check logs: Actions → Failed workflow → Job
2. Common issues:
   - Linting errors: Run `ruff check app/` locally
   - Test failures: Run `pytest` locally
   - Build errors: Check Containerfile syntax

### Container Push Fails
1. Settings → Actions → General
2. Verify "Read and write permissions" enabled
3. Re-run workflow

### Dependabot PRs Not Appearing
1. Insights → Dependency graph → Dependabot
2. Click "Check for updates"
3. View logs for errors

## Quick Links

- [Full Setup Guide](../SETUP_CICD.md)
- [CI/CD Documentation](../CI.md)
- [Deployment Guide](../ops/README.md)
- [Actions Tab](../../actions)
- [Packages](../../packages)

## Emergency Rollback

```bash
# Find previous working image
podman images ghcr.io/darkflib/yt-feed-aggregator

# Run specific version
podman run -d --name yt-aggregator \
  -p 8080:8080 \
  --env-file .env \
  ghcr.io/darkflib/yt-feed-aggregator:v0.9.0
```

## Support

Issues? Check the docs:
1. [SETUP_CICD.md](../SETUP_CICD.md) - Initial setup
2. [CI.md](../CI.md) - Workflow details
3. [ops/README.md](../ops/README.md) - Deployment
