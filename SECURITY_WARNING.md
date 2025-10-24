# Security Warning - GitHub Token Exposed

## CRITICAL ACTION REQUIRED

A GitHub Personal Access Token was found exposed in `configs/config.json`:
- Token: `[REDACTED - Token removed for security]`
- File: `configs/config.json` line 4

## Immediate Steps Required:

1. **Revoke the exposed token immediately:**
   - Go to: https://github.com/settings/tokens
   - Find the token that was exposed (starts with `ghp_`)
   - Click "Delete" to revoke it

2. **Generate a new token:**
   - Go to: https://github.com/settings/tokens/new
   - Set appropriate scopes (repo, read:org)
   - Copy the new token

3. **Store the token securely:**
   ```bash
   # Option 1: Environment variable (recommended)
   export GITHUB_TOKEN="your_new_token_here"

   # Option 2: .env file (also gitignored)
   echo "GITHUB_TOKEN=your_new_token_here" > .env
   ```

4. **Update docker-compose.yml:**
   The token is already configured to read from environment:
   ```yaml
   environment:
     - GITHUB_TOKEN=${GITHUB_TOKEN}
   ```

5. **Verify git history:**
   ```bash
   # Check if token was committed to git
   git log -p --all -S "ghp_"
   ```

6. **If token is in git history, consider:**
   - Using BFG Repo-Cleaner to remove it from history
   - Rotating all secrets
   - Notifying your security team

## Files Updated:
- ✅ `.gitignore` - Added `configs/config.json` to ignore list
- ✅ `configs/config.example.json` - Created template without secrets
- ✅ `configs/config.json` - Removed exposed token (replaced with placeholder)

## Going Forward:
- Never commit secrets to version control
- Use environment variables or secret management tools
- Use pre-commit hooks to scan for secrets
- Consider using tools like git-secrets or detect-secrets
