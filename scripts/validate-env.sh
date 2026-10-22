#!/bin/sh
set -eu
[ -f .env ] || { echo 'Missing .env; copy .env.example and set real values.' >&2; exit 1; }
command -v docker >/dev/null 2>&1 || { echo 'Docker with the Compose plugin is required.' >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo 'Python 3 is required for environment validation.' >&2; exit 1; }
python3 - <<'PY'
import json, subprocess, sys
result = subprocess.run(['docker', 'compose', 'config', '--format', 'json'], capture_output=True, text=True)
if result.returncode:
    sys.exit('Compose configuration could not be resolved. Check required .env variables and compose syntax.')
config = json.loads(result.stdout)
env = config['services']['api1'].get('environment', {})
db = config['services']['db'].get('environment', {})
values = {key: env.get(key, db.get(key, '')) for key in ('DJANGO_SECRET_KEY', 'MYSQL_PASSWORD', 'MYSQL_ROOT_PASSWORD')}
for name, value in values.items():
    if not value or value.startswith('REPLACE_') or 'change-me' in value.lower():
        sys.exit(f'{name} is unset or a placeholder')
if len(values['DJANGO_SECRET_KEY']) < 50:
    sys.exit('DJANGO_SECRET_KEY must contain at least 50 random characters')
if values['MYSQL_PASSWORD'] == values['MYSQL_ROOT_PASSWORD']:
    sys.exit('Application and root database passwords must differ')
if str(env.get('DEBUG', 'false')).lower() not in ('false', '0'):
    sys.exit('DEBUG must be false/0 for this deployment')
if str(env.get('ENABLE_DEMO_ACCOUNTS', 'false')).strip().lower() in ('1', 'true', 'yes', 'on'):
    sys.exit('ENABLE_DEMO_ACCOUNTS must be false for this deployment')
print('Environment and Compose configuration are valid. Secrets were not displayed.')
PY
