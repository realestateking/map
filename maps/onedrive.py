"""
Microsoft OneDrive Integration for Property Mapper

This module handles integration with Microsoft OneDrive for storing and retrieving
large files like shapefiles that exceed local storage limitations.
"""

import os
import json
import time
import logging
import urllib.parse
from urllib.parse import urlencode
import requests
from django.conf import settings
from django.urls import reverse
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponse

# OneDrive API URLs
AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
GRAPH_URL = "https://graph.microsoft.com/v1.0"

# Access scopes required for OneDrive
SCOPES = [
    "Files.ReadWrite",
    "Files.ReadWrite.All",
    "offline_access",  # For refresh token
]

class OneDriveClient:
    """Client for interacting with Microsoft OneDrive API"""
    
    def __init__(self):
        """Initialize the OneDrive client with settings"""
        self.client_id = settings.ONEDRIVE_CLIENT_ID
        self.client_secret = settings.ONEDRIVE_CLIENT_SECRET
        self.redirect_uri = settings.ONEDRIVE_REDIRECT_URI
        self.token = self._load_token()
    
    def _load_token(self):
        """Load token from storage or return None"""
        try:
            with open('onedrive_token.json', 'r') as f:
                token_data = json.load(f)
                # Check if token is expired
                if token_data.get('expires_at', 0) < time.time():
                    # Try to refresh the token
                    return self._refresh_token(token_data.get('refresh_token'))
                return token_data
        except (FileNotFoundError, json.JSONDecodeError):
            return None
    
    def _save_token(self, token_data):
        """Save token to storage"""
        # Add expiration time
        if 'expires_in' in token_data:
            token_data['expires_at'] = time.time() + int(token_data['expires_in']) - 300  # 5 min buffer
        
        try:
            with open('onedrive_token.json', 'w') as f:
                json.dump(token_data, f)
            return token_data
        except Exception as e:
            print(f"Error saving token: {e}")
            return token_data
    
    def _refresh_token(self, refresh_token):
        """Refresh an expired token"""
        if not refresh_token:
            return None
            
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
        }
        
        try:
            response = requests.post(TOKEN_URL, data=data)
            if response.status_code == 200:
                token_data = response.json()
                return self._save_token(token_data)
        except Exception as e:
            print(f"Error refreshing token: {e}")
        
        return None
    
    def get_auth_url(self, state=None):
        """Generate authorization URL for OneDrive"""
        logger = logging.getLogger(__name__)
        
        # Check if required settings are configured
        if not self.client_id:
            logger.error("ONEDRIVE_CLIENT_ID is not configured or empty")
            return "#error-no-client-id"
            
        if not self.redirect_uri:
            logger.error("ONEDRIVE_REDIRECT_URI is not configured or empty")
            return "#error-no-redirect-uri"
        
        # Generate a secure state parameter if one wasn't provided
        import random
        import string
        if not state:
            state = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        
        params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': self.redirect_uri,
            'scope': ' '.join(SCOPES),
            'response_mode': 'query',
            'state': state,
        }
        
        auth_url = f"{AUTH_URL}?{urlencode(params)}"
        
        # Log the URL (without exposing client_id)
        redacted_params = params.copy()
        redacted_params['client_id'] = 'CLIENT_ID_REDACTED'
        redacted_url = f"{AUTH_URL}?{urlencode(redacted_params)}"
        logger.info(f"Generated OneDrive auth URL: {redacted_url}")
        logger.info(f"Using redirect URI: {self.redirect_uri}")
        
        return auth_url
    
    def handle_auth_response(self, code):
        """Handle authorization response and get access token"""
        logger = logging.getLogger(__name__)
        
        # Validate input data
        if not code:
            logger.error("Authorization code is missing")
            return False
            
        if not self.client_id or not self.client_secret:
            logger.error("OneDrive client credentials are not properly configured")
            return False
            
        if not self.redirect_uri:
            logger.error("OneDrive redirect URI is not configured")
            return False
        
        # Log what we're trying to do
        logger.info(f"Exchanging authorization code for access token using redirect URI: {self.redirect_uri}")
        
        # Add logging of credential lengths for debugging without exposing secrets
        client_id_len = len(self.client_id) if self.client_id else 0
        client_secret_len = len(self.client_secret) if self.client_secret else 0
        logger.info(f"Client ID length: {client_id_len}, Client Secret length: {client_secret_len}")
        logger.info(f"Client ID first/last 4 chars: {self.client_id[:4]}...{self.client_id[-4:] if len(self.client_id) > 8 else ''}")
        
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': code,
            'redirect_uri': self.redirect_uri,
            'grant_type': 'authorization_code',
        }
        
        # Create a copy with secrets hidden for logging
        debug_data = data.copy()
        if debug_data.get('client_secret'):
            debug_data['client_secret'] = f"***SECRET***({len(debug_data['client_secret'])} chars)"
        if debug_data.get('code'):
            debug_data['code'] = f"***CODE***({len(debug_data['code'])} chars)"
        logger.info(f"Token request data: {debug_data}")
        
        try:
            logger.info(f"Making token request to {TOKEN_URL}")
            
            # Make the token request
            response = requests.post(TOKEN_URL, data=data)
            
            # Log the response status and details
            logger.info(f"Token response status: {response.status_code}")
            
            if response.status_code == 200:
                logger.info("Successfully obtained access token")
                token_data = response.json()
                
                # Save token and set in client
                self.token = self._save_token(token_data)
                
                # Log a redacted version of the token for debugging
                redacted_token = {
                    k: (v[:10] + '...' if k in ('access_token', 'refresh_token') and isinstance(v, str) else v) 
                    for k, v in token_data.items()
                }
                logger.info(f"Token data (redacted): {redacted_token}")
                
                return True
            else:
                # If not successful, log the error
                logger.error(f"Failed to get token. Status: {response.status_code}")
                try:
                    error_info = response.json()
                    logger.error(f"Error details: {error_info}")
                except:
                    logger.error(f"Error response text: {response.text}")
        except Exception as e:
            # Log any exceptions
            logger.error(f"Exception when getting token: {e}")
            print(f"Error getting token: {e}")
        
        return False
    
    def is_authenticated(self):
        """Check if client is authenticated"""
        return self.token is not None and 'access_token' in self.token
    
    def _get_headers(self):
        """Get authorization headers for API requests"""
        if not self.is_authenticated():
            return None
        
        return {
            'Authorization': f"Bearer {self.token['access_token']}",
            'Content-Type': 'application/json',
        }
    
    def upload_file(self, file_path, destination_path=None):
        """Upload a file to OneDrive
        
        Args:
            file_path: Path to the file to upload
            destination_path: Path in OneDrive where to store the file
            
        Returns:
            dict: The OneDrive file item or None if failed
        """
        if not self.is_authenticated():
            return None
        
        file_name = os.path.basename(file_path)
        destination_path = destination_path or '/property_mapper_uploads'
        
        # Check if destination folder exists, create if not
        folder = self._ensure_folder(destination_path)
        if not folder:
            return None
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        if file_size <= 4 * 1024 * 1024:  # 4 MB
            # Use simple upload for small files
            return self._simple_upload(file_path, folder['id'], file_name)
        else:
            # Use resumable upload for large files
            return self._resumable_upload(file_path, folder['id'], file_name)
    
    def _ensure_folder(self, folder_path):
        """Ensure the folder exists in OneDrive, create if not"""
        headers = self._get_headers()
        if not headers:
            return None
        
        # Remove leading slash if present
        if folder_path.startswith('/'):
            folder_path = folder_path[1:]
        
        # Split path into parts
        parts = folder_path.split('/')
        current_path = ''
        parent_id = 'root'
        
        for part in parts:
            if not part:
                continue
                
            current_path += '/' + part
            
            # Check if folder exists
            url = f"{GRAPH_URL}/me/drive/root:{current_path}"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                folder = response.json()
                parent_id = folder['id']
            else:
                # Create folder
                url = f"{GRAPH_URL}/me/drive/items/{parent_id}/children"
                data = {
                    'name': part,
                    'folder': {},
                    '@microsoft.graph.conflictBehavior': 'rename'
                }
                
                response = requests.post(url, headers=headers, json=data)
                
                if response.status_code in (201, 200):
                    folder = response.json()
                    parent_id = folder['id']
                else:
                    print(f"Failed to create folder {part}: {response.text}")
                    return None
        
        return {
            'id': parent_id,
            'path': current_path
        }
    
    def _simple_upload(self, file_path, parent_id, file_name):
        """Upload a small file (< 4MB) to OneDrive"""
        headers = self._get_headers()
        if not headers:
            return None
        
        # Remove content-type header for file upload
        upload_headers = headers.copy()
        upload_headers.pop('Content-Type', None)
        
        url = f"{GRAPH_URL}/me/drive/items/{parent_id}:/{file_name}:/content"
        
        with open(file_path, 'rb') as f:
            response = requests.put(url, headers=upload_headers, data=f)
            
            if response.status_code in (200, 201):
                return response.json()
            else:
                print(f"Failed to upload file: {response.text}")
                return None
    
    def _resumable_upload(self, file_path, parent_id, file_name):
        """Upload a large file using resumable upload session"""
        headers = self._get_headers()
        if not headers:
            return None
        
        # Create upload session
        url = f"{GRAPH_URL}/me/drive/items/{parent_id}:/{file_name}:/createUploadSession"
        data = {
            "item": {
                "@microsoft.graph.conflictBehavior": "rename",
            }
        }
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code != 200:
            print(f"Failed to create upload session: {response.text}")
            return None
        
        upload_session = response.json()
        upload_url = upload_session['uploadUrl']
        
        # Upload file in chunks
        chunk_size = 10 * 1024 * 1024  # 10 MB chunks
        file_size = os.path.getsize(file_path)
        
        with open(file_path, 'rb') as f:
            offset = 0
            while offset < file_size:
                chunk = f.read(chunk_size)
                chunk_len = len(chunk)
                
                # Prepare headers for chunk upload
                chunk_headers = {
                    'Content-Length': str(chunk_len),
                    'Content-Range': f'bytes {offset}-{offset + chunk_len - 1}/{file_size}'
                }
                
                # Upload chunk
                chunk_response = requests.put(upload_url, headers=chunk_headers, data=chunk)
                
                if chunk_response.status_code in (200, 201, 202):
                    if chunk_response.status_code in (200, 201):
                        # Upload completed
                        return chunk_response.json()
                else:
                    print(f"Failed to upload chunk: {chunk_response.text}")
                    return None
                
                offset += chunk_len
        
        return None
    
    def get_download_url(self, file_id):
        """Get a download URL for a file in OneDrive"""
        headers = self._get_headers()
        if not headers:
            return None
        
        url = f"{GRAPH_URL}/me/drive/items/{file_id}"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            file_data = response.json()
            return file_data.get('@microsoft.graph.downloadUrl')
        
        return None

def get_onedrive_client():
    """Helper function to get an instance of OneDriveClient"""
    client = OneDriveClient()
    # Print settings for debugging
    print(f"OneDrive redirect URI: {settings.ONEDRIVE_REDIRECT_URI}")
    return client
    
def check_onedrive_auth(request):
    """View to check OneDrive authentication status and manage it directly"""
    from django.shortcuts import render
    import logging
    logger = logging.getLogger(__name__)
    
    client = get_onedrive_client()
    is_authenticated = client.is_authenticated()
    
    logger.info(f"OneDrive Auth Check - Is authenticated: {is_authenticated}")
    print(f"OneDrive Auth Check - Is authenticated: {is_authenticated}")
    
    # Get additional debugging information
    from django.conf import settings
    import os
    
    debug_info = {
        'ONEDRIVE_CLIENT_ID': settings.ONEDRIVE_CLIENT_ID[:5] + '...' if settings.ONEDRIVE_CLIENT_ID else 'Not set',
        'ONEDRIVE_REDIRECT_URI': settings.ONEDRIVE_REDIRECT_URI,
        'BASE_URL': settings.BASE_URL,
        'ALLOWED_HOSTS': settings.ALLOWED_HOSTS,
        'CSRF_TRUSTED_ORIGINS': settings.CSRF_TRUSTED_ORIGINS,
        'HTTP_HOST': request.META.get('HTTP_HOST', 'Unknown'),
        'REQUEST_METHOD': request.method,
        'PATH_INFO': request.path_info,
        'FULL_PATH': request.get_full_path(),
        'COOKIES_ENABLED': 'sessionid' in request.COOKIES,
        'SESSION_EXISTS': bool(request.session.session_key),
        'TOKEN_FILE_EXISTS': os.path.exists('onedrive_token.json'),
    }
    
    print("OneDrive Debug Info:")
    for key, value in debug_info.items():
        print(f"  {key}: {value}")
    
    if request.method == 'POST' and 'clear_auth' in request.POST:
        # Clear OneDrive authentication
        try:
            import os
            if os.path.exists('onedrive_token.json'):
                os.remove('onedrive_token.json')
                logger.info("OneDrive Auth Check - Cleared token file")
                print("OneDrive Auth Check - Cleared token file")
                
            # Also clear from session
            if 'pending_layer_data' in request.session:
                request.session.pop('pending_layer_data', None)
                request.session.modified = True
                logger.info("OneDrive Auth Check - Cleared session data")
                print("OneDrive Auth Check - Cleared session data")
                
            return render(request, 'maps/onedrive_auth_check.html', {
                'is_authenticated': False,
                'message': 'Authentication data successfully cleared.',
                'auth_url': client.get_auth_url(),
                'debug_info': debug_info,
            })
        except Exception as e:
            logger.error(f"OneDrive Auth Check - Error clearing auth: {e}")
            print(f"OneDrive Auth Check - Error clearing auth: {e}")
            return render(request, 'maps/onedrive_auth_check.html', {
                'is_authenticated': is_authenticated,
                'error': f"Error clearing authentication: {str(e)}",
                'auth_url': client.get_auth_url(),
                'debug_info': debug_info,
            })
    
    # Create auth URL and print it for debugging
    auth_url = client.get_auth_url()
    print(f"OneDrive Auth URL: {auth_url}")
    
    return render(request, 'maps/onedrive_auth_check.html', {
        'is_authenticated': is_authenticated,
        'auth_url': auth_url,
        'debug_info': debug_info,
    })

def authenticate_onedrive(request):
    """View to initiate OneDrive authentication"""
    from django.conf import settings
    import logging
    logger = logging.getLogger(__name__)
    
    # Log OneDrive configuration for debugging
    logger.info(f"OneDrive Auth - Client ID: {settings.ONEDRIVE_CLIENT_ID[:5]}... (truncated)")
    logger.info(f"OneDrive Auth - Redirect URI: {settings.ONEDRIVE_REDIRECT_URI}")
    print(f"OneDrive Auth - Redirect URI: {settings.ONEDRIVE_REDIRECT_URI}")
    
    client = get_onedrive_client()
    
    # Store the current page in session to redirect back after auth
    if 'HTTP_REFERER' in request.META:
        request.session['onedrive_redirect_after_auth'] = request.META['HTTP_REFERER']
        logger.info(f"OneDrive Auth - Will redirect back to: {request.META['HTTP_REFERER']}")
    
    # Store any pending upload data
    pending_layer_data = request.session.get('pending_layer_data')
    if pending_layer_data:
        logger.info("OneDrive Auth - Found pending layer data in session")
    
    # Generate and log the auth URL
    auth_url = client.get_auth_url()
    logger.info(f"OneDrive Auth - Generated auth URL: {auth_url}")
    print(f"OneDrive Auth - Full auth URL: {auth_url}")
    
    # Create a simple HTML page with explicit instructions for Replit environment
    return HttpResponse(f"""
    <html>
    <head>
        <title>Microsoft OneDrive Authentication</title>
        <style>
            body {{ 
                font-family: Arial, sans-serif; 
                text-align: center; 
                padding: 40px;
                background-color: #f5f5f5;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                background: white;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            h2 {{ color: #0078d4; margin-bottom: 20px; }}
            .btn {{
                display: inline-block;
                background-color: #0078d4;
                color: white;
                text-decoration: none;
                padding: 12px 24px;
                border-radius: 4px;
                font-weight: bold;
                margin: 20px 0;
                transition: background-color 0.3s;
            }}
            .btn:hover {{ background-color: #0063b1; color: white; }}
            .alert {{
                background-color: #f0f7ff;
                border-left: 4px solid #0078d4;
                padding: 15px;
                margin: 20px 0;
                text-align: left;
            }}
            .steps {{
                text-align: left;
                margin: 20px 0;
            }}
            .steps li {{
                margin-bottom: 10px;
            }}
            code {{
                background: #f5f5f5;
                padding: 2px 5px;
                border-radius: 3px;
                font-family: monospace;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Microsoft OneDrive Authentication</h2>
            
            <div class="alert">
                <p><strong>Important:</strong> You need to authenticate with Microsoft to upload large files to OneDrive.</p>
            </div>
            
            <h3>Please follow these steps:</h3>
            <ol class="steps">
                <li>Click the button below to open Microsoft's login page in a <strong>new tab</strong></li>
                <li>Login with your Microsoft account and authorize the application</li>
                <li>After successful authorization, close that tab and return to this app</li>
                <li>Once authenticated, you can upload large files to OneDrive</li>
            </ol>
            
            <a href="{auth_url}" class="btn" target="_blank">Login with Microsoft</a>
            
            <p>Having trouble? Try <a href="/onedrive-check/">checking your authentication status</a> after login.</p>
        </div>
    </body>
    </html>
    """)

def onedrive_debug(request):
    """Direct debugging view for OneDrive authentication"""
    from django.http import HttpResponse
    from django.conf import settings
    import json
    
    # Get client info for debugging
    client = get_onedrive_client()
    
    # Return a JSON response with all debugging info
    debug_info = {
        'ONEDRIVE_CLIENT_ID': settings.ONEDRIVE_CLIENT_ID[:5] + '...' if settings.ONEDRIVE_CLIENT_ID else 'Not set',
        'ONEDRIVE_REDIRECT_URI': settings.ONEDRIVE_REDIRECT_URI,
        'BASE_URL': settings.BASE_URL,
        'ALLOWED_HOSTS': settings.ALLOWED_HOSTS,
        'CSRF_TRUSTED_ORIGINS': settings.CSRF_TRUSTED_ORIGINS,
        'HTTP_HOST': request.META.get('HTTP_HOST', 'Unknown'),
        'REQUEST_METHOD': request.method,
        'PATH_INFO': request.path_info,
        'FULL_PATH': request.get_full_path(),
        'AUTH_URL': client.get_auth_url(),
        'IS_AUTHENTICATED': client.is_authenticated(),
    }
    
    print("ONEDRIVE DEBUG INFO:")
    for key, value in debug_info.items():
        print(f"  {key}: {value}")
    
    # Create a nicely formatted HTML response with the debug info
    html_response = """
    <html>
    <head>
        <title>OneDrive Debug Info</title>
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; padding: 20px; max-width: 800px; margin: 0 auto; }
            h1 { color: #0078d4; }
            .debug-info { background: #f5f5f5; padding: 15px; border-radius: 4px; margin: 20px 0; }
            .debug-item { margin-bottom: 10px; }
            .key { font-weight: bold; color: #333; }
            .value { font-family: monospace; word-break: break-all; }
            .auth-btn { 
                display: inline-block; background: #0078d4; color: white; padding: 10px 15px; 
                text-decoration: none; border-radius: 4px; margin-top: 20px; 
            }
            .auth-btn:hover { background: #0063b1; }
        </style>
    </head>
    <body>
        <h1>OneDrive Debug Information</h1>
        <p>This page shows detailed debugging information about the OneDrive authentication setup.</p>
        
        <div class="debug-info">
    """
    
    # Add each debug item to the response
    for key, value in debug_info.items():
        html_response += f"""
            <div class="debug-item">
                <span class="key">{key}:</span> 
                <div class="value">{value}</div>
            </div>
        """
    
    # Add a callback URL test section
    callback_url = settings.ONEDRIVE_REDIRECT_URI
    
    # Continue with the rest of the HTML
    html_response += f"""
        </div>
        
        <h2>Authentication Test</h2>
        <div class="debug-info">
            <p>Click the button below to try authenticating with Microsoft OneDrive:</p>
            <a href="{debug_info['AUTH_URL']}" class="auth-btn" target="_blank">Try Authentication</a>
        </div>
        
        <h2>Callback Test</h2>
        <div class="debug-info">
            <p>This section tests if your callback URL is correctly configured and accessible:</p>
            
            <div class="debug-item">
                <span class="key">Callback URL:</span>
                <div class="value">{callback_url}</div>
            </div>
            
            <p>Click the button below to test if the callback URL is accessible:</p>
            <a href="{callback_url}?test=true&debug=true" class="auth-btn" style="background: #28a745;">Test Callback URL</a>
            <p class="mt-2"><small>This will open the callback URL with test parameters to check if it's accessible.</small></p>
        </div>
        
        <p><a href="/onedrive-check/">Back to Authentication Status</a></p>
    </body>
    </html>
    """
    
    return HttpResponse(html_response)

def onedrive_callback(request):
    """Handle callback from OneDrive authentication"""
    import logging
    logger = logging.getLogger(__name__)
    
    from django.urls import reverse
    from django.shortcuts import redirect
    from django.contrib import messages
    from django.http import HttpResponse
    from django.conf import settings
    
    # Log the callback receipt with full URL for debugging
    full_path = request.get_full_path()
    request_meta = request.META.get('HTTP_HOST', 'unknown')
    server_name = request.META.get('SERVER_NAME', 'unknown')
    remote_addr = request.META.get('REMOTE_ADDR', 'unknown')
    
    logger.info(f"Received OneDrive callback. Full path: {full_path} - Host: {request_meta}")
    logger.info(f"OneDrive callback server info - SERVER_NAME: {server_name}, REMOTE_ADDR: {remote_addr}")
    print(f"Received OneDrive callback. Full path: {full_path} - Host: {request_meta}")
    print(f"OneDrive callback server info - SERVER_NAME: {server_name}, REMOTE_ADDR: {remote_addr}")
    
    # Log all query parameters for debugging
    query_params = request.GET.dict()
    logger.info(f"OneDrive callback query params: {query_params}")
    print(f"OneDrive callback query params: {query_params}")
    
    # Log important configuration values
    logger.info(f"OneDrive callback configuration - REDIRECT_URI: {settings.ONEDRIVE_REDIRECT_URI}")
    logger.info(f"OneDrive callback configuration - BASE_URL: {settings.BASE_URL}")
    logger.info(f"OneDrive callback configuration - ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")
    print(f"OneDrive callback configuration - REDIRECT_URI: {settings.ONEDRIVE_REDIRECT_URI}")
    
    code = request.GET.get('code')
    error = request.GET.get('error')
    error_description = request.GET.get('error_description')
    state = request.GET.get('state')
    
    logger.info(f"OneDrive callback received - Code present: {bool(code)}, Error: {error or 'None'}")
    
    # If there's an error parameter, show detailed error information
    if error:
        error_msg = f"OneDrive authentication error: {error}"
        if error_description:
            error_msg += f" - {error_description}"
        
        logger.error(error_msg)
        print(error_msg)
        
        # For debugging, sometimes it's better to show the error on a page instead of redirecting
        if 'debug' in request.GET:
            html_response = f"""
            <html>
            <head>
                <title>OneDrive Authentication Error</title>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; padding: 20px; max-width: 800px; margin: 0 auto; }}
                    h1 {{ color: #d40000; }}
                    .error-info {{ background: #fff5f5; padding: 15px; border-radius: 4px; margin: 20px 0; border-left: 4px solid #d40000; }}
                    pre {{ background: #f5f5f5; padding: 10px; border-radius: 4px; overflow-x: auto; }}
                    .back-link {{ display: inline-block; margin-top: 20px; color: #0078d4; text-decoration: none; }}
                    .back-link:hover {{ text-decoration: underline; }}
                </style>
            </head>
            <body>
                <h1>OneDrive Authentication Error</h1>
                <div class="error-info">
                    <p><strong>Error:</strong> {error}</p>
                    {f'<p><strong>Description:</strong> {error_description}</p>' if error_description else ''}
                    <p><strong>Request Path:</strong> {full_path}</p>
                    <p><strong>State Parameter:</strong> {state or 'Not provided'}</p>
                </div>
                
                <h2>Debug Information</h2>
                <pre>
Redirect URI: {settings.ONEDRIVE_REDIRECT_URI}
HTTP Host: {request_meta}
Server Name: {server_name}
Remote Address: {remote_addr}
Allowed Hosts: {settings.ALLOWED_HOSTS}
CSRF Trusted Origins: {settings.CSRF_TRUSTED_ORIGINS}
                </pre>
                
                <a href="/onedrive-debug/" class="back-link">Back to Debug Page</a>
            </body>
            </html>
            """
            return HttpResponse(html_response)
        
        messages.error(request, error_msg)
        return redirect('admin_dashboard')
    
    # If no code is provided, that's a problem
    if not code:
        error_msg = "No authorization code received from Microsoft. Authentication failed."
        logger.error(error_msg)
        print(error_msg)
        
        messages.error(request, error_msg)
        return redirect('admin_dashboard')
    
    # Log code length for debugging (without revealing the actual code)
    logger.info(f"Auth code received with length: {len(code)}")
    
    # Process the authorization code
    client = get_onedrive_client()
    success = client.handle_auth_response(code)
    
    if not success:
        error_msg = "Failed to exchange authorization code for access token. Please try again."
        logger.error(error_msg)
        messages.error(request, error_msg)
        return redirect('admin_dashboard')
    
    # Check if we have a pending layer upload
    pending_layer_data = request.session.get('pending_layer_data')
    if pending_layer_data:
        # We need to continue a layer upload that was interrupted by auth
        try:
            layer_name = pending_layer_data.get('layer_name', 'your layer')
            file_name = pending_layer_data.get('file_name', 'your file')
            file_size = pending_layer_data.get('file_size', 0)
            
            if file_size > 0:
                file_size_str = f" ({file_size/1024/1024:.1f} MB)"
            else:
                file_size_str = ""
                
            messages.success(
                request, 
                f"OneDrive authentication successful! You can now upload '{file_name}'{file_size_str} " +
                f"for your '{layer_name}' layer. Please continue with your upload."
            )
            
            # Keep the pending data in session for now, it will be used when the user retries the upload
            # We'll update a flag to indicate authentication is complete
            pending_layer_data['onedrive_authenticated'] = True
            request.session['pending_layer_data'] = pending_layer_data
            request.session.modified = True
            
            # Log the updated status
            logging.getLogger(__name__).info(f"OneDrive callback - Updated pending layer data with auth status: {pending_layer_data}")
        except Exception as e:
            # Log any errors that occur
            logging.getLogger(__name__).error(f"OneDrive callback - Error processing pending layer data: {e}")
            messages.success(request, "OneDrive authentication successful. Please retry your upload.")
            request.session.pop('pending_layer_data', None)
            
            # Redirect to add map layer form
            return redirect('add_map_layer')
    
    # Create a confirmation page with clear instructions instead of immediate redirect
    redirect_url = request.session.get('onedrive_redirect_after_auth', reverse('admin_dashboard'))
    request.session.pop('onedrive_redirect_after_auth', None)
    
    # Show a confirmation page with instructions to return to the upload form
    response = HttpResponse("""
    <html>
    <head>
        <title>OneDrive Authentication Complete</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f8f9fa;
                color: #333;
                text-align: center;
            }
            .container {
                max-width: 600px;
                margin: 0 auto;
                background: white;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #0078d4;
                margin-top: 0;
            }
            .success-icon {
                color: #107C10;
                font-size: 48px;
                margin-bottom: 20px;
            }
            .btn {
                display: inline-block;
                background-color: #0078d4;
                color: white;
                padding: 10px 20px;
                text-decoration: none;
                border-radius: 4px;
                font-weight: bold;
                margin-top: 20px;
            }
            .btn:hover {
                background-color: #0063b1;
            }
            .steps {
                text-align: left;
                margin: 20px 0;
                padding-left: 20px;
            }
            .steps li {
                margin-bottom: 10px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="success-icon">✓</div>
            <h1>Authentication Complete!</h1>
            <p>Your OneDrive account has been successfully connected.</p>
            
            <h2>Next Steps:</h2>
            <ol class="steps">
                <li>Return to the map layer form</li>
                <li>Select the same file you were trying to upload</li>
                <li>Make sure "OneDrive" is selected as the storage option</li>
                <li>Submit the form to complete the upload process</li>
            </ol>
            
            <a href="%s" class="btn">Continue to Map Layer Form</a>
        </div>
    </body>
    </html>
    """ % (redirect_url))
    
    return response