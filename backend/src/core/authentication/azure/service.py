import msal

from src import settings
from src.common.nanoid import NanoIdType, generate_custom_nanoid
from src.core.authentication.azure.exceptions import AzureAuthFailure
from src.core.authentication.azure.utils import AzureSSOAuthCodeFlowEncoder
from src.core.user import UserNotFound, UserService
from src.network.cache.cache import Cache


class AzureSSOService:
    """
    Service class for handling Azure Single Sign-On (SSO) authentication flow.

    This class provides methods to initiate the authentication process with Azure,
    manage the exchange of authorization codes for tokens, and handle user identity
    retrieval. It leverages Microsoft Authentication Library (MSAL) for Python to
    interact with Azure Active Directory.

    Attributes:
        user_service (UserService): Service used to manage user identities.
        client_id (str): Azure client ID for the application.
        client_secret (str): Azure client secret for the application.
        scope (list): List of scopes required for authentication.
        redirect_uri (str): Redirect URI configured in Azure for the application.
        authority (str): Azure authority URL.
    """

    def __init__(self, user_service: UserService):
        self.user_service = user_service

        self.client_id = settings.AZURE_CLIENT_ID
        self.client_secret = settings.AZURE_CLIENT_SECRET
        self.redirect_uri = settings.AZURE_REDIRECT_URI

        self.scope = ['email', 'User.Read']
        self.authority = 'https://login.microsoftonline.com/common'

    @classmethod
    def factory(cls) -> 'AzureSSOService':
        """
        Factory method to create an instance of AzureSSOService with the default
        UserService.

        Returns:
            AzureSSOService: An instance of the AzureSSOService class.
        """
        return cls(user_service=UserService.factory())

    def initialize_authentication_flow(self) -> str:
        """
        Initializes the authentication flow with Azure and stores the flow state
        in cache for future retrieval during token acquisition.

        Returns:
            str: The authentication URI to redirect the user to for login.
        """
        # Generate the auth code flow object with the unique state
        state = generate_custom_nanoid(size=12)
        msal_app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=self.authority,
            client_credential=self.client_secret,
        )
        auth_code_flow = msal_app.initiate_auth_code_flow(
            scopes=self.scope,
            redirect_uri=self.redirect_uri,
            state=state,
        )

        # Encode auth_code_flow to base64 using the utility
        auth_code_flow_base64 = AzureSSOAuthCodeFlowEncoder.encode(auth_code_flow)

        # Stored in redis to be retrieved later for authentication
        key = f'azure-auth-flow:{state}'
        Cache.set(key, auth_code_flow_base64)
        # Expiration time (e.g., 5 minutes)
        Cache.expire(key, 300)

        return auth_code_flow['auth_uri']

    def authenticate_with_azure(self, auth_response: dict) -> NanoIdType:
        """
        Authenticates the user with Azure using the authorization code provided
        in the response and retrieves the user's email to fetch their user ID.

        Args:
            auth_response (dict): The response from Azure containing the authorization code.

        Returns:
            NanoIdType: The user ID associated with the authenticated email.

        Raises:
            AzureAuthFailure: If authentication fails or user is not found.
        """
        msal_app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=self.authority,
            client_credential=self.client_secret,
        )

        # Retrieve the state from the auth response
        state = auth_response['state']

        # Retrieve the stored values from Redis using the state
        key = f'azure-auth-flow:{state}'
        auth_flow_data = Cache.get(key)
        # Check if data exists
        if not auth_flow_data:
            raise AzureAuthFailure(message=f'Unknown azure auth flow attempt: {state}')

        # Decode auth_flow_data from base64 using the utility
        auth_code_flow = AzureSSOAuthCodeFlowEncoder.decode(auth_flow_data)

        # Directly acquire the token using the authorization code
        result = msal_app.acquire_token_by_auth_code_flow(
            auth_code_flow=auth_code_flow,
            auth_response=auth_response,
            scopes=self.scope,
        )

        if 'error' in result:
            raise AzureAuthFailure(
                message=f"Error during token acquisition: {result.get('error_description', 'Unknown error')}"
            )

        id_token_claims = result.get('id_token_claims')
        if not id_token_claims:
            raise AzureAuthFailure(message='ID token claims not found in Azure response')

        return self.get_user_email_from_claims(id_token_claims)

    def get_user_email_from_claims(self, user_info: dict) -> NanoIdType:
        """
        Extracts the user email from the ID token claims and retrieves the associated
        user ID from the identity service.

        Args:
            user_info (dict): The dictionary containing user claims from the ID token.

        Returns:
            NanoIdType: The user ID associated with the provided email.

        Raises:
            AzureAuthFailure: If the email is not found or the user does not exist.
        """
        email = user_info.get('email')
        if not email:
            raise AzureAuthFailure(message='Email not provided in Azure token')
        try:
            user = self.user_service.get_user_for_email(email)
            return user.id
        except UserNotFound:
            raise AzureAuthFailure(message=f'Unknown user: {email}')
