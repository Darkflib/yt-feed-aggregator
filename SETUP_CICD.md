# CI/CD Setup Guide

This guide walks you through setting up the CI/CD pipeline for the YouTube Feed Aggregator project on GitHub.

## Prerequisites

- GitHub repository created at `darkflib/yt-feed-aggregator`
- Git configured locally
- Access to repository settings

## Initial GitHub Setup

### 1. Enable GitHub Actions

GitHub Actions should be enabled by default, but verify:

1. Go to repository **Settings** → **Actions** → **General**
2. Under "Actions permissions", select **Allow all actions and reusable workflows**
3. Under "Workflow permissions", select **Read and write permissions**
4. Check **Allow GitHub Actions to create and approve pull requests**
5. Click **Save**

### 2. Enable GitHub Container Registry (GHCR)

GHCR is automatically available. To make your container images public:

1. After the first successful build, go to your profile
2. Navigate to **Packages** tab
3. Click on **yt-feed-aggregator** package
4. Go to **Package settings**
5. Scroll to **Danger Zone** → **Change visibility**
6. Select **Public** (recommended) or keep **Private**

### 3. Configure Branch Protection (Recommended)

Protect your main branch to ensure all tests pass before merging:

1. Go to **Settings** → **Branches**
2. Click **Add rule** under "Branch protection rules"
3. Branch name pattern: `main`
4. Enable:
   - ✅ Require a pull request before merging
   - ✅ Require status checks to pass before merging
     - Search and add: `Backend Linting`, `Frontend Linting`, `Backend Tests`, `Build Frontend`
   - ✅ Require branches to be up to date before merging
   - ✅ Do not allow bypassing the above settings
5. Click **Create** or **Save changes**

### 4. Enable Dependabot Alerts

1. Go to **Settings** → **Code security and analysis**
2. Enable:
   - ✅ Dependency graph (should be on by default)
   - ✅ Dependabot alerts
   - ✅ Dependabot security updates
3. Dependabot will now create PRs for security vulnerabilities

### 5. Enable Code Scanning

For CodeQL scanning:

1. Go to **Security** → **Code scanning**
2. Click **Set up code scanning**
3. The workflow already includes CodeQL, so this should activate automatically after first run
4. Review alerts in the **Security** tab

## Workflow Configuration

### Environment Variables

The workflows use these environment variables (no manual setup needed):

- `GITHUB_TOKEN` - Automatically provided by GitHub
- `GITHUB_ACTOR` - Your GitHub username
- `REGISTRY` - Set to `ghcr.io` in workflow
- `IMAGE_NAME` - Set to `darkflib/yt-feed-aggregator` in workflow

### Optional Secrets

Add these in **Settings** → **Secrets and variables** → **Actions** if needed:

#### Codecov (Optional)

For coverage reporting:

1. Sign up at [codecov.io](https://codecov.io) with your GitHub account
2. Add your repository
3. Copy the upload token
4. Add to GitHub: **Settings** → **Secrets** → **New repository secret**
   - Name: `CODECOV_TOKEN`
   - Value: `<your-codecov-token>`

Note: Codecov upload continues on error, so this is optional.

## Testing the Pipeline

### Initial Push

1. **Commit all CI/CD files:**
   ```bash
   git add .github/ ops/ CI.md CHANGELOG.md SETUP_CICD.md
   git commit -m "feat: add comprehensive CI/CD pipeline

   - Add GitHub Actions workflows for CI/CD and releases
   - Add Dependabot configuration
   - Add deployment scripts and documentation
   - Add security scanning with CodeQL and Trivy
   - Add SBOM generation
   - Add multi-platform container builds
   "
   git push origin main
   ```

2. **Monitor the workflow:**
   - Go to **Actions** tab in GitHub
   - Watch "CI/CD Pipeline" workflow run
   - All jobs should complete successfully (green checkmarks)

3. **Verify container image:**
   - After workflow completes, go to your profile → **Packages**
   - You should see `yt-feed-aggregator` package
   - Multiple tags should be present: `main`, `latest`, `sha-<hash>`

### Testing Pull Requests

1. **Create a test branch:**
   ```bash
   git checkout -b test/ci-pipeline
   echo "# Test" >> README.md
   git add README.md
   git commit -m "test: verify CI pipeline on PR"
   git push origin test/ci-pipeline
   ```

2. **Create a Pull Request:**
   - Go to GitHub and create a PR from `test/ci-pipeline` to `main`
   - Watch the CI checks run
   - All checks should pass
   - Note: Container build job is skipped on PRs (only runs on main)

3. **Verify status checks:**
   - PR should show all required checks passing
   - If branch protection is enabled, "Merge" button appears only after checks pass

## Creating Your First Release

### 1. Update Version Numbers

```bash
# Update pyproject.toml
sed -i 's/version = "0.1.0"/version = "1.0.0"/' pyproject.toml

# Update frontend/package.json
sed -i 's/"version": "1.0.0"/"version": "1.0.0"/' frontend/package.json
```

### 2. Update CHANGELOG.md

Edit `CHANGELOG.md` to document changes:

```markdown
## [1.0.0] - 2025-01-05

### Added
- Initial release
- Google OAuth authentication
- YouTube subscription fetching
- RSS feed aggregation
- Clean dark-mode UI
- Multi-platform container images
```

### 3. Commit and Tag

```bash
git add pyproject.toml frontend/package.json CHANGELOG.md
git commit -m "chore: bump version to 1.0.0"
git push origin main

# Create and push tag
git tag v1.0.0
git push origin v1.0.0
```

### 4. Monitor Release Workflow

1. Go to **Actions** tab
2. Watch "Release" workflow execute
3. Verify all jobs complete successfully

### 5. Check the Release

1. Go to **Releases** section of your repository
2. You should see "Release v1.0.0"
3. Verify:
   - ✅ Release notes are generated
   - ✅ SBOM artifact is attached
   - ✅ Container images are tagged

## Dependabot Setup

Dependabot is configured via `.github/dependabot.yml` and will:

- Create PRs weekly for dependency updates
- Group related updates together
- Auto-assign PRs to `darkflib`

### First Dependabot Run

1. **Trigger manually (optional):**
   - Go to **Insights** → **Dependency graph** → **Dependabot**
   - Click **Check for updates** for each ecosystem

2. **Review PRs:**
   - Dependabot will create PRs in **Pull requests** tab
   - Review changes, check CI status
   - Merge approved updates

### Configuring Auto-merge (Optional)

For minor/patch updates, you can enable auto-merge:

1. Install [Dependabot auto-merge GitHub Action](https://github.com/marketplace/actions/dependabot-auto-merge)
2. Or manually enable auto-merge on each PR:
   ```bash
   gh pr merge <PR-number> --auto --squash
   ```

## Monitoring and Alerts

### 1. Workflow Notifications

Enable notifications for workflow failures:

1. Go to **Settings** → **Notifications**
2. Under **Actions**, enable:
   - ✅ Send notifications for failed workflows only
   - ✅ Send notifications for workflow runs on branches I own

### 2. Security Alerts

Monitor security findings:

1. **Code scanning alerts:** **Security** → **Code scanning**
2. **Dependabot alerts:** **Security** → **Dependabot**
3. **Secret scanning:** **Security** → **Secret scanning** (if enabled)

### 3. Package Insights

Monitor container registry:

1. Go to your **Packages**
2. Click on **yt-feed-aggregator**
3. View:
   - Download statistics
   - Package versions
   - Security vulnerabilities

## Troubleshooting

### Workflow Fails with Permission Errors

**Issue:** Container push fails with 403 or permission denied

**Solution:**
1. Verify Actions workflow permissions: **Settings** → **Actions** → **General**
2. Ensure "Read and write permissions" is selected
3. Re-run the workflow

### CodeQL Analysis Fails

**Issue:** CodeQL job fails or times out

**Solution:**
1. CodeQL can be slow on large repositories
2. Limit languages if needed in `ci.yml`:
   ```yaml
   with:
     languages: python  # Remove javascript if not needed
   ```

### Dependabot PRs Not Created

**Issue:** No Dependabot PRs after a week

**Solution:**
1. Check syntax: `.github/dependabot.yml`
2. View Dependabot logs: **Insights** → **Dependency graph** → **Dependabot**
3. Manually trigger: Click **Check for updates**

### Container Build Fails

**Issue:** Multi-platform build fails or times out

**Solution:**
1. Check Containerfile syntax
2. Reduce platforms if needed (remove arm64):
   ```yaml
   platforms: linux/amd64  # Remove linux/arm64 if causing issues
   ```

### Test Job Fails - Service Containers

**Issue:** Tests fail to connect to Redis or PostgreSQL

**Solution:**
1. Check service health in workflow logs
2. Verify connection strings in test environment variables
3. Increase health check timeout if needed

## Advanced Configuration

### Custom Runners

To use self-hosted runners instead of GitHub-hosted:

1. Set up runner: **Settings** → **Actions** → **Runners** → **New self-hosted runner**
2. Update workflows:
   ```yaml
   runs-on: self-hosted  # Instead of ubuntu-latest
   ```

### Matrix Testing

To test more Python or Node versions:

```yaml
strategy:
  matrix:
    python-version: ['3.12', '3.13', '3.14']
    node-version: ['20', '22']
```

### Deploy to Production on Release

Add deployment job to `release.yml`:

```yaml
deploy:
  name: Deploy to Production
  runs-on: ubuntu-latest
  needs: build-release-container
  steps:
    - name: Trigger deployment
      run: |
        curl -X POST https://your-server.com/deploy \
          -H "Authorization: Bearer ${{ secrets.DEPLOY_TOKEN }}"
```

### Slack/Discord Notifications

Add notification step to workflows:

```yaml
- name: Notify on failure
  if: failure()
  uses: 8398a7/action-slack@v3
  with:
    status: ${{ job.status }}
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

## Best Practices

1. **Keep workflows fast:**
   - Use caching aggressively
   - Run jobs in parallel when possible
   - Skip unnecessary jobs with `if` conditions

2. **Secure secrets:**
   - Never commit secrets to repository
   - Use GitHub Secrets for sensitive values
   - Rotate secrets periodically

3. **Review Dependabot PRs:**
   - Don't auto-merge all updates blindly
   - Test major version updates carefully
   - Check changelogs for breaking changes

4. **Monitor workflows:**
   - Check Actions tab regularly
   - Fix failing workflows promptly
   - Keep workflow definitions up to date

5. **Tag releases properly:**
   - Use semantic versioning
   - Include comprehensive changelogs
   - Test releases before tagging

## Maintenance

### Weekly Tasks

- Review Dependabot PRs
- Check security alerts
- Monitor workflow success rates

### Monthly Tasks

- Review and update workflow dependencies
- Check for new GitHub Actions features
- Optimize build times if needed
- Review container image sizes

### Quarterly Tasks

- Update base images in Containerfile
- Review and update security policies
- Audit and clean up old container images
- Update documentation

## Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [GHCR Documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Dependabot Documentation](https://docs.github.com/en/code-security/dependabot)
- [CodeQL Documentation](https://codeql.github.com/docs/)
- [Semantic Versioning](https://semver.org/)

## Getting Help

If you encounter issues:

1. Check workflow logs in Actions tab
2. Review this guide and [CI.md](CI.md)
3. Search [GitHub Actions community forum](https://github.community/c/code-to-cloud/github-actions/41)
4. Open an issue in the repository

---

**Next Steps:**

After completing this setup:

1. ✅ Push code and verify CI pipeline runs
2. ✅ Create a test PR to verify branch protection
3. ✅ Create your first release tag
4. ✅ Set up deployment automation using `ops/` scripts
5. ✅ Configure monitoring and alerts

For deployment setup, see [ops/README.md](ops/README.md).
