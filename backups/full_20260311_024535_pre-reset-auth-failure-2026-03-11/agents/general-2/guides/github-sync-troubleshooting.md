# GitHub Sync Troubleshooting Guide

## Common Errors & Fixes

### Error: 410 Gone + Permission Denied
**Cause:** Repository access revoked or token expired
**Fix:**
```bash
git remote -v  # Verify remote URL
git config --global credential.helper cache
git credential-manager clear # Clear cached credentials
```

### Error: TypeError: .filter() on undefined
**Cause:** System bug in OpenClaw's git sync handler
**Fix:** Report to system admin; retry after restart

### Error: SSH Auth Denied (publickey)
**Cause:** SSH key not in GitHub or key not loaded
**Fix:**
```bash
ssh-add -l  # Check loaded keys
ssh-add ~/.ssh/id_ed25519  # Add key if missing
cat ~/.ssh/id_ed25519.pub  # Verify on GitHub
```

### Error: Repository Not Found
**Cause:** Repo deleted, renamed, or no access
**Fix:**
```bash
git remote set-url origin <new-url>
```

## Current Blocked Commit
- Commit: `4c744b8`
- Status: Saved locally
- Blocker: SSH auth
