build-dev:
	docker buildx build --platform=linux/amd64 --tag mc-gateway:dev .
run:
	docker compose -f compose.yml up -d --force-recreate
stop:
	docker  compose -f compose.yml down
