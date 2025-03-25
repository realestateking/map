from django.urls import path
from . import views
from . import onedrive
from django.http import HttpResponse

# Add a debug view to help with domain issues
def domain_debug(request):
    """Debug view to show the current domain and request information."""
    from django.conf import settings
    import os
    
    html = f"""
    <html>
    <head>
        <title>Domain Debug Information</title>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; padding: 20px; max-width: 800px; margin: 0 auto; }}
            h1 {{ color: #0078d4; }}
            .debug-info {{ background: #f5f5f5; padding: 15px; border-radius: 4px; margin: 20px 0; }}
            .debug-item {{ margin-bottom: 10px; }}
            .key {{ font-weight: bold; display: inline-block; width: 200px; }}
            .value {{ display: inline-block; }}
            pre {{ background: #f0f0f0; padding: 10px; border-radius: 4px; overflow-x: auto; }}
        </style>
    </head>
    <body>
        <h1>Domain Debug Information</h1>
        
        <div class="debug-info">
            <div class="debug-item">
                <span class="key">HTTP_HOST:</span>
                <span class="value">{request.META.get('HTTP_HOST', 'Not available')}</span>
            </div>
            <div class="debug-item">
                <span class="key">SERVER_NAME:</span>
                <span class="value">{request.META.get('SERVER_NAME', 'Not available')}</span>
            </div>
            <div class="debug-item">
                <span class="key">REMOTE_ADDR:</span>
                <span class="value">{request.META.get('REMOTE_ADDR', 'Not available')}</span>
            </div>
            <div class="debug-item">
                <span class="key">REQUEST_URI:</span>
                <span class="value">{request.META.get('REQUEST_URI', 'Not available')}</span>
            </div>
            <div class="debug-item">
                <span class="key">PATH_INFO:</span>
                <span class="value">{request.path}</span>
            </div>
            <div class="debug-item">
                <span class="key">get_host():</span>
                <span class="value">{request.get_host()}</span>
            </div>
            <div class="debug-item">
                <span class="key">build_absolute_uri():</span>
                <span class="value">{request.build_absolute_uri()}</span>
            </div>
            <div class="debug-item">
                <span class="key">is_secure():</span>
                <span class="value">{request.is_secure()}</span>
            </div>
        </div>
        
        <h2>Configuration</h2>
        <div class="debug-info">
            <div class="debug-item">
                <span class="key">Settings BASE_URL:</span>
                <span class="value">{settings.BASE_URL}</span>
            </div>
            <div class="debug-item">
                <span class="key">OneDrive Redirect URI:</span>
                <span class="value">{settings.ONEDRIVE_REDIRECT_URI}</span>
            </div>
            <div class="debug-item">
                <span class="key">ALLOWED_HOSTS:</span>
                <span class="value">{settings.ALLOWED_HOSTS}</span>
            </div>
            <div class="debug-item">
                <span class="key">CSRF_TRUSTED_ORIGINS:</span>
                <span class="value">{settings.CSRF_TRUSTED_ORIGINS}</span>
            </div>
        </div>
        
        <h2>Environment Variables</h2>
        <div class="debug-info">
            <div class="debug-item">
                <span class="key">HTTP_HOST:</span>
                <span class="value">{os.environ.get('HTTP_HOST', 'Not set')}</span>
            </div>
            <div class="debug-item">
                <span class="key">REPL_SLUG:</span>
                <span class="value">{os.environ.get('REPL_SLUG', 'Not set')}</span>
            </div>
            <div class="debug-item">
                <span class="key">REPL_OWNER:</span>
                <span class="value">{os.environ.get('REPL_OWNER', 'Not set')}</span>
            </div>
        </div>
        
        <p>
            <a href="/onedrive-debug/" style="color: #0078d4;">Go to OneDrive Debug Page</a> |
            <a href="/" style="color: #0078d4;">Back to Home</a>
        </p>
    </body>
    </html>
    """
    return HttpResponse(html)

urlpatterns = [
    path('', views.index, name='index'),
    path('search/', views.search_properties, name='search_properties'),
    path('property/<int:property_id>/', views.property_detail, name='property_detail'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('upload/', views.upload_file, name='upload_file'),
    path('process-ml/<int:property_id>/', views.process_ml, name='process_ml'),
    
    # Map layer management
    path('map-layers/', views.map_layer_list, name='map_layer_list'),
    path('map-layers/add/', views.add_map_layer, name='add_map_layer'),
    path('map-layers/<int:layer_id>/edit/', views.edit_map_layer, name='edit_map_layer'),
    path('map-layers/<int:layer_id>/delete/', views.delete_map_layer, name='delete_map_layer'),
    
    # OneDrive integration
    path('onedrive-auth/', onedrive.authenticate_onedrive, name='onedrive_auth'),
    path('onedrive-callback/', onedrive.onedrive_callback, name='onedrive_callback'),
    path('onedrive-check/', onedrive.check_onedrive_auth, name='onedrive_check'),
    path('onedrive-debug/', onedrive.onedrive_debug, name='onedrive_debug'),
    
    # Debug views
    path('domain-debug/', domain_debug, name='domain_debug'),
    
    # API endpoints
    path('api/region/<int:region_id>/properties/', views.region_properties, name='region_properties'),
    path('api/layers/', views.map_layers_list, name='map_layers_list'),
    path('api/layer/<int:layer_id>/data/', views.map_layer_data, name='map_layer_data'),
]
