# Security Guidelines

## Environment Variables and Secrets Management

### Generating Secrets

**NEVER commit real secrets to version control!**

Generate cryptographically secure secrets:

```bash
# App Secret Key (for JWT signing)
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Token Encryption Key (32 bytes, base64 encoded)
python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

### Environment Setup

1. Copy `.env.example` to `.env`
2. Generate unique secrets for each environment (dev, staging, production)
3. Configure Google OAuth credentials from https://console.cloud.google.com/apis/credentials
4. Verify `.env` is in `.gitignore` (it is by default)

### Production Secrets Management

For production deployments, use a proper secrets management system:

- **AWS**: AWS Secrets Manager or Parameter Store
- **GCP**: Secret Manager
- **Azure**: Key Vault
- **Self-hosted**: HashiCorp Vault
- **Kubernetes**: Sealed Secrets or External Secrets Operator

### Secret Rotation Policy

- Rotate secrets every 90 days minimum
- Rotate immediately if:
  - A team member with access leaves
  - Secrets are suspected to be compromised
  - After any security incident
  - Secrets are accidentally committed to version control

## Security Best Practices

### Authentication
- Session tokens use JWT with HS256
- Tokens expire after 7 days
- Refresh tokens are encrypted using Fernet (AES-128 CBC)
- All authentication endpoints should be rate-limited

### API Security
- CORS is configured to allow specific origins only
- All sensitive endpoints require authentication
- Input validation on all parameters
- Rate limiting on expensive operations

### Database Security
- Use parameterized queries (SQLAlchemy ORM handles this)
- Never construct SQL from user input
- Limit database user permissions in production

### Deployment Security
- Always use HTTPS in production (secure cookies require it)
- Set proper security headers (X-Frame-Options, CSP, etc.)
- Run containers as non-root user
- Keep dependencies updated regularly

## Reporting Security Issues

If you discover a security vulnerability:

1. **DO NOT** create a public GitHub issue
2. Email the maintainer directly with details
3. Include steps to reproduce if possible
4. Allow reasonable time for fix before disclosure

## Security Audit

See `SECURITY_AUDIT.md` for the latest security audit findings and remediation status.

Last updated: 2025-11-06
