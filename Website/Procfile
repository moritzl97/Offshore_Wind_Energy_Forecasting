# Azure App Service startup command
# Set this as the startup command in Azure Portal under Configuration > General Settings:
#
#   gunicorn --bind=0.0.0.0 --timeout 600 app:app
#
# Or create a Procfile (Heroku-style) which Azure also supports:
web: gunicorn --bind=0.0.0.0:8000 --timeout 600 app:app
