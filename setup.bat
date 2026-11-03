@echo off 
call "..\venv\Scripts\activate.bat" 
python.exe -m pip install --upgrade pip 
pip install -r requirements.txt 
:: python manage.py collectstatic --noinput 
python manage.py makemigrations 
python manage.py migrate 
:: python manage.py load_mock_data 
