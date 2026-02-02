import base64
import json


class AzureSSOAuthCodeFlowEncoder:
    """
    Used to encode / decode auth code flows for azure SSO
    """

    @staticmethod
    def encode(data: dict) -> str:
        """
        Encodes a dictionary into a Base64 string after converting it to a JSON string.
        """
        try:
            json_data = json.dumps(data)
            base64_data = base64.b64encode(json_data.encode()).decode()
            return base64_data
        except (TypeError, ValueError) as e:
            raise ValueError(f'Failed to encode data to Base64: {str(e)}')

    @staticmethod
    def decode(base64_str: str) -> dict:
        """
        Decodes a Base64 string back into a dictionary after converting it from a JSON string.
        """
        try:
            json_data = base64.b64decode(base64_str.encode()).decode()
            data = json.loads(json_data)
            return data
        except (TypeError, ValueError, json.JSONDecodeError) as e:
            raise ValueError(f'Failed to decode Base64 string: {str(e)}')
