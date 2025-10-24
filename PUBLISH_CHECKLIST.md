# GitHub Publication Checklist

Use this checklist before publishing the CodeLupe repository to GitHub.

## ✅ Completed (Already Done)

- [x] Removed `.env` from git tracking
- [x] Removed `*.db` files from git tracking
- [x] Removed `configs/config.json` from git tracking
- [x] Updated `.gitignore` with comprehensive patterns
- [x] Sanitized `configs/config.json` (removed private network paths)
- [x] Created MIT LICENSE file
- [x] Updated README.md with correct GitHub username (n0tt1m)
- [x] Updated CONTRIBUTING.md with correct repository URLs
- [x] Created security documentation (SECURITY_NOTICE.md)
- [x] Created PR template for contributors

## 🚨 CRITICAL - You Must Do This BEFORE Publishing

### 1. Revoke Exposed API Tokens (MANDATORY)

**GitHub Token:** `[REDACTED - Token removed for security]`
- [ ] Go to https://github.com/settings/tokens
- [ ] Find and delete this token
- [ ] Create new token with same permissions
- [ ] Add new token to `.env` file (NOT git)
- [ ] Test that new token works

**Hugging Face Token:** `[REDACTED - Token removed for security]`
- [ ] Go to https://huggingface.co/settings/tokens
- [ ] Find and delete this token
- [ ] Create new token
- [ ] Add new token to `.env` file (NOT git)
- [ ] Test that new token works

### 2. Update Your Local Config Files

- [ ] Update `.env` with new tokens
- [ ] Update `configs/config.json` with your actual settings (stays local, not committed)
- [ ] Verify both files are listed when you run: `git status` under "Untracked files"

## ⚠️ Recommended (But Optional)

### Clean Git History

To completely remove sensitive data from git history:

```bash
# Backup first!
cd .. && cp -r codelupe codelupe-backup && cd codelupe

# Install BFG (macOS)
brew install bfg

# Remove files from entire history
bfg --delete-files .env
bfg --delete-files '*.db'

# Cleanup
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

- [ ] Backed up repository
- [ ] Installed BFG Repo-Cleaner
- [ ] Removed .env from history
- [ ] Removed .db files from history
- [ ] Cleaned up git objects

## 📋 Pre-Publish Verification

Run these commands to verify everything is clean:

```bash
# Should return NOTHING
git ls-files | grep -E '\.(env|db)$'

# Should return ONLY config.example.json
git ls-files | grep config.json

# Should show files exist locally
ls -la .env configs/config.json

# Review what will be committed
git status
```

- [ ] No `.env` files in git tracking
- [ ] No `.db` files in git tracking
- [ ] No `configs/config.json` in git tracking
- [ ] Sensitive files exist locally but are gitignored
- [ ] Git status looks clean

## 🎯 Final Commit & Push

Once all critical steps are complete:

```bash
# Stage changes
git add .gitignore CONTRIBUTING.md README.md LICENSE SECURITY_NOTICE.md .github/

# Commit
git commit -m "chore: prepare repository for public release

- Remove sensitive files from git tracking
- Add MIT LICENSE
- Improve .gitignore security
- Sanitize configuration files
- Update documentation with correct URLs
- Add security documentation"

# Push (normal or force if you cleaned history)
git push origin main
# OR if you cleaned history:
# git push --force origin main
```

- [ ] Committed all changes
- [ ] Pushed to GitHub

## 🚀 Post-Publication

After making the repository public:

- [ ] Enable GitHub secret scanning (Settings → Security → Code security)
- [ ] Add repository description
- [ ] Add topics/tags (AI, machine-learning, code-quality, github-crawler, etc.)
- [ ] Review README renders correctly on GitHub
- [ ] Test clone from GitHub to verify everything works
- [ ] Delete SECURITY_NOTICE.md and PUBLISH_CHECKLIST.md (or keep as reference)
- [ ] Celebrate! 🎉

## 📧 If You Get a GitHub Secret Scanning Alert

If GitHub detects secrets after publishing:

1. **Don't panic** - You've already revoked the tokens
2. Confirm the alert is for the old revoked tokens
3. Mark the alert as "Revoked" in GitHub
4. Consider cleaning git history if you haven't already

## 🔒 Ongoing Security

- Never commit `.env` files
- Always use `git status` before committing
- Review `git diff --cached` before committing
- Use environment variables in production
- Rotate tokens regularly
- Enable GitHub Dependabot for security updates

---

**Last Updated:** 2024-10-24
**Status:** Ready for publication after token revocation
