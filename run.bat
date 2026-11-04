@echo off 
call "..\venv\Scripts\activate.bat" 
python manage.py check
python manage.py makemigrations organizacion identidad sync_sucursal
python manage.py migrate
python manage.py runserver 127.0.0.1:8002