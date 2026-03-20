# Security Policy

## Reporting Vulnerabilities

If you discover a security vulnerability in CarbonScope, please report it responsibly.

**Do NOT open a public issue.** Instead, email security concerns to **security@carbonscope.io** or contact the maintainers privately. Include:

1. Description of the vulnerability
2. Steps to reproduce
3. Potential impact assessment
4. Suggested remediation (if any)

We aim to acknowledge reports within 48 hours and provide a resolution timeline within 7 days.

---

## Supported Versions

| Version | Supported |
| :------ | :-------: |
| 0.27.x  |    ✅     |
| 0.26.x  |    ✅     |
| 0.25.x  |    ✅     |
| 0.24.x  |    ✅     |
| 0.23.x  |    ✅     |
| 0.22.x  |    ✅     |
| 0.21.x  |    ✅     |
| 0.20.x  |    ✅     |
| 0.19.x  |    ✅     |
| < 0.19  |    ❌     |

---

## Security Architecture

### Authentication

| Feature               | Implementation                                                      |
| :-------------------- | :------------------------------------------------------------------ |
| **Password Hashing**  | bcrypt via passlib                                                  |
| **Access Tokens**     | JWT (HS256) with 60-minute expiry and unique JTI                    |
| **Refresh Tokens**    | SHA-256 hashed, persisted in DB, single-use rotation, 30-day expiry |
| **Token Revocation**  | JTI-based access token blacklist (checked on every request)         |
| **Cookie Auth**       | httpOnly, Secure (production), SameSite=lax                         |
| **CSRF Protection**   | Double-submit cookie pattern (`X-CSRF-Token` header)                |
| **Account Lockout**   | 5 failed attempts → 15-minute lockout                               |
| **Password Reset**    | SHA-256 hashed tokens, 15-minute expiry, single-use                 |
| **Password Strength** | Minimum 8 characters with complexity requirements                   |
| **MFA (TOTP)**        | RFC 4226/6238 TOTP with backup codes, pure Python implementation    |

### Authorization

| Feature               | Implementation                                                     |
| :-------------------- | :----------------------------------------------------------------- |
| **Role-Based Access** | `admin` and `member` roles via `require_admin()` dependency        |
| **Tenant Isolation**  | All queries filtered by `company_id` — cross-tenant access blocked |
| **Plan Gating**       | `require_plan(feature)` restricts features by subscription tier    |
| **Credit Gating**     | `require_credits(operation)` checks and deducts credits atomically |

### Transport Security

| Feature                | Implementation                                                             |
| :--------------------- | :------------------------------------------------------------------------- |
| **HTTPS**              | TLS termination at Nginx; HSTS header auto-added on HTTPS responses        |
| **CORS**               | Strict origin allowlist via `ALLOWED_ORIGINS` env var                      |
| **Security Headers**   | CSP, X-Frame-Options DENY, X-Content-Type-Options nosniff, Referrer-Policy |
| **Permissions-Policy** | Camera, microphone, geolocation disabled                                   |

### Input Validation & Injection Prevention

| Threat             | Mitigation                                                                     |
| :----------------- | :----------------------------------------------------------------------------- |
| **SQL Injection**  | SQLAlchemy ORM with parameterized queries — no raw SQL                         |
| **XSS**            | Content-Security-Policy header; React auto-escapes output by default           |
| **SSRF**           | Webhook URLs validated against private/internal IP ranges (`url_validator.py`) |
| **File Upload**    | 10 MB limit, file type whitelist (PDF, DOCX, XLSX, CSV), content validation    |
| **Request Body**   | 1 MB global limit via `RequestBodyLimitMiddleware`                             |
| **Path Traversal** | File names sanitized before processing                                         |

### Rate Limiting

| Scope                       | Limit     | Purpose                                 |
| :-------------------------- | :-------- | :-------------------------------------- |
| Auth                        | 10/minute | Prevent brute-force login attempts      |
| Default                     | 60/minute | General API abuse protection            |
| `/estimate`                 | 5/minute  | Protect expensive estimation operations |
| `/scenarios/*/compute`      | 5/minute  | Protect scenario computation engine     |
| `/questionnaires/upload`    | 5/minute  | Limit file upload processing            |
| `/questionnaires/*/extract` | 5/minute  | Protect expensive AI extraction         |
| `/marketplace/*/purchase`   | 10/minute | Limit purchase operations               |
| `/billing/subscription`     | 5/minute  | Protect subscription changes            |
| `/stripe/webhooks`          | 60/minute | Stripe event ingestion                  |

Rate limiting is IP-based (supports `X-Forwarded-For` when `TRUST_PROXY=true`).

### Health & Diagnostics

| Endpoint             | Access     | Detail                                                  |
| :------------------- | :--------- | :------------------------------------------------------ |
| `GET /health`        | Public     | Returns `{"status": "healthy"}` only (no internals)     |
| `GET /health/detail` | Admin-only | Full system info (DB, Redis, versions) behind auth gate |
| `GET /metrics`       | Admin-only | Prometheus-compatible application metrics               |

### Audit & Monitoring

| Feature             | Implementation                                                    |
| :------------------ | :---------------------------------------------------------------- |
| **Audit Logging**   | All CRUD operations logged with user ID, action, resource, detail |
| **Request Tracing** | `X-Request-ID` header on every request/response                   |
| **Access Logging**  | Method, path, status, duration logged per request                 |
| **Structured Logs** | JSON format in production for log aggregation                     |

### Data Protection

| Feature           | Implementation                                                   |
| :---------------- | :--------------------------------------------------------------- |
| **GDPR Deletion** | `DELETE /auth/me` soft-deletes account and anonymizes user data  |
| **Soft Deletes**  | Records marked with `deleted_at` rather than permanently removed |
| **Marketplace**   | Data is anonymized before listing (company identity stripped)    |
| **Secrets**       | Webhook HMAC secrets are auto-generated with cryptographic RNG   |

---

## Production Security Enforcement

The application enforces security requirements at startup in production mode:

- `SECRET_KEY` must be ≥ 32 characters with ≥ 10 unique characters
- `DATABASE_URL` must be PostgreSQL (not SQLite)
- `COOKIE_SECURE=true` is enforced for HTTPS-only cookies
- `LOG_JSON=true` is auto-enabled for structured audit logging

---

## Dependency Security

- All Python dependencies are pinned in `requirements.txt`
- All npm dependencies are pinned in `package.json`
- Docker images use specific version tags (e.g., `python:3.12-slim`, `node:20`, `postgres:16-alpine`)
- Containers run as non-root users (`appuser` for backend, `node` for frontend)
- Docker `no-new-privileges` security option is enabled in production

---

## Webhook Security

Webhooks use HMAC-SHA256 for payload authentication:

1. A unique secret is generated per webhook endpoint
2. Payloads are signed with `HMAC-SHA256(secret, body)`
3. The signature is sent in the request header
4. Recipients should verify the signature before processing

Webhook URLs are validated to prevent SSRF attacks:

- Private IP ranges are blocked (10.x, 172.16-31.x, 192.168.x, 127.x, ::1)
- Internal hostnames are blocked (localhost, _.local, _.internal)
- Only HTTPS URLs are accepted in production

---

## Security Best Practices for Deployers

1. **Use strong secrets** — Generate `SECRET_KEY` with `python -c "import secrets; print(secrets.token_hex(32))"`
2. **Enable TLS** — Always use HTTPS in production with valid certificates
3. **Configure CORS** — Set `ALLOWED_ORIGINS` to your exact frontend domain only
4. **Set up SMTP** — Required for password reset functionality
5. **Monitor logs** — Set up alerting on 401/403/500 status codes
6. **Regular backups** — Schedule automated PostgreSQL backups
7. **Update dependencies** — Regularly check for security updates
8. **Restrict network access** — Only expose Nginx (port 443) publicly; backend (8000) and frontend (3000) should be internal only
9. **Rotate secrets** — Periodically rotate `SECRET_KEY` and database credentials
10. **Review audit logs** — Regularly check `/api/v1/audit-logs` for suspicious activity

---

## Incident Response Procedure

### Severity Levels

| Level             | Definition                                             | Response Time        | Examples                                                          |
| :---------------- | :----------------------------------------------------- | :------------------- | :---------------------------------------------------------------- |
| **P0 — Critical** | Active data breach or complete service outage          | Immediate (< 15 min) | Database compromise, credential leak, full service down           |
| **P1 — High**     | Security vulnerability being exploited, partial outage | < 1 hour             | Authentication bypass, moderate data exposure, key subsystem down |
| **P2 — Medium**   | Vulnerability discovered, no active exploitation       | < 24 hours           | XSS/CSRF found, misconfigured permissions, dependency CVE         |
| **P3 — Low**      | Minor hardening improvement, informational             | < 7 days             | Missing headers, verbose error messages, outdated dependency      |

### Response Steps

1. **Detect** — Identify the incident via monitoring alerts, user reports, or audit log anomalies.
2. **Contain** — Isolate affected systems immediately:
   - Revoke compromised tokens: truncate the `refresh_tokens` table or redeploy with a new `SECRET_KEY`.
   - Block malicious IPs at the ingress level: `kubectl -n carbonscope annotate ingress carbonscope-ingress nginx.ingress.kubernetes.io/denylist-source-range="<IP>/32"`.
   - Scale down affected services if necessary: `kubectl -n carbonscope scale deployment backend --replicas=0`.
3. **Investigate** — Gather evidence:
   - Review audit logs: `GET /api/v1/audit-logs?user_id=<suspect>`.
   - Check application logs: `kubectl -n carbonscope logs deploy/backend --since=1h`.
   - Examine database for unauthorized changes.
4. **Remediate** — Fix the root cause:
   - Patch the vulnerability and deploy the fix.
   - Force password resets if credentials were compromised.
   - Rotate secrets (`SECRET_KEY`, `POSTGRES_PASSWORD`, `STRIPE_SECRET_KEY`).
5. **Recover** — Restore normal operations:
   - Verify the fix is deployed and working.
   - Re-enable affected services.
   - Monitor closely for recurrence.
6. **Post-mortem** — Document within 72 hours:
   - Timeline of events.
   - Root cause analysis.
   - Actions taken and their effectiveness.
   - Preventive measures for the future.

### Communication

- **Internal**: Notify the engineering team immediately for P0/P1.
- **External**: Notify affected users within 72 hours if personal data was exposed (GDPR Article 34).
- **Regulatory**: File breach notification with relevant authorities if required (GDPR Article 33: within 72 hours).
