/**
 * Map functionality for Property Mapper application
 * Handles map initialization, property display, and interaction
 */

// Global variables
let propertyMap = null;
let markerLayer = null;
let propertyMarkers = {};
let radiusCircle = null;
let selectedRegion = null;
let mapLayers = {};  // Store custom map layers
let layerControl = null; // For layer control
let layerManager = null; // Advanced layer manager

/**
 * Initialize the map with specified region
 * @param {string} mapElementId - ID of the HTML element to render the map
 * @param {object} defaultRegion - Default region to display
 * @param {array} regions - All available regions
 */
function initMap(mapElementId, defaultRegion, regions) {
    // Initialize the map
    propertyMap = L.map(mapElementId).setView(defaultRegion.center, defaultRegion.zoom);
    
    // Define base layers
    const baseLayers = {
        'OpenStreetMap': L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxZoom: 19
        }),
        'Satellite': L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community',
            maxZoom: 19
        }),
        'Terrain': L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', {
            attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ, TomTom, Intermap, iPC, USGS, FAO, NPS, NRCAN, GeoBase, Kadaster NL, Ordnance Survey, Esri Japan, METI, Esri China (Hong Kong), and the GIS User Community',
            maxZoom: 19
        })
    };
    
    // Add default base layer (OpenStreetMap)
    baseLayers['OpenStreetMap'].addTo(propertyMap);
    
    // Create a layer for property markers
    markerLayer = L.layerGroup().addTo(propertyMap);
    
    // Initialize layer control in top-left position so it doesn't conflict with the search panel
    if (typeof createLayerManager === 'function') {
        // Use advanced layer manager if available
        layerManager = createLayerManager(propertyMap, baseLayers, {
            position: 'topleft',
            categorized: true,
            searchable: true,
            paginationSize: 5
        });
        
        // Add property markers layer
        layerManager.addOverlay(markerLayer, 'Properties', {
            category: 'Base Layers'
        });
        
        // For backward compatibility, still set layerControl
        layerControl = layerManager;
    } else {
        // Fall back to standard layer control
        layerControl = L.control.layers(baseLayers, {
            'Properties': markerLayer
        }, {
            position: 'topleft',
            collapsed: true  // Start collapsed for better space usage
        }).addTo(propertyMap);
    }
    
    // Set the selected region
    selectedRegion = defaultRegion;
    
    // Add event listener for region selection
    const regionItems = document.querySelectorAll('.region-item');
    regionItems.forEach(item => {
        item.addEventListener('click', function(e) {
            e.preventDefault();
            
            const regionId = parseInt(this.getAttribute('data-region-id'));
            const lat = parseFloat(this.getAttribute('data-lat'));
            const lng = parseFloat(this.getAttribute('data-lng'));
            const zoom = parseInt(this.getAttribute('data-zoom'));
            
            // Update the map view
            propertyMap.setView([lat, lng], zoom);
            
            // Update selected region
            selectedRegion = regions.find(r => r.id === regionId) || defaultRegion;
            
            // Load properties for this region
            loadRegionProperties(regionId);
            
            // Load map layers for this region
            loadMapLayers(regionId);
            
            // Update active class
            regionItems.forEach(ri => ri.classList.remove('active'));
            this.classList.add('active');
        });
    });
    
    // Load properties for default region
    if (defaultRegion && defaultRegion.id) {
        loadRegionProperties(defaultRegion.id);
        // Load map layers for default region
        loadMapLayers(defaultRegion.id);
    }
    
    // Add event listener for radius search
    propertyMap.on('click', handleMapClick);
    
    // Add event for zoom end to reload shapefile layers with appropriate detail
    propertyMap.on('zoomend', function() {
        // Only reload shapefiles if we're at certain zoom level boundaries
        const newZoom = propertyMap.getZoom();
        const zoomThresholds = [10, 12, 14, 16];
        
        // Only reload if we crossed a threshold to avoid too many reloads
        if (zoomThresholds.includes(newZoom)) {
            console.log(`Zoom changed to ${newZoom}, reloading shapefile layers`);
            
            // Reload shapefile layers at new zoom level
            for (const layerId in mapLayers) {
                const layerInfo = mapLayers[layerId]._layerInfo;
                if (layerInfo && layerInfo.layer_type === 'shapefile') {
                    // Remove old layer from map and control
                    propertyMap.removeLayer(mapLayers[layerId]);
                    
                    // Remove from appropriate layer control
                    if (layerManager && typeof layerManager.removeLayer === 'function') {
                        layerManager.removeLayer(mapLayers[layerId]);
                    } else {
                        layerControl.removeLayer(mapLayers[layerId]);
                    }
                    
                    // Re-add with new simplification
                    addMapLayer(layerInfo);
                }
            }
        }
    });
    
    // Add scale control
    L.control.scale().addTo(propertyMap);
    
    return propertyMap;
}

/**
 * Load properties for a specific region
 * @param {number} regionId - ID of the region to load properties for
 */
function loadRegionProperties(regionId) {
    // Show loading indicator
    showMapLoading(true);
    
    // Clear existing markers
    markerLayer.clearLayers();
    propertyMarkers = {};
    
    // Fetch properties from the API
    fetch(`/api/region/${regionId}/properties/`)
        .then(response => response.json())
        .then(data => {
            // Add markers for each property
            data.properties.forEach(property => {
                addPropertyMarker(property);
            });
            
            showMapLoading(false);
        })
        .catch(error => {
            console.error('Error loading region properties:', error);
            showMapLoading(false);
            
            // Show error message on the map
            showMapError('Failed to load properties. Please try again.');
        });
}

/**
 * Add a marker for a property on the map
 * @param {object} property - Property data object
 */
function addPropertyMarker(property) {
    if (!property.latitude || !property.longitude) {
        return;
    }
    
    // Create marker
    const marker = L.marker([property.latitude, property.longitude], {
        propertyId: property.id,
        title: property.address || property.lot_number
    });
    
    // Add popup with property information
    const popupContent = `
        <div class="property-popup">
            <h5>${property.address || 'Property'}</h5>
            <p><strong>Lot #:</strong> ${property.lot_number}</p>
            ${property.property_type ? `<p><strong>Type:</strong> ${property.property_type}</p>` : ''}
            <a href="${property.detail_url}" class="btn btn-primary btn-sm mt-2">View Details</a>
        </div>
    `;
    
    marker.bindPopup(popupContent);
    
    // Store the marker and add to layer
    propertyMarkers[property.id] = marker;
    marker.addTo(markerLayer);
    
    return marker;
}

/**
 * Handle map click events for radius search
 * @param {object} e - Map click event
 */
function handleMapClick(e) {
    // Check if radius search is selected
    const radiusRadio = document.getElementById('search-radius');
    if (!radiusRadio || !radiusRadio.checked) {
        return;
    }
    
    const lat = e.latlng.lat;
    const lng = e.latlng.lng;
    
    // Update hidden form fields
    document.getElementById('latitude').value = lat;
    document.getElementById('longitude').value = lng;
    
    // Get radius in kilometers
    const radiusInput = document.getElementById('radius');
    const radius = parseFloat(radiusInput.value) || 1.0;
    
    // Update or create the radius circle
    if (radiusCircle) {
        propertyMap.removeLayer(radiusCircle);
    }
    
    radiusCircle = L.circle([lat, lng], {
        radius: radius * 1000, // Convert to meters
        fillColor: '#3388ff',
        fillOpacity: 0.1,
        stroke: true,
        color: '#3388ff',
        weight: 2
    }).addTo(propertyMap);
    
    // Add a marker at the center
    const centerMarker = L.marker([lat, lng], {
        icon: L.divIcon({
            className: 'radius-center-marker',
            html: '<i class="fas fa-map-pin"></i>',
            iconSize: [20, 20],
            iconAnchor: [10, 20]
        })
    }).addTo(propertyMap);
    
    // Remove marker after 3 seconds
    setTimeout(() => {
        propertyMap.removeLayer(centerMarker);
    }, 3000);
}

/**
 * Show or hide loading indicator on the map
 * @param {boolean} isLoading - Whether to show loading indicator
 * @param {object} info - Optional information about the loading process (percentage, layer name, etc.)
 */
function showMapLoading(isLoading, info = {}) {
    // Remove existing loading indicator
    const existingIndicator = document.querySelector('.map-loading-indicator');
    if (existingIndicator) {
        // If we just want to update the existing indicator
        if (isLoading && info.updateOnly && info.percent) {
            const progressBar = existingIndicator.querySelector('.progress-bar');
            if (progressBar) {
                progressBar.style.width = `${info.percent}%`;
                progressBar.setAttribute('aria-valuenow', info.percent);
                existingIndicator.querySelector('.progress-text').textContent = 
                    `${info.percent}% - ${info.layerName || 'Loading'} (${info.loadedFeatures || '?'}/${info.totalFeatures || '?'} features)`;
                return;
            }
        } else {
            existingIndicator.remove();
        }
    }
    
    if (isLoading) {
        // Create loading indicator
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'map-loading-indicator';
        
        // Basic content for the loading indicator
        let content = `
            <div class="loading-spinner">
                <i class="fas fa-circle-notch fa-spin"></i>
                <span>Loading map data... This may take a moment for large files.</span>
            </div>
        `;
        
        // If we have percentage info, show a progress bar
        if (info.percent) {
            const layerText = info.layerName ? `Loading ${info.layerName}` : 'Loading layer';
            const featuresText = info.totalFeatures ? 
                `(${info.loadedFeatures || 0}/${info.totalFeatures} features)` : '';
            
            content = `
                <div class="loading-progress">
                    <div class="progress-header">
                        <i class="fas fa-circle-notch fa-spin"></i>
                        <span>${layerText}</span>
                    </div>
                    <div class="progress">
                        <div class="progress-bar" role="progressbar" 
                            style="width: ${info.percent}%" 
                            aria-valuenow="${info.percent}" 
                            aria-valuemin="0" 
                            aria-valuemax="100">
                        </div>
                    </div>
                    <div class="progress-text">${info.percent}% ${featuresText}</div>
                </div>
            `;
        }
        
        loadingDiv.innerHTML = content;
        
        // Add to map
        document.getElementById('map').appendChild(loadingDiv);
    }
}

/**
 * Show error message on the map
 * @param {string} message - Error message to display
 */
function showMapError(message) {
    // Create error message element
    const errorDiv = document.createElement('div');
    errorDiv.className = 'map-error-message alert alert-danger';
    errorDiv.innerHTML = `
        <i class="fas fa-exclamation-triangle"></i>
        ${message}
    `;
    
    // Add to map
    document.getElementById('map').appendChild(errorDiv);
    
    // Remove after 5 seconds
    setTimeout(() => {
        errorDiv.remove();
    }, 5000);
}

/**
 * Highlight a property on the map
 * @param {number} propertyId - ID of the property to highlight
 */
function highlightProperty(propertyId) {
    const marker = propertyMarkers[propertyId];
    if (marker) {
        marker.openPopup();
        propertyMap.panTo(marker.getLatLng());
    }
}

/**
 * Update the radius circle on the map
 * @param {number} lat - Latitude of the center point
 * @param {number} lng - Longitude of the center point
 * @param {number} radius - Radius in kilometers
 */
function updateRadiusCircle(lat, lng, radius) {
    // Remove existing circle
    if (radiusCircle) {
        propertyMap.removeLayer(radiusCircle);
    }
    
    // Create new circle
    radiusCircle = L.circle([lat, lng], {
        radius: radius * 1000, // Convert to meters
        fillColor: '#3388ff',
        fillOpacity: 0.1,
        stroke: true,
        color: '#3388ff',
        weight: 2
    }).addTo(propertyMap);
    
    // Center map on the circle
    propertyMap.setView([lat, lng], getZoomForRadius(radius));
}

/**
 * Calculate appropriate zoom level for a given radius
 * @param {number} radius - Radius in kilometers
 * @returns {number} - Zoom level
 */
function getZoomForRadius(radius) {
    if (radius <= 0.5) return 15;
    if (radius <= 1) return 14;
    if (radius <= 2) return 13;
    if (radius <= 5) return 12;
    if (radius <= 10) return 11;
    return 10;
}

/**
 * Display GeoJSON data on the map
 * @param {object} geojson - GeoJSON data to display
 * @param {object} options - Display options
 */
function displayGeoJson(geojson, options = {}) {
    const defaultOptions = {
        style: function(feature) {
            return {
                color: '#3388ff',
                weight: 2,
                opacity: 1,
                fillColor: '#3388ff',
                fillOpacity: 0.2
            };
        },
        onEachFeature: function(feature, layer) {
            if (feature.properties) {
                const popupContent = `
                    <div class="property-popup">
                        <h5>${feature.properties.address || 'Property'}</h5>
                        <p><strong>Lot #:</strong> ${feature.properties.lot_number}</p>
                        ${feature.properties.property_type ? `<p><strong>Type:</strong> ${feature.properties.property_type}</p>` : ''}
                        <a href="/property/${feature.properties.id}/" class="btn btn-primary btn-sm mt-2">View Details</a>
                    </div>
                `;
                layer.bindPopup(popupContent);
            }
        }
    };
    
    // Merge options
    const mergedOptions = { ...defaultOptions, ...options };
    
    // Add GeoJSON to map
    L.geoJSON(geojson, mergedOptions).addTo(propertyMap);
}

/**
 * Create a heatmap from property data
 * @param {array} properties - Array of property objects
 * @param {string} valueField - Field to use for heat intensity
 */
function createHeatmap(properties, valueField) {
    // Check if Leaflet.heat plugin is available
    if (!L.heatLayer) {
        console.error('Leaflet.heat plugin is not loaded');
        return;
    }
    
    // Create heatmap data
    const heatData = properties
        .filter(p => p.latitude && p.longitude && p[valueField])
        .map(p => [p.latitude, p.longitude, p[valueField]]);
    
    // Create and add heatmap layer
    const heatLayer = L.heatLayer(heatData, {
        radius: 25,
        blur: 15,
        maxZoom: 17
    }).addTo(propertyMap);
    
    return heatLayer;
}

/**
 * Load map layers for a specific region
 * @param {number} regionId - ID of the region to load layers for
 */
function loadMapLayers(regionId) {
    // Clear existing custom layers
    clearMapLayers();
    
    // Fetch available layers from the API
    fetch(`/api/layers/?region_id=${regionId}`)
        .then(response => response.json())
        .then(data => {
            // Process and add each layer
            data.layers.forEach(layerInfo => {
                addMapLayer(layerInfo);
            });
        })
        .catch(error => {
            console.error('Error loading map layers:', error);
        });
}

/**
 * Add a map layer based on its configuration
 * @param {object} layerInfo - Layer configuration from the API
 */
function addMapLayer(layerInfo) {
    // Check if layer already exists
    if (mapLayers[layerInfo.id]) {
        return mapLayers[layerInfo.id];
    }
    
    let layer = null;
    
    // Process different layer types
    switch (layerInfo.layer_type) {
        case 'tile':
            // Add tile layer
            layer = L.tileLayer(layerInfo.url, {
                attribution: layerInfo.description || '',
                maxZoom: 19
            });
            break;
            
        case 'wms':
            // Add WMS service layer
            layer = L.tileLayer.wms(layerInfo.url, {
                layers: layerInfo.style && layerInfo.style.layers ? layerInfo.style.layers : '',
                format: 'image/png',
                transparent: true,
                attribution: layerInfo.description || ''
            });
            break;
            
        case 'geojson':
        case 'shapefile':
            // Show loading indicator for large files
            showMapLoading(true, { layerName: layerInfo.name });
            
            // If we have layer manager, mark layer as loading
            if (layerManager && typeof layerManager.setLayerLoading === 'function') {
                layerManager.setLayerLoading(layerInfo.name, true, { percent: 0 });
            }
            
            // For shapefiles, add optimization parameters
            let url = `/api/layer/${layerInfo.id}/data/`;
            if (layerInfo.layer_type === 'shapefile') {
                // Get current map zoom level to adjust simplification
                const zoom = propertyMap.getZoom();
                let simplify = 'auto';
                let maxFeatures = 10000;
                
                // Adjust simplification based on zoom level
                if (zoom <= 10) {
                    simplify = 0.01; // High simplification for far zoom
                    maxFeatures = 5000; // Fewer features at far zoom
                } else if (zoom <= 12) {
                    simplify = 0.005; // Medium simplification
                    maxFeatures = 10000;
                } else if (zoom <= 14) {
                    simplify = 0.002; // Light simplification
                    maxFeatures = 15000;
                } else {
                    simplify = 0.001; // Minimal simplification for close zoom
                    maxFeatures = 25000; // More features at close zoom
                }
                
                // Add parameters to URL including zoom level for backend optimization
                url += `?simplify=${simplify}&max_features=${maxFeatures}&zoom=${zoom}`;
                
                console.log(`Loading shapefile layer with simplification ${simplify} at zoom ${zoom}, max features: ${maxFeatures}`);
            }
            
            // Fetch and process GeoJSON data
            fetch(url)
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error ${response.status}`);
                    }
                    
                    // Get response size for progress calculation
                    const contentLength = response.headers.get('content-length');
                    if (contentLength && layerInfo.layer_type === 'shapefile') {
                        const totalBytes = parseInt(contentLength, 10);
                        let receivedBytes = 0;
                        
                        // Create a reader to read the streaming response
                        const reader = response.body.getReader();
                        const chunks = [];
                        
                        // Function to process stream chunks with progress
                        return new Promise((resolve, reject) => {
                            function processChunk({ done, value }) {
                                if (done) {
                                    // Combine all chunks into one Uint8Array
                                    const chunksAll = new Uint8Array(receivedBytes);
                                    let position = 0;
                                    for (const chunk of chunks) {
                                        chunksAll.set(chunk, position);
                                        position += chunk.length;
                                    }
                                    
                                    // Convert to text and then parse as JSON
                                    const json = new TextDecoder("utf-8").decode(chunksAll);
                                    try {
                                        resolve(JSON.parse(json));
                                    } catch (error) {
                                        reject(new Error('Failed to parse JSON response'));
                                    }
                                    return;
                                }
                                
                                // Store this chunk and update progress
                                chunks.push(value);
                                receivedBytes += value.length;
                                
                                // Calculate and display progress
                                const percent = Math.round((receivedBytes / totalBytes) * 100);
                                
                                // Update loading indicators with progress
                                showMapLoading(true, {
                                    updateOnly: true,
                                    percent: percent, 
                                    layerName: layerInfo.name
                                });
                                
                                // Update layer manager loading indicator if available
                                if (layerManager && typeof layerManager.setLayerLoading === 'function') {
                                    layerManager.setLayerLoading(layerInfo.name, true, { 
                                        percent: percent
                                    });
                                }
                                
                                // Continue reading
                                return reader.read().then(processChunk);
                            }
                            
                            // Start reading the stream
                            reader.read().then(processChunk);
                        });
                    }
                    
                    // Regular response handling if no content-length
                    return response.json();
                })
                .then(data => {
                    // Create style function
                    let styleFunction = function() {
                        return {
                            color: '#3388ff',
                            weight: 2,
                            opacity: 1,
                            fillColor: '#3388ff',
                            fillOpacity: 0.2
                        };
                    };
                    
                    // If custom style is provided, use it
                    if (layerInfo.style) {
                        styleFunction = function() {
                            return layerInfo.style;
                        };
                    }
                    
                    // Hide loading indicator
                    showMapLoading(false);
                    
                    // Clear loading state in layer manager
                    if (layerManager && typeof layerManager.setLayerLoading === 'function') {
                        layerManager.setLayerLoading(layerInfo.name, false);
                    }
                    
                    // Log info about the data if available
                    if (data.info) {
                        console.log(`Layer ${layerInfo.name} info:`, data.info);
                    }
                    
                    // Create GeoJSON layer
                    const gjLayer = L.geoJSON(data, {
                        style: styleFunction,
                        onEachFeature: function(feature, layer) {
                            if (feature.properties) {
                                // Create popup content from properties
                                let popupContent = '<div class="custom-layer-popup">';
                                for (const key in feature.properties) {
                                    if (key !== 'id' && key !== 'geometry' && feature.properties[key] !== null) {
                                        popupContent += `<p><strong>${key}:</strong> ${feature.properties[key]}</p>`;
                                    }
                                }
                                popupContent += '</div>';
                                layer.bindPopup(popupContent);
                            }
                        }
                    });
                    
                    // Store layer info for future use (like zoom-based reloading)
                    gjLayer._layerInfo = layerInfo;
                    
                    // Track what zoom level this was loaded at
                    gjLayer._loadedAtZoom = propertyMap.getZoom();
                    
                    // Add feature count information for debugging
                    if (data.features) {
                        gjLayer._featureCount = data.features.length;
                        console.log(`Loaded layer ${layerInfo.name} with ${data.features.length} features at zoom level ${gjLayer._loadedAtZoom}`);
                        
                        // Check if we have info about the original number of features
                        if (data.info && data.info.total_features) {
                            // Calculate percentage of total features loaded
                            const percentage = (data.features.length / data.info.total_features * 100).toFixed(1);
                            console.log(`Layer ${layerInfo.name} info:`, data.info);
                            
                            // Show a message if we're only showing a small fraction of the data
                            if (percentage < 5) {
                                // This is < 5% of the total data, show hint message
                                const messageDiv = document.createElement('div');
                                messageDiv.className = 'map-info-message alert alert-info';
                                messageDiv.innerHTML = `
                                    <i class="fas fa-info-circle"></i>
                                    Showing ${percentage}% of the "${layerInfo.name}" layer. Zoom in for more detail.
                                `;
                                
                                // Add to map with auto removal after 5 seconds
                                document.getElementById('map').appendChild(messageDiv);
                                setTimeout(() => messageDiv.remove(), 8000);
                            }
                        }
                    }
                    
                    // Store and add to map
                    mapLayers[layerInfo.id] = gjLayer;
                    
                    // Add to layer control and show if needed
                    if (layerManager && typeof layerManager.addOverlay === 'function') {
                        // Use the advanced layer manager
                        const category = layerInfo.layer_type === 'shapefile' ? 'Shapefiles' : 'GeoJSON Layers';
                        layerManager.addOverlay(gjLayer, layerInfo.name, {
                            category: category,
                            description: layerInfo.description || '',
                            active: layerInfo.is_visible_by_default
                        });
                    } else {
                        // Fall back to standard control
                        layerControl.addOverlay(gjLayer, layerInfo.name);
                    }
                    
                    if (layerInfo.is_visible_by_default) {
                        gjLayer.addTo(propertyMap);
                    }
                })
                .catch(error => {
                    console.error(`Error loading layer ${layerInfo.name}:`, error);
                    showMapLoading(false);
                    
                    // Clear loading state in layer manager
                    if (layerManager && typeof layerManager.setLayerLoading === 'function') {
                        layerManager.setLayerLoading(layerInfo.name, false);
                    }
                    
                    // Provide a more detailed error message
                    let errorMessage = `Failed to load layer "${layerInfo.name}".`;
                    
                    // If it's likely a timeout or size issue
                    if (error.message && error.message.includes('timeout')) {
                        errorMessage += " The layer is too large and timed out. Try zooming in to load a smaller area.";
                    } else if (layerInfo.layer_type === 'shapefile') {
                        errorMessage += " This shapefile may be too large. Try zooming in further to load with higher simplification.";
                    } else {
                        errorMessage += " The layer may be temporarily unavailable.";
                    }
                    
                    showMapError(errorMessage);
                    
                    // Log more details for debugging
                    console.log(`Layer details: Type=${layerInfo.layer_type}, ID=${layerInfo.id}`);
                });
            return; // Exit early since this is handled asynchronously
            
        case 'kml':
            // For KML files, use the Leaflet-KML plugin or a similar approach
            // This requires additional libraries to be included
            console.log(`KML layer ${layerInfo.name} - To implement with Leaflet-KML`);
            // fetch(`/api/layer/${layerInfo.id}/data/`)
            //     .then(response => response.text())
            //     .then(kmlString => {
            //         // Process KML (requires Leaflet-KML plugin)
            //         // const kmlLayer = L.KML(kmlString);
            //         // mapLayers[layerInfo.id] = kmlLayer;
            //         // layerControl.addOverlay(kmlLayer, layerInfo.name);
            //         
            //         // if (layerInfo.is_visible_by_default) {
            //         //     kmlLayer.addTo(propertyMap);
            //         // }
            //     });
            return;
            
        default:
            console.warn(`Unsupported layer type: ${layerInfo.layer_type}`);
            return;
    }
    
    // For immediate layer types (tile, wms), store and add to map
    if (layer) {
        mapLayers[layerInfo.id] = layer;
        
        // Add to layer control
        if (layerManager && typeof layerManager.addOverlay === 'function') {
            // Use the advanced layer manager
            let category;
            switch(layerInfo.layer_type) {
                case 'tile':
                    category = 'Tile Layers';
                    break;
                case 'wms':
                    category = 'WMS Services';
                    break;
                default:
                    category = 'Additional Layers';
            }
            
            layerManager.addOverlay(layer, layerInfo.name, {
                category: category,
                description: layerInfo.description || '',
                active: layerInfo.is_visible_by_default
            });
        } else {
            // Fall back to standard control
            layerControl.addOverlay(layer, layerInfo.name);
        }
        
        // Add to map if it should be visible by default
        if (layerInfo.is_visible_by_default) {
            layer.addTo(propertyMap);
        }
        
        return layer;
    }
}

/**
 * Clear all custom map layers
 */
function clearMapLayers() {
    // Remove each layer from the map
    Object.keys(mapLayers).forEach(layerId => {
        const layer = mapLayers[layerId];
        if (layer) {
            if (propertyMap.hasLayer(layer)) {
                propertyMap.removeLayer(layer);
            }
            
            // Remove from layer control
            if (layerManager && typeof layerManager.removeLayer === 'function') {
                layerManager.removeLayer(layer);
            } else {
                layerControl.removeLayer(layer);
            }
        }
    });
    
    // Reset the layers object
    mapLayers = {};
}
