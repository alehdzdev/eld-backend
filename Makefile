up:
	docker compose -f docker-compose.yml up -d

stop:
	docker compose -f docker-compose.yml stop

build:
	docker compose -f docker-compose.yml build

restart:
	docker compose -f docker-compose.yml stop && docker compose -f docker-compose.yml up -d

down:
	docker compose -f docker-compose.yml down -v

migrations:
	docker compose -f docker-compose.yml exec web /bin/sh -c "python manage.py makemigrations"

migrate:
	docker compose -f docker-compose.yml exec web /bin/sh -c "python manage.py migrate"
    
logs:
	docker compose -f docker-compose.yml logs -f web

messages:
	docker compose -f docker-compose.yml exec web /bin/sh -c "python manage.py makemessages -l es"

compilemessages:
	docker compose -f docker-compose.yml exec web /bin/sh -c "python manage.py compilemessages"

shell:
	docker compose -f docker-compose.yml exec web python manage.py shell_plus
