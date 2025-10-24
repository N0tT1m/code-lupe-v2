#!/bin/bash
set -e

echo "🚀 Deploying CodeLupe Pipeline V2"
echo "===================================="

# Colors
GREEN='\033[0.32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Build images
echo -e "\n${YELLOW}Step 1: Building Docker images...${NC}"
docker build -f Dockerfile.pipeline -t codelupe-pipeline:latest .
docker build -f Dockerfile.qwen-5090 -t codelupe-qwen-5090:latest .
echo -e "${GREEN}✓ Images built${NC}"

# Step 2: Stop old pipeline
echo -e "\n${YELLOW}Step 2: Stopping old pipeline components...${NC}"
docker-compose stop downloader processor trainer || true
echo -e "${GREEN}✓ Old components stopped${NC}"

# Step 3: Start infrastructure
echo -e "\n${YELLOW}Step 3: Starting infrastructure (Redis, Elasticsearch, PostgreSQL)...${NC}"
docker-compose up -d redis elasticsearch postgres
echo "Waiting for services to be healthy..."
sleep 30
echo -e "${GREEN}✓ Infrastructure started${NC}"

# Step 4: Start crawler (if not running)
echo -e "\n${YELLOW}Step 4: Ensuring crawler is running...${NC}"
docker-compose up -d crawler
echo -e "${GREEN}✓ Crawler running${NC}"

# Step 5: Start crawler adapter
echo -e "\n${YELLOW}Step 5: Starting crawler adapter...${NC}"
docker-compose up -d crawler-adapter
echo -e "${GREEN}✓ Crawler adapter started${NC}"

# Step 6: Start pipeline
echo -e "\n${YELLOW}Step 6: Starting data pipeline...${NC}"
docker-compose up -d pipeline
echo -e "${GREEN}✓ Pipeline started${NC}"

# Step 7: Start trainer
echo -e "\n${YELLOW}Step 7: Starting Qwen trainer with Elasticsearch...${NC}"
docker-compose up -d qwen-5090-trainer-es
echo -e "${GREEN}✓ Trainer started${NC}"

# Step 8: Verify
echo -e "\n${YELLOW}Step 8: Verifying deployment...${NC}"

echo "Checking Redis..."
docker exec codelupe-redis redis-cli ping || echo "Redis not responding"

echo "Checking Elasticsearch..."
curl -s http://localhost:9200/_cluster/health | jq -r '.status' || echo "Elasticsearch not responding"

echo "Checking queue lengths..."
REPO_QUEUE=$(docker exec codelupe-redis redis-cli LLEN pipeline:repos)
FILE_QUEUE=$(docker exec codelupe-redis redis-cli LLEN pipeline:files)
echo "  - Repo queue: $REPO_QUEUE"
echo "  - File queue: $FILE_QUEUE"

echo -e "${GREEN}✓ Verification complete${NC}"

# Summary
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}🎉 Pipeline V2 Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"

echo -e "\nServices running:"
echo "  - Redis: localhost:6380"
echo "  - Elasticsearch: localhost:9200"
echo "  - Kibana: localhost:5601"
echo "  - Trainer metrics: localhost:8093"

echo -e "\nMonitoring:"
echo "  docker-compose logs -f pipeline"
echo "  docker-compose logs -f crawler-adapter"
echo "  docker-compose logs -f qwen-5090-trainer-es"

echo -e "\nRedis queues:"
echo "  docker exec -it codelupe-redis redis-cli"
echo "  LLEN pipeline:repos"
echo "  LLEN pipeline:files"

echo -e "\nElasticsearch:"
echo "  curl http://localhost:9200/codelupe-code/_count"

echo -e "\n${YELLOW}Note: It may take 5-10 minutes for repos to start flowing through the pipeline${NC}"
