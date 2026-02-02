import os
import sys
import tempfile
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# ruff: noqa: E402
from src import settings

db_user = settings.DB_NAME

# These commands are run before psql shell to set context
psqlrc_commands = f"""
SET auditcontext.event_id = '{uuid.uuid4()}';
SET auditcontext.user_id = 'user-engineer'; 
"""
temp_psqlrc = tempfile.NamedTemporaryFile(mode='w+', delete=False)
temp_psqlrc.write(psqlrc_commands)
temp_psqlrc.close()

os.environ['PSQLRC'] = temp_psqlrc.name
os.environ['PGPASSWORD'] = settings.DB_PASSWORD

dbshell_command = f'psql -U {settings.DB_USER} -d {settings.DB_NAME} -h {settings.DB_HOST} -p {settings.DB_PORT}'
os.system(dbshell_command)
# Cleanup temp file manually
os.remove(temp_psqlrc.name)
