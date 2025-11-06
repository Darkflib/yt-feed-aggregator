# CI/CD Documentation

This document describes the Continuous Integration and Continuous Deployment (CI/CD) pipeline for the YouTube Feed Aggregator project.

## Overview

The project uses GitHub Actions for automated testing, building, and deployment. The pipeline is designed to:

- Ensure code quality through linting and type checking
- Run comprehensive tests before merging
- Build and publish container images automatically
- Create versioned releases with proper tagging
- Maintain dependencies with automated updates
- Scan for security vulnerabilities

## Workflows

### 1. CI/CD Pipeline (`.github/workflows/ci.yml`)

**Triggers:**
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop`
- Manual workflow dispatch

**Jobs:**

#### Backend Linting (`lint-backend`)
- Runs `ruff check` for code quality
- Runs `ruff format --check` for formatting
- Runs `mypy` for type checking (continues on error)
- Uses Python 3.13

#### Frontend Linting (`lint-frontend`)
- Runs ESLint on TypeScript/React code
- Runs TypeScript compiler in check mode
- Uses Node.js 20

#### Backend Tests (`test-backend`)
- Matrix testing against Python 3.12 and 3.13
- Runs pytest with coverage reporting
- Uses Redis and PostgreSQL service containers
- Uploads coverage to Codecov (Python 3.13 only)

#### Frontend Build (`build-frontend`)
- Validates frontend builds successfully
- Caches node_modules for faster builds
- Uploads build artifacts for inspection

#### Security Scan (`security-scan`)
- Runs CodeQL analysis for Python and JavaScript
- Uses security-extended queries
- Uploads results to GitHub Security tab

#### Build Container (`build-container`)
- Only runs on `main` branch or version tags
- Builds multi-platform images (amd64, arm64)
- Pushes to GitHub Container Registry (GHCR)
- Generates SBOM (Software Bill of Materials)
- Scans image for vulnerabilities with Trivy
- Uses BuildKit cache for faster builds

**Container Tags Generated:**
- `sha-<commit>` - Unique SHA-based tag
- `main` - Latest from main branch
- `latest` - Alias for main
- `v*.*.*` - Semantic version tags
- `*.* ` - Major.minor tags
- `*` - Major version tags

### 2. Release Workflow (`.github/workflows/release.yml`)

**Triggers:**
- Push of version tags matching `v[0-9]+.[0-9]+.[0-9]+`
- Manual workflow dispatch with version input

**Jobs:**

#### Validate (`validate`)
- Validates tag format (must be `v*.*.*`)
- Extracts version information

#### Build and Test (`build-and-test`)
- Runs full test suite
- Builds frontend
- Ensures release quality before publishing

#### Build Release Container (`build-release-container`)
- Builds multi-platform container images
- Tags with multiple version formats:
  - `v1.2.3` - Full version with `v` prefix
  - `1.2.3` - Full version number
  - `1.2` - Major.minor
  - `1` - Major version only
  - `latest` - Latest release
- Generates SBOM for the release
- Creates GitHub Release with:
  - Changelog extracted from CHANGELOG.md or git history
  - SBOM artifact attached
  - Auto-generated release notes

### 3. Dependency Updates (`.github/dependabot.yml`)

Dependabot is configured to automatically create pull requests for dependency updates:

#### Python Dependencies
- Checks weekly (Mondays at 09:00)
- Groups production and development dependencies separately
- Monitors `pyproject.toml` and related files

#### npm Dependencies (Frontend)
- Checks weekly (Mondays at 09:00)
- Groups updates by ecosystem:
  - React ecosystem (`react*`, `@types/react*`)
  - Build tools (`vite`, `typescript`)
  - Linting tools (`eslint*`, `@typescript-eslint/*`)
  - Other production/development dependencies

#### GitHub Actions
- Checks weekly (Mondays at 09:00)
- Groups all action updates together

#### Docker Base Images
- Checks weekly (Mondays at 09:00)
- Monitors `Containerfile` for base image updates

All Dependabot PRs:
- Auto-assign to `darkflib` for review
- Include appropriate labels (dependencies, language/ecosystem)
- Use conventional commit messages (`chore(deps):`)

## Environment Variables and Secrets

### Required Secrets

#### Automatic (GitHub-provided)
- `GITHUB_TOKEN` - Automatically provided for GHCR push and releases

#### Optional (for full functionality)
- `CODECOV_TOKEN` - For coverage reporting (optional, continues on error)

### Environment Variables Used in Tests

Test jobs use the following environment variables (provided in workflow):

```yaml
YT_APP_SECRET_KEY: test-secret-key-for-ci
YT_TOKEN_ENC_KEY: test-token-enc-key-12345678901234567890123456789012
YT_GOOGLE_CLIENT_ID: test-client-id
YT_GOOGLE_CLIENT_SECRET: test-client-secret
YT_GOOGLE_REDIRECT_URI: http://localhost:8080/auth/callback
YT_DATABASE_URL: sqlite+aiosqlite:///:memory:
YT_REDIS_URL: redis://localhost:6379/0
YT_ENV: dev
```

## Container Registry

Images are published to GitHub Container Registry (GHCR):

**Registry:** `ghcr.io`
**Repository:** `ghcr.io/darkflib/yt-feed-aggregator`

### Authentication

The workflows use the automatic `GITHUB_TOKEN` to authenticate with GHCR. No additional secrets are needed.

### Pulling Images

```bash
# Pull latest from main
podman pull ghcr.io/darkflib/yt-feed-aggregator:latest

# Pull specific version
podman pull ghcr.io/darkflib/yt-feed-aggregator:v1.0.0

# Pull by commit SHA (useful for debugging)
podman pull ghcr.io/darkflib/yt-feed-aggregator:main-abc1234
```

### Making Images Public

By default, GHCR packages are private. To make them public:

1. Go to the package page: https://github.com/users/darkflib/packages/container/yt-feed-aggregator
2. Click "Package settings"
3. Scroll to "Danger Zone"
4. Click "Change visibility"
5. Select "Public"

## Caching Strategy

The pipeline uses several caching mechanisms for faster builds:

1. **Python pip cache** - Caches pip packages between runs
2. **npm cache** - Caches node_modules for frontend builds
3. **Docker layer cache** - Uses GitHub Actions cache for Docker layers
4. **BuildKit cache** - Reuses layers across builds

## Security Features

### 1. Static Application Security Testing (SAST)

**CodeQL Analysis:**
- Scans Python and JavaScript code
- Uses security-extended query suite
- Results appear in GitHub Security tab
- Runs on every push and PR

### 2. Container Vulnerability Scanning

**Trivy Scanner:**
- Scans built container images
- Checks for known vulnerabilities in dependencies
- Results uploaded to GitHub Security (SARIF format)
- Continues on error to not block deployments

### 3. Software Bill of Materials (SBOM)

**SBOM Generation:**
- Generates SPDX-format SBOM for each release
- Attached to GitHub Releases
- Helps track dependencies and licenses
- Useful for compliance and security audits

### 4. Dependency Security

**Dependabot:**
- Monitors for security vulnerabilities in dependencies
- Creates PRs for security updates with priority
- Includes severity information in PR descriptions

## Release Process

### Creating a New Release

1. **Update Version** (optional):
   - Update `pyproject.toml` version field
   - Update `frontend/package.json` version field
   - Update CHANGELOG.md with changes

2. **Create and Push Tag**:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

3. **Automatic Actions**:
   - Release workflow triggers automatically
   - Tests run to validate the release
   - Multi-platform container images are built
   - Images are tagged with version numbers
   - GitHub Release is created with:
     - Changelog
     - SBOM artifact
     - Links to container images

4. **Manual Trigger** (alternative):
   - Go to Actions → Release workflow
   - Click "Run workflow"
   - Enter version tag (e.g., `v1.0.0`)

### Version Naming Convention

Follow semantic versioning (SemVer):

- `v1.0.0` - Major release (breaking changes)
- `v1.1.0` - Minor release (new features, backwards compatible)
- `v1.1.1` - Patch release (bug fixes)

## Deployment

### Automatic Deployment (Recommended)

For automatic deployment to your Podman host, create a systemd timer or cron job:

```bash
#!/usr/bin/env bash
# /usr/local/bin/yt-aggregator-update.sh

IMAGE="ghcr.io/darkflib/yt-feed-aggregator:latest"

# Pull latest image
podman pull "$IMAGE"

# Get new and current digests
NEW_DIGEST=$(podman inspect "$IMAGE" --format '{{.Digest}}')
CUR_DIGEST=$(podman inspect yt-aggregator --format '{{.ImageDigest}}' 2>/dev/null || echo "")

# Restart if different
if [ "$NEW_DIGEST" != "$CUR_DIGEST" ]; then
  echo "New image detected ($NEW_DIGEST), restarting..."

  podman stop yt-aggregator || true
  podman rm yt-aggregator || true

  podman run -d \
    --name yt-aggregator \
    -p 8080:8080 \
    --env-file /srv/yt-aggregator/.env \
    --restart always \
    "$IMAGE"

  echo "Deployment complete"
else
  echo "No changes detected"
fi
```

**Systemd Timer Example** (`/etc/systemd/system/yt-aggregator-update.timer`):

```ini
[Unit]
Description=Check for YouTube Aggregator updates
Requires=yt-aggregator-update.service

[Timer]
OnCalendar=*:0/15  # Every 15 minutes
Persistent=true

[Install]
WantedBy=timers.target
```

**Systemd Service** (`/etc/systemd/system/yt-aggregator-update.service`):

```ini
[Unit]
Description=Update YouTube Aggregator container
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/yt-aggregator-update.sh
User=root

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
systemctl daemon-reload
systemctl enable yt-aggregator-update.timer
systemctl start yt-aggregator-update.timer
```

### Manual Deployment

```bash
# Pull latest
podman pull ghcr.io/darkflib/yt-feed-aggregator:latest

# Stop and remove old container
podman stop yt-aggregator
podman rm yt-aggregator

# Run new container
podman run -d \
  --name yt-aggregator \
  -p 8080:8080 \
  --env-file .env \
  --restart always \
  ghcr.io/darkflib/yt-feed-aggregator:latest
```

## Monitoring CI/CD

### GitHub Actions UI

- View workflow runs: https://github.com/darkflib/yt-feed-aggregator/actions
- Check workflow status badges in README.md
- Review failed jobs and logs

### Notifications

Configure GitHub notifications for:
- Failed workflow runs
- Security alerts from Dependabot
- Code scanning alerts from CodeQL

Settings → Notifications → Actions

### Logs and Artifacts

- Build logs are retained for 90 days
- Artifacts (SBOM, frontend builds) are retained for 7-30 days
- Container images are retained indefinitely in GHCR

## Troubleshooting

### Build Failures

**Linting Errors:**
- Run `ruff check app/` locally before pushing
- Run `ruff format app/` to auto-fix formatting
- Run `npm run lint -- --fix` for frontend

**Test Failures:**
- Check if Redis/PostgreSQL services are healthy
- Verify environment variables are set correctly
- Run tests locally: `pytest -v`

**Container Build Failures:**
- Ensure Containerfile syntax is correct
- Check if all COPY sources exist
- Verify multi-platform build support

### GHCR Permission Errors

If you see permission errors pushing to GHCR:

1. Check repository settings → Actions → Workflow permissions
2. Ensure "Read and write permissions" is enabled
3. Verify package visibility settings

### Dependabot Issues

**PRs Not Created:**
- Check dependabot.yml syntax
- Verify repository has dependencies to update
- Check Dependabot logs in Insights → Dependency graph → Dependabot

**Too Many PRs:**
- Adjust `open-pull-requests-limit` in dependabot.yml
- Use grouping to consolidate updates

## Performance Optimization

### Reducing Build Times

1. **Use caching effectively:**
   - pip cache for Python dependencies
   - npm cache for node_modules
   - Docker layer cache for container builds

2. **Parallel job execution:**
   - Lint and test jobs run in parallel
   - Frontend and backend jobs are independent

3. **Selective job execution:**
   - Container builds only on main/tags
   - Security scans can be limited to important branches

4. **Matrix strategy:**
   - Test against multiple Python versions in parallel
   - Can be extended to test different OS/configurations

### Cost Optimization

GitHub Actions minutes are free for public repositories. For private repositories:

- Optimize workflow triggers
- Use self-hosted runners for frequent builds
- Cache aggressively to reduce redundant work
- Use `if` conditions to skip unnecessary jobs

## Best Practices

1. **Always run tests before merge:**
   - Use branch protection rules
   - Require status checks to pass
   - Enforce code review

2. **Keep dependencies updated:**
   - Review Dependabot PRs weekly
   - Test updates in development first
   - Use grouped updates for easier review

3. **Version everything:**
   - Use semantic versioning for releases
   - Tag container images with multiple versions
   - Keep CHANGELOG.md updated

4. **Monitor security:**
   - Review CodeQL alerts promptly
   - Act on Dependabot security updates quickly
   - Check Trivy scan results regularly

5. **Document changes:**
   - Update CHANGELOG.md for each release
   - Include migration guides for breaking changes
   - Keep CI.md documentation current

## Future Enhancements

Potential improvements to the CI/CD pipeline:

- [ ] Add frontend unit tests (Vitest)
- [ ] Add E2E tests (Playwright)
- [ ] Performance testing for API endpoints
- [ ] Automated rollback on deployment failures
- [ ] Staging environment deployments
- [ ] Blue/green deployment strategy
- [ ] Canary releases
- [ ] Integration with monitoring tools (Sentry, etc.)
- [ ] Automated security scanning with additional tools
- [ ] Container image signing with cosign
- [ ] Attestation generation for supply chain security

## Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [GitHub Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Dependabot Configuration](https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file)
- [CodeQL](https://codeql.github.com/)
- [Trivy Scanner](https://github.com/aquasecurity/trivy)
- [Semantic Versioning](https://semver.org/)
- [Conventional Commits](https://www.conventionalcommits.org/)
