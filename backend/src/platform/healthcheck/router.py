from fastapi import APIRouter, Response
from sqlalchemy import text
from starlette import status

router = APIRouter()


@router.get('/api')
def status_get(response: Response) -> str:
    """
    Fast check to ensure API is running.
    🏴‍☠️ DO NOT CHANGE 🏴‍☠️
    This is used in a lot of infrastructure:
        nginx
        telemetry
        aws load balancer
        deploy scripts
    """
    message = '💸 Colonel Collateral is hungry... 💸'
    response.headers['Content-Type'] = 'text/html; charset=utf-8'

    return message


@router.get('/database')
def database_health_check(response: Response) -> str:
    """
    Fast check to ensure database connectivity.
    Returns status of read-only and regular database connections.
    """
    from src.network.database.session import ReadOnlySession, db

    lines = []
    is_healthy = True
    test_query = text('SELECT 1')

    try:
        db.session.execute(test_query)
        lines.append('✅ Regular DB is happy')
    except Exception as e:
        lines.append(f'❌ Regular DB is sad: {str(e)}')
        is_healthy = False

    try:
        with ReadOnlySession() as session:
            session.execute(test_query)
            lines.append('✅ Read-only DB is happy')
    except Exception as e:
        lines.append(f'❌ Read-only DB is sad: {str(e)}')
        is_healthy = False

    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    response.status_code = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return '<br>'.join(lines)
