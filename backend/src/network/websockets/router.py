from fastapi import APIRouter, Depends, WebSocketException
from starlette import status
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from src import settings
from src.core.authentication.services.authentication_service import (
    AuthenticationService,
    AuthTokenExpired,
    AuthTokenInvalid,
)
from src.network.websockets.domains import WebSocketMessageDomain
from src.network.websockets.service import WebSocketConnectionService

api_router = APIRouter()


def get_websocket_url(backend_origin):
    if backend_origin.startswith('https://'):
        return backend_origin.replace('https://', 'wss://', 1)
    elif backend_origin.startswith('http://'):
        return backend_origin.replace('http://', 'ws://', 1)
    else:
        raise ValueError('Invalid BACKEND_ORIGIN protocol')


# Get the WebSocket URL
websocket_url = get_websocket_url(settings.BACKEND_ORIGIN)

html = """
<!DOCTYPE html>
<html>
<head>
    <title>Chat</title>
</head>
<body>
    <h1>WebSocket Chat</h1>
    <form action="" onsubmit="sendMessage(event)">
        <input type="text" id="messageText" autocomplete="off"/>
        <button>Send</button>
    </form>
    <ul id='messages'>
    </ul>
    <script>
        // Function to set a cookie
        function setCookie(name, value, days) {{
            var expires = "";
            if (days) {{
                var date = new Date();
                date.setTime(date.getTime() + (days*24*60*60*1000));
                expires = "; expires=" + date.toUTCString();
            }}
            document.cookie = name + "=" + (value || "")  + expires + "; path=/";
        }}

        // Set the access token as a namespaced cookie
        var accessToken = JSON.parse(localStorage.getItem('SESSION')).accessToken;
        if (!accessToken) {{
            alert("No access token found. Please log in first.");
            // Redirect to login page or handle unauthenticated state
        }} else {{
            setCookie("ws_auth_token", accessToken, 1); // Set cookie to expire in 1 day
        }}

        var ws;
        var reconnectInterval = 1000; // Reconnect interval in ms

        function connect() {{
            ws = new WebSocket("{websocket_url}/ws");

            ws.onopen = function() {{
                console.log("Connected to WebSocket");
                reconnectInterval = 1000; // Reset the reconnect interval on successful connection
            }};

            ws.onmessage = function(event) {{
                var messages = document.getElementById('messages')
                var message = document.createElement('li')
                var content = document.createTextNode(event.data)
                message.appendChild(content)
                messages.appendChild(message)
            }};

            ws.onclose = function() {{
                console.log("WebSocket connection closed, attempting to reconnect...");
                setTimeout(connect, reconnectInterval);
                reconnectInterval = Math.min(reconnectInterval * 2, 30000); // Exponential backoff up to 30 seconds
            }};

            ws.onerror = function(error) {{
                console.error("WebSocket error: ", error);
                ws.close();
            }};
        }}

        function sendMessage(event) {{
            var input = document.getElementById("messageText");
            var message = input.value;
            var jsonMessage = JSON.stringify({{ message: message, channel_type: "CHAT"}}); // Ensure the message is JSON formatted
            ws.send(jsonMessage);
            input.value = '';
            event.preventDefault();
        }}

        // Connect to WebSocket server
        connect();
    </script>
</body>
</html>
""".format(websocket_url=websocket_url)


CONNECTION_CHANNEL_TYPE = 'CONNECT'


async def get_token_from_protocol(websocket: WebSocket):
    """
    This is a hack for getting the authentication token via wss cross origin
    """
    if 'sec-websocket-protocol' in websocket.headers:
        return websocket.headers['sec-websocket-protocol'].split(',')[1].strip()
    return None


@api_router.websocket('/ws')
async def websocket_endpoint(
    websocket: WebSocket,
    authn_service: AuthenticationService = Depends(AuthenticationService.factory),
):
    """
    Accepts and authenticates websocket traffic
    """
    unvalidated_token = await get_token_from_protocol(websocket)

    if not unvalidated_token:
        await websocket.close(code=1008, reason='No token provided')
        return

    # First accept the traffic before
    await websocket.accept(subprotocol='message')

    try:
        token = authn_service.verify_jwt_token(unvalidated_token)
    except AuthTokenExpired:
        # This should be retried after a refresh
        reason = 'Expired access token'
        response = WebSocketMessageDomain(
            code=status.HTTP_401_UNAUTHORIZED,
            user_id=None,
            channel_type=CONNECTION_CHANNEL_TYPE,
            payload={'message': reason},
        )
        await websocket.send_json(response.to_dict())
        await websocket.close(code=status.WS_1001_GOING_AWAY, reason=reason)
        return
    except AuthTokenInvalid:
        reason = 'Invalid access token'
        response = WebSocketMessageDomain(
            code=status.HTTP_403_FORBIDDEN,
            user_id=None,
            channel_type=CONNECTION_CHANNEL_TYPE,
            payload={'message': reason},
        )
        await websocket.send_json(response.to_dict())
        await websocket.close(code=status.WS_1001_GOING_AWAY, reason=reason)
        return
    except Exception:
        reason = 'Unknown exception occurred'
        response = WebSocketMessageDomain(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            user_id=None,
            channel_type=CONNECTION_CHANNEL_TYPE,
            payload={'message': reason},
        )
        await websocket.send_json(response.to_dict())
        await websocket.close(code=status.WS_1001_GOING_AWAY, reason=reason)
        return

    user_id = token.sub
    websocket_conn_service = WebSocketConnectionService.factory()

    connection_id = await websocket_conn_service.connect(user_id=user_id, websocket=websocket)
    try:
        while True:
            # This is just sending the response back which is useful for testing
            # but unnecessary to have live
            data = await websocket.receive_json()
            message = WebSocketMessageDomain(
                user_id=user_id,
                channel_type=data['channel_type'],
                payload=data,
            )
            await websocket_conn_service.publish(message)
    except WebSocketDisconnect:
        await websocket_conn_service.disconnect(user_id=user_id, connection_id=connection_id)
    except WebSocketException as e:
        raise e
    finally:
        # Ensure that the WebSocket is closed only once
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket_conn_service.disconnect(
                user_id=user_id,
                connection_id=connection_id,
            )
            await websocket.close()
