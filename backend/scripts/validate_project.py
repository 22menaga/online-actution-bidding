from pathlib import Path
import ast,sys
ROOT=Path(__file__).resolve().parents[1]
required=['manage.py','requirements.txt','.env.example','README.md','config/settings.py','config/asgi.py','config/wsgi.py','config/urls.py','accounts/models.py','products/models.py','auctions/models.py','bidding/services.py','payments/services.py','notifications/services.py','messaging/models.py','audit/models.py','dashboard/views.py']
missing=[p for p in required if not (ROOT/p).exists()]
if missing: print('MISSING',missing); sys.exit(1)
excluded_dirs = {'venv', '.venv', '.git', '__pycache__'}
python_files = [
    path for path in ROOT.rglob('*.py')
    if not excluded_dirs.intersection(path.relative_to(ROOT).parts)
]
for p in python_files:
    ast.parse(p.read_text(encoding='utf-8'), filename=str(p))
print('Static validation: OK')
print('Python files:',len(python_files))
print('Migration files:',len(list(ROOT.glob('*/migrations/[0-9]*.py'))))
