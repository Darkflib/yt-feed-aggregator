# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive CI/CD pipeline with GitHub Actions
- Automated testing for Python 3.12 and 3.13
- Multi-platform container builds (amd64, arm64)
- Security scanning with CodeQL and Trivy
- SBOM generation for releases
- Dependabot for automated dependency updates
- Deployment automation scripts

### Changed
- Enhanced README with CI/CD badges and documentation

### Security
- Automated security scanning in CI pipeline
- Container vulnerability scanning with Trivy

## [0.1.0] - Initial Development

### Added
- Project structure and core configuration
- Database layer with SQLAlchemy
- Google OAuth authentication
- YouTube API client for subscriptions
- RSS feed fetching and caching
- Feed aggregation and pagination
- FastAPI backend API
- React + Vite frontend (in progress)
- Container support with multi-stage Containerfile

[Unreleased]: https://github.com/darkflib/yt-feed-aggregator/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/darkflib/yt-feed-aggregator/releases/tag/v0.1.0
