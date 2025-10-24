# CodeLupe Development Container
FROM mcr.microsoft.com/devcontainers/go:1.24

# Install additional tools
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    postgresql-client \
    redis-tools \
    curl \
    wget \
    git \
    build-essential \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip3 install --no-cache-dir \
    black \
    ruff \
    pytest \
    pytest-cov \
    mypy \
    pylint

# Install Go tools
RUN go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest \
    && go install golang.org/x/tools/gopls@latest \
    && go install github.com/go-delve/delve/cmd/dlv@latest

# Set up workspace
WORKDIR /workspace

# Create directories
RUN mkdir -p /workspace/bin /workspace/repos /workspace/logs

# Set environment variables
ENV GOPATH=/go
ENV PATH=$PATH:/go/bin
ENV GO111MODULE=on

# Non-root user
RUN useradd -m -s /bin/bash vscode \
    && usermod -aG sudo vscode \
    && echo "vscode ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

USER vscode
