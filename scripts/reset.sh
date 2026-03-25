#!/bin/bash
echo "🧹 Wiping distributed databases and stopping containers..."
docker-compose down -v --remove-orphans

echo "🗑️ Clearing local JSON storage..."
rm -rf node_data/node*/*

echo "🚀 Rebuilding and launching a pristine cluster..."
docker-compose up -d --build

echo "✅ Cluster is up! Run 'docker-compose logs -f' to watch the process."