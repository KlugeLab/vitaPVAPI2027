@echo off 
 
django-admin startapp %1 "apps\%1" 
 
powershell -Command "(Get-Content 'apps\%1\apps.py') -replace \"name = '%1'\", \"name = 'apps.%1'\" | Set-Content 'apps\%1\apps.py'" 
 
powershell -NoProfile -Command "$file='vitaPVAPI2027\settings.py'; $content=Get-Content $file -Raw; $app='apps.%1'; if ($content -notmatch [regex]::Escape($app)) { $replacement='INSTALLED_APPS = [' + [Environment]::NewLine + '    ''' + $app + ''','; $content=$content -replace 'INSTALLED_APPS\s*=\s*\[', $replacement; Set-Content $file $content -Encoding UTF8 }" 
