# Security Considerations for Amplify MCP Servers

**Last Updated**: February 20, 2025

This document outlines critical security considerations for the example MCP servers in this repository.

---

## 🚨 CRITICAL: These are Example Templates

**These servers are demonstration examples with known security limitations.** They are functional for learning and demos but require extensive hardening before production use.

---

## Critical Security Issue: AWS Credentials Exposure in Jupyter Server

### The Problem

**Severity**: CRITICAL
**Status**: FIXED (as of latest commit)
**Affected Server**: Jupyter Notebook MCP Server

#### Description

Lambda functions receive temporary AWS credentials via environment variables:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN`

These credentials grant the Lambda function access to AWS resources based on its IAM execution role.

**Vulnerability**: If user code can access `os.environ` (which it can by default in Jupyter), users could:
1. See the Lambda execution role credentials
2. Use those credentials to access AWS resources
3. Potentially read S3 buckets, call other AWS services, etc.
4. Violate security boundaries and least privilege principles

#### Example of the Vulnerability

```python
# User executes this in Jupyter cell:
import os
print(dict(os.environ))

# Output includes:
# {
#   'AWS_ACCESS_KEY_ID': 'ASIAZQ3DRXZ6THGWQIIH',
#   'AWS_SECRET_ACCESS_KEY': 'ygczQ0cmHU06TarvXKrOyuAqErj3S6WKr5nM56Re',
#   'AWS_SESSION_TOKEN': 'IQoJb3JpZ2luX2VjENL...',
#   ...
# }
```

### The Fix

**Location**: `servers/jupyter/jupyter_mcp_server/kernel_manager.py`

**Implementation**: The `_sanitize_environment()` method now:

1. **Removes sensitive AWS credentials** before starting the Jupyter kernel:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `AWS_SESSION_TOKEN`
   - `AWS_SECURITY_TOKEN`

2. **Removes Lambda metadata** that could leak sensitive information:
   - `AWS_LAMBDA_FUNCTION_NAME`
   - `AWS_LAMBDA_FUNCTION_VERSION`
   - `AWS_LAMBDA_LOG_GROUP_NAME`
   - `AWS_LAMBDA_LOG_STREAM_NAME`
   - `AWS_LAMBDA_FUNCTION_MEMORY_SIZE`
   - X-Ray daemon addresses

3. **Keeps essential variables** for Python/Jupyter functionality:
   - `PATH`, `HOME`, `LANG`, `PYTHONPATH`, `MPLBACKEND`

**Code**:
```python
def _sanitize_environment(self):
    """Remove sensitive AWS credentials from environment"""
    sensitive_keys = [
        'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY',
        'AWS_SESSION_TOKEN',
        'AWS_SECURITY_TOKEN',
        'AWS_LAMBDA_FUNCTION_NAME',
        # ... etc
    ]

    # Create sanitized environment without sensitive keys
    sanitized = {k: v for k, v in os.environ.items()
                 if k not in sensitive_keys}

    return sanitized
```

### Verification

After the fix, running `import os; print(dict(os.environ))` in Jupyter should NOT show any AWS credentials.

### Limitations of the Fix

This fix prevents **environment variable** access to credentials, but does NOT provide:

- **User authentication**: Still need to verify WHO is executing code
- **User isolation**: Multiple users could share the same kernel
- **Resource limits**: No CPU/memory limits per user
- **Network restrictions**: User code can still make outbound connections
- **File system isolation**: Users can potentially access /tmp files from other requests
- **Code sandboxing**: No restrictions on what Python code can do (beyond env access)

---

## Additional Security Requirements for Production

### 1. User Authentication and Authorization

**Current State**: No authentication
**Production Need**:
- Verify user identity before allowing code execution
- Implement API key or OAuth token validation
- Add role-based access control (RBAC)

**Example Implementation**:
```python
def verify_user(request):
    api_key = request.headers.get('X-API-Key')
    user = lookup_user_by_api_key(api_key)
    if not user:
        raise Unauthorized("Invalid API key")
    return user
```

### 2. User Isolation

**Current State**: Shared kernel, shared filesystem
**Production Need**:
- Separate Jupyter kernel per user
- Isolate user workspaces (/tmp directories)
- Prevent users from accessing each other's data

**Example Implementation**:
- Use user-specific S3 prefixes: `s3://bucket/users/{user_id}/`
- Create per-user temp directories: `/tmp/user_{user_id}/`
- Track kernel ownership and prevent cross-user access

### 3. Resource Limits

**Current State**: Lambda limits only (memory, timeout)
**Production Need**:
- Per-user CPU quotas
- Per-user memory limits
- Execution time limits per code cell
- Disk space quotas

**Example Implementation**:
```python
import resource
import signal

# Set CPU time limit (5 seconds)
resource.setrlimit(resource.RLIMIT_CPU, (5, 5))

# Set memory limit (512 MB)
resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
```

### 4. Code Sandboxing

**Current State**: Environment sanitization only
**Production Need**:
- Restricted Python execution environment
- Whitelist allowed modules/functions
- Block dangerous operations (file I/O, subprocess, network)

**Example Options**:
- Use RestrictedPython library
- Run kernels in separate containers with seccomp/AppArmor
- Use gVisor or Firecracker for VM-level isolation

### 5. Audit Logging

**Current State**: Basic CloudWatch logs
**Production Need**:
- Log all code execution with user attribution
- Track file access and modifications
- Log package installations
- Monitor for suspicious patterns

**Example Implementation**:
```python
def log_execution(user_id, code, result):
    audit_log.info({
        'event': 'code_execution',
        'user_id': user_id,
        'code_hash': hashlib.sha256(code.encode()).hexdigest(),
        'code_length': len(code),
        'execution_time_ms': result['duration'],
        'success': result['success'],
        'timestamp': datetime.utcnow().isoformat()
    })
```

### 6. Network Restrictions

**Current State**: Full network access
**Production Need**:
- Whitelist allowed outbound destinations
- Block access to internal AWS metadata service (169.254.169.254)
- Rate limit network requests

**Example Implementation**:
- Deploy Lambda in VPC with restrictive security groups
- Use VPC endpoints for AWS services only
- Block 169.254.169.254 at network level

### 7. Package Installation Controls

**Current State**: Any pip package can be installed
**Production Need**:
- Whitelist approved packages only
- Scan packages for known vulnerabilities
- Prevent malicious package installation

**Example Implementation**:
```python
ALLOWED_PACKAGES = ['pandas', 'numpy', 'scikit-learn', 'matplotlib']

def install_package(package_name):
    if package_name not in ALLOWED_PACKAGES:
        raise SecurityError(f"Package {package_name} not in whitelist")
    # Proceed with installation
```

### 8. Input Validation and Sanitization

**Current State**: Basic validation
**Production Need**:
- Validate all input parameters
- Sanitize code before execution
- Limit input sizes
- Prevent code injection

**Example Implementation**:
```python
def validate_code(code: str):
    if len(code) > 100000:  # 100KB limit
        raise ValidationError("Code too large")

    # Block dangerous imports
    forbidden = ['os.system', 'subprocess', 'eval', 'exec']
    if any(dangerous in code for dangerous in forbidden):
        raise SecurityError("Forbidden operations detected")

    return code
```

---

## Security Checklist for Production Deployment

Before deploying to production, ensure you have implemented:

- [ ] **User Authentication**: Verify user identity on every request
- [ ] **User Authorization**: Check user permissions for requested operations
- [ ] **User Isolation**: Separate kernels and workspaces per user
- [ ] **Resource Limits**: CPU, memory, time, and disk quotas per user
- [ ] **Environment Sanitization**: Strip sensitive variables (✅ DONE)
- [ ] **Code Sandboxing**: Restrict dangerous operations
- [ ] **Network Restrictions**: Limit outbound connections
- [ ] **Audit Logging**: Comprehensive logging with user attribution
- [ ] **Package Controls**: Whitelist/scan pip packages
- [ ] **Input Validation**: Validate and sanitize all inputs
- [ ] **Rate Limiting**: Prevent abuse via request throttling
- [ ] **Monitoring & Alerts**: Detect and alert on suspicious activity
- [ ] **Incident Response Plan**: Documented procedures for security incidents
- [ ] **Regular Security Audits**: Periodic code reviews and penetration testing
- [ ] **Dependency Updates**: Keep all libraries and frameworks up to date

---

## Other Server Security Considerations

### Data Transformation Server

**Considerations**:
- Input size limits (prevent memory exhaustion)
- XML entity expansion attacks (XXE)
- YAML deserialization vulnerabilities
- CSV injection attacks

**Mitigations**:
- Limit input size to reasonable values
- Disable external entity resolution in XML parser
- Use safe YAML loader (SafeLoader)
- Sanitize CSV output for formula injection

### Image Processing Server

**Considerations**:
- Image bomb attacks (huge decompressed size)
- Buffer overflow vulnerabilities in image libraries
- Path traversal in filename parameters
- Excessive memory usage

**Mitigations**:
- Validate image dimensions before processing
- Set memory limits on PIL operations
- Sanitize filenames (no path traversal)
- Use latest Pillow version with security patches

### Node.js Execution Server

**Considerations**:
- Code injection vulnerabilities
- Prototype pollution attacks
- Infinite loops (DoS)
- Access to sensitive Node.js APIs

**Mitigations**:
- VM sandbox with limited context (✅ DONE)
- Timeout enforcement (✅ DONE)
- No filesystem or network access from VM (✅ DONE)
- Regularly update Node.js runtime

---

## Reporting Security Issues

If you discover a security vulnerability in these example servers:

1. **DO NOT** open a public GitHub issue
2. Email security concerns to the repository maintainers
3. Include detailed reproduction steps
4. Allow time for a fix before public disclosure

---

## Disclaimer

**These MCP servers are provided as educational examples.** They demonstrate how to build MCP servers but are not production-ready without significant additional security hardening.

**Use at your own risk.** Users are responsible for:
- Implementing appropriate security measures
- Meeting compliance requirements
- Following security best practices
- Regular security audits and updates

The maintainers of this repository are not responsible for security issues arising from the use of these example servers in production environments.

---

## Additional Resources

- [AWS Lambda Security Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/lambda-security.html)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Python Security Best Practices](https://python.readthedocs.io/en/stable/library/security_warnings.html)
- [Jupyter Security Documentation](https://jupyter-notebook.readthedocs.io/en/stable/security.html)
- [AWS Well-Architected Framework - Security Pillar](https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/welcome.html)
