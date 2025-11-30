# Security Policy

## Commitment to Security

The **dapr-state-cache** project takes security seriously. We appreciate your help in keeping this project and its users safe. This document describes how to report security vulnerabilities responsibly.

## Supported Versions

Currently, the following versions receive security updates:

| Version | Supported |
|---------|-----------|
| 0.5.x | Yes |
| 0.4.x | Critical patches only |
| < 0.4 | No |

We recommend always using the latest version to ensure you have all security fixes.

## Reporting a Vulnerability

### How to Report

**Do not report security vulnerabilities through public issues, pull requests, or discussions.**

To report a security vulnerability, choose one of the following options:

1. **GitHub Security Advisories (Recommended)**

   Use GitHub's [Private Vulnerability Reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability) feature to submit a private report directly to the repository.

2. **Direct Email**

   Send an email to: **helton.doria@gmail.com**

   Subject: `[SECURITY] dapr-state-cache - Brief description`

### What to Include in Your Report

To help us understand and resolve the issue quickly, please include:

- **Description** - Clear explanation of the vulnerability
- **Type** - Type of vulnerability (e.g., injection, XSS, authentication bypass)
- **Steps to reproduce** - How to reproduce the issue
- **Affected versions** - Which library versions are affected
- **Potential impact** - What could an attacker achieve
- **Proof of concept** - Code or commands, if available
- **Suggested fix** - Optional, but appreciated

### Response Expectations

| Stage | Expected Time |
|-------|---------------|
| Acknowledgment of receipt | 48 hours |
| Initial assessment | 7 days |
| Fix plan | 14 days |
| Fix and release | 30-90 days* |

*Depending on the complexity and severity of the vulnerability.

## Coordinated Disclosure Process

We follow a **coordinated disclosure** process to protect users:

### 1. Report Received

- We acknowledge receipt within 48 hours
- We create a private advisory for tracking

### 2. Triage and Analysis

- We validate the reported vulnerability
- We assess severity using CVSS
- We determine affected versions

### 3. Fix Development

- We develop the fix in a private fork
- We prepare regression tests
- We review the code internally

### 4. Release and Disclosure

- We publish the fixed version
- We disclose the security advisory
- We update documentation if necessary
- We credit the researcher (if desired)

### 5. Embargo

We ask that you:

- **Do not disclose** publicly until the fix is released
- **Do not exploit** the vulnerability beyond what is necessary for demonstration
- **Give us reasonable time** to develop and test the fix

We respect your work, and after the fix, you will be publicly credited (if you wish) in the security advisory.

## Security Best Practices for Users

### Environment Configuration

1. **Keep Dapr updated**

   ```bash
   dapr upgrade
   ```

2. **Use secure connections with the State Store**

   Configure TLS/SSL for communication with Redis, MongoDB, or other backends.

3. **Isolate the Dapr sidecar**

   The sidecar should only be accessible by the local application:

   ```yaml
   # Configuration example
   apiVersion: dapr.io/v1alpha1
   kind: Configuration
   metadata:
     name: appconfig
   spec:
     api:
       allowed:
         - group: state
           version: v1
           operations: ["get", "set", "delete"]
   ```

### Safe Library Usage

1. **Do not store sensitive data without encryption**

   The library does not encrypt data by default. For sensitive data, consider:

   - Using state stores with at-rest encryption
   - Implementing encryption in the application before caching

2. **Configure appropriate TTLs**

   ```python
   # Sensitive data should have short TTL
   @cacheable(store_name="cache", ttl_seconds=60)  # 1 minute
   def get_sensitive_data():
       pass
   ```

3. **Monitor cache errors**

   ```python
   from dapr_state_cache import cacheable, InMemoryMetrics

   metrics = InMemoryMetrics()

   @cacheable(store_name="cache", metrics=metrics)
   def my_function():
       pass

   # Check errors periodically
   stats = metrics.get_stats()
   if stats.errors > 0:
       logger.warning(f"Cache errors detected: {stats.errors}")
   ```

### Dependencies

Keep library dependencies updated:

```bash
# Check for known vulnerabilities
pip-audit

# or with uv
uv pip compile --upgrade
```

## Scope

This security policy covers:

- Source code of the `dapr-state-cache` library
- Official documentation
- Examples and configuration scripts

**Out of scope:**

- Vulnerabilities in the Dapr runtime
- Vulnerabilities in state stores (Redis, MongoDB, etc.)
- Vulnerabilities in dependencies (report to upstream project)

For vulnerabilities in Dapr, report at: [dapr/dapr Security](https://github.com/dapr/dapr/security)

## Acknowledgments

We thank all security researchers who help keep this project safe. Contributors who have responsibly reported vulnerabilities will be credited (with permission) in our advisories.

## References

- [Open Source Security Best Practices](https://opensource.guide/security-best-practices-for-your-project/)
- [GitHub Security Advisories](https://docs.github.com/en/code-security/security-advisories)
- [Dapr Security](https://docs.dapr.io/operations/security/)
- [CVSS Calculator](https://www.first.org/cvss/calculator/3.1)

---

Last updated: November 2025
