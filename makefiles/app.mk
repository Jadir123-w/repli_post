.PHONY: app.test  		 \
		app.local 		 \
		app.add   		 \
		app.migrate		 \
		app.test		 \
		app.static

app.local: ## Ejecutar la aplicación en local
	python3 app/manage.py runserver

app.add: ## Crear una nueva aplicación
	@echo "Creando una nueva aplicación..."
	@echo "Nombre de la aplicación: "
	@read app_name; \
	python3 app/manage.py startapp $$app_name; \
	mv $$app_name app/

app.migrate: ## Realizar migraciones
	python3 app/manage.py makemigrations
	python3 app/manage.py migrate

app.test: ## Ejecutar pruebas
	python3 app/manage.py test

app.static: ## Recolectar archivos estáticos
	python3 app/manage.py collectstatic

app.rm.static: ## Eliminar archivos estáticos
	rm -rf app/static