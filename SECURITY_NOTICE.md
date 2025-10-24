# 🚨 CRITICAL SECURITY NOTICE

## BEFORE PUSHING TO GITHUB - READ THIS!

The following API tokens were found in your git history and MUST be revoked before making this repository public:

### Exposed Tokens (Found in .env file in git history)

1. **GitHub Personal Access Token**
   - Token: `[REDACTED - Token removed for security]`
   - Action Required: Revoke at https://github.com/settings/tokens
   - Create a new token and add to `.env` file (which is now gitignored)

2. **Hugging Face Token**
   - Token: `[REDACTED - Token removed for security]`
   - Action Required: Revoke at https://huggingface.co/settings/tokens
   - Create a new token and add to `.env` file (which is now gitignored)

## What Has Been Fixed

✅ Removed `.env` from git tracking
✅ Removed `*.db` files from git tracking
✅ Removed `configs/config.json` from git tracking
✅ Updated `.gitignore` to prevent future commits of sensitive files
✅ Sanitized config files to remove private network paths
✅ Created MIT LICENSE file
✅ Updated documentation placeholders

## What You MUST Do Before Publishing

### Step 1: Revoke All Exposed Tokens (CRITICAL)

Both tokens above are exposed in your git history and can be accessed by anyone who clones your repository once it's public.

**GitHub Token:**
1. Go to https://github.com/settings/tokens
2. Find the token starting with `ghp_cmzH...`
3. Click "Delete" or "Revoke"
4. Create a new token with the same permissions
5. Add it to your `.env` file (NOT in git)

**Hugging Face Token:**
1. Go to https://huggingface.co/settings/tokens
2. Find the token starting with `hf_itei...`
3. Click "Delete" or "Revoke"
4. Create a new token
5. Add it to your `.env` file (NOT in git)

### Step 2: Clean Git History (OPTIONAL BUT RECOMMENDED)

These files are still in your git history. To completely remove them:

```bash
# Install BFG Repo-Cleaner
# macOS: brew install bfg
# Or download from: https://roboboogie.com/BFG-repo-cleaner/

# Backup your repo first!
cd ..
cp -r codelupe codelupe-backup

cd codelupe

# Remove sensitive files from history
bfg --delete-files .env
bfg --delete-files '*.db'

# Clean up
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Force push to overwrite history (if already pushed)
# git push --force origin main
```

**WARNING:** Force pushing rewrites history. Only do this if:
- You haven't shared this repo with others yet, OR
- You coordinate with all collaborators

### Step 3: Verify Clean State

```bash
# Check that sensitive files are not tracked
git ls-files | grep -E '\.(env|db)$'
# Should return nothing

# Check that config.json is not tracked
git ls-files | grep config.json
# Should only show config.example.json

# Verify files exist locally but are gitignored
ls -la .env configs/config.json *.db
# Files should exist

git status
# Should show "nothing to commit" or only show legitimate changes
```

### Step 4: Commit and Push

Once you've revoked the tokens and cleaned the history (if desired):

```bash
git add -A
git commit -m "chore: prepare repository for public release

- Remove sensitive files from git tracking
- Add MIT LICENSE
- Update .gitignore for better security
- Sanitize configuration files
- Update documentation placeholders"

# If you cleaned history, force push:
# git push --force origin main

# Otherwise, normal push:
git push origin main
```

## Ongoing Security Practices

1. **Never commit secrets**: Use `.env` files and keep them gitignored
2. **Use environment variables**: Load secrets from environment in production
3. **Review before commits**: Use `git status` and `git diff` before committing
4. **Enable secret scanning**: GitHub has free secret scanning for public repos
5. **Regular audits**: Periodically check for accidentally committed secrets

## After Publishing

Once published, GitHub's secret scanning may automatically detect and notify you of exposed secrets. Respond promptly to any alerts.

## Questions?

If you're unsure about any step, DO NOT publish the repository yet. Take time to:
1. Revoke the exposed tokens first (most critical)
2. Research git history cleaning
3. Consult security best practices

---

**DELETE THIS FILE** before making the repository public, or keep it as a reminder of security practices.

Last updated: 2024-10-24
