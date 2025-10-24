#!/bin/bash
# Script to set up Docker secrets for secure credential management

set -e

SECRETS_DIR="./secrets"

echo "🔐 Setting up Docker secrets..."

# Create secrets directory
mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"

# Function to create a secret file
create_secret() {
    local secret_name=$1
    local secret_file="$SECRETS_DIR/$secret_name.txt"
    local env_var=$2
    local prompt=$3

    if [ -f "$secret_file" ]; then
        echo "✓ Secret already exists: $secret_name"
        return
    fi

    # Try to get from environment variable
    if [ -n "${!env_var}" ]; then
        echo "${!env_var}" > "$secret_file"
        chmod 600 "$secret_file"
        echo "✓ Created secret from env var: $secret_name"
    else
        # Prompt user
        echo -n "$prompt: "
        read -s secret_value
        echo
        if [ -n "$secret_value" ]; then
            echo "$secret_value" > "$secret_file"
            chmod 600 "$secret_file"
            echo "✓ Created secret: $secret_name"
        else
            echo "⚠ Skipped: $secret_name (no value provided)"
        fi
    fi
}

# Create secrets
create_secret "postgres_password" "POSTGRES_PASSWORD" "Enter PostgreSQL password"
create_secret "postgres_user" "POSTGRES_USER" "Enter PostgreSQL user (default: coding_user)"
create_secret "mongodb_password" "MONGO_INITDB_ROOT_PASSWORD" "Enter MongoDB password"
create_secret "github_token" "GITHUB_TOKEN" "Enter GitHub personal access token"
create_secret "wandb_api_key" "WANDB_API_KEY" "Enter Weights & Biases API key (optional)"
create_secret "hf_token" "HF_TOKEN" "Enter Hugging Face token"

# Create .gitignore for secrets
cat > "$SECRETS_DIR/.gitignore" << 'EOL'
# Ignore all secret files
*.txt
!.gitignore
EOL

echo ""
echo "✅ Secrets setup complete!"
echo ""
echo "📁 Secrets stored in: $SECRETS_DIR/"
echo "🔒 File permissions: 600 (read/write for owner only)"
echo ""
echo "⚠️  IMPORTANT:"
echo "  1. Never commit files in $SECRETS_DIR/ to version control"
echo "  2. Backup secrets securely (use password manager or vault)"
echo "  3. Rotate secrets regularly"
echo "  4. Use docker-compose.secrets.yml for production deployments"
echo ""
echo "Usage:"
echo "  docker-compose -f docker-compose.yml -f docker-compose.secrets.yml up"
