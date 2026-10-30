"""Keep integration tests away from developer data and live provider accounts."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_temporary = tempfile.TemporaryDirectory(prefix='facilityops-tests-', ignore_cleanup_errors=True)
os.environ['DATABASE_URL'] = 'sqlite:///' + (Path(_temporary.name) / 'tests.db').as_posix()
os.environ['ADMIN_USERNAME'] = 'admin'
os.environ['ADMIN_PASSWORD'] = 'facilityops123'
os.environ['JWT_SECRET_KEY'] = 'test-only-secret-not-for-production'
os.environ['AI_PROVIDER'] = 'mock'
