from src.common.exceptions import InternalException


class SMSFailedToSend(InternalException):
    """Raised when SMS fails to send through all available providers"""

    default_detail = 'SMS failed to send'
    default_code = 'sms_send_failure'
