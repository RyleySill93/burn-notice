# Azure SSO Authentication Flow

This guide provides an overview of the Azure AD login flow using MSAL, utilizing Redis to manage the authentication state.

## Overview

1. **User Initiates Login**: The user clicks a login button on the frontend, which redirects them to Azure AD.
2. **Azure AD Authentication**: User logs in on Azure AD and is redirected back to the frontend with an authorization code.
3. **Frontend Sends Code to Backend**: The frontend captures the authorization details via query params and sends it to the backend.
4. **Backend Exchanges Code for Tokens**: The backend uses the details as well as the initial code flow (retrieved from redis) to request access and refresh tokens from Azure AD.
5. **Token Handling**: The backend issues Burn Notice token in exchange.

## Components

- **Frontend**: Redirects users to Azure AD and handles the callback to capture the authorization code.
- **Backend**: Manages authentication state, exchanges authorization codes for tokens, and handles errors.
- **Redis**: Temporarily stores authentication code flow state (e.g., code verifier, nonce) using the `state` as the key.
This is necessary to validate with Azure AD.
