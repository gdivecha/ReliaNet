.PHONY: reset up down logs chaos

# Run the reset script
reset:
	@./scripts/reset.sh

# Shortcut to boot the cluster
up:
	docker-compose up -d --build

# Shortcut to wipe the cluster
down:
	docker-compose down -v --remove-orphans

# Shortcut to watch logs
logs:
	docker-compose logs -f

# Shotrcut to remove local storage
discard:
	rm -rf node_data/node*/*

# Shortcut to deactivate node 3
stop3:
	docker-compose stop node3

# Shortcut to activate node 3
start3:
	docker-compose start node3