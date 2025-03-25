/**
 * Search functionality for Property Mapper application
 * Handles search form behavior and AJAX property search
 */

// Initialize the search functionality
function initSearch() {
    setupSearchTypeToggle();
    setupSearchForm();
    setupAjaxSearch();
}

/**
 * Setup behavior for toggling between search types
 */
function setupSearchTypeToggle() {
    const searchTypeRadios = document.querySelectorAll('input[name="search_type"]');
    const lotSearchFields = document.getElementById('lot-search-fields');
    const addressSearchFields = document.getElementById('address-search-fields');
    const radiusSearchFields = document.getElementById('radius-search-fields');
    
    // Function to toggle visibility of search fields
    function toggleSearchFields() {
        const selectedType = document.querySelector('input[name="search_type"]:checked').value;
        
        lotSearchFields.style.display = selectedType === 'lot' ? 'block' : 'none';
        addressSearchFields.style.display = selectedType === 'address' ? 'block' : 'none';
        radiusSearchFields.style.display = selectedType === 'radius' ? 'block' : 'none';
    }
    
    // Add change event listener to each radio button
    searchTypeRadios.forEach(radio => {
        radio.addEventListener('change', toggleSearchFields);
    });
    
    // Initial toggle based on default selection
    toggleSearchFields();
}

/**
 * Setup search form behavior
 */
function setupSearchForm() {
    const searchForm = document.getElementById('search-form');
    if (!searchForm) return;
    
    // Add event listener for radius change
    const radiusInput = document.getElementById('radius');
    if (radiusInput) {
        radiusInput.addEventListener('input', function() {
            // Update radius circle on map if lat/lng are already set
            const lat = parseFloat(document.getElementById('latitude').value);
            const lng = parseFloat(document.getElementById('longitude').value);
            const radius = parseFloat(this.value);
            
            if (!isNaN(lat) && !isNaN(lng) && !isNaN(radius) && window.updateRadiusCircle) {
                window.updateRadiusCircle(lat, lng, radius);
            }
        });
    }
    
    // Add event listener for form submission
    searchForm.addEventListener('submit', function(e) {
        // Validate the form based on search type
        const searchType = document.querySelector('input[name="search_type"]:checked').value;
        
        if (searchType === 'lot' && !document.getElementById('lot_number').value.trim()) {
            e.preventDefault();
            showSearchError('Please enter a lot or matricule number.');
        }
        else if (searchType === 'address' && !document.getElementById('address').value.trim()) {
            e.preventDefault();
            showSearchError('Please enter an address.');
        }
        else if (searchType === 'radius') {
            const lat = document.getElementById('latitude').value;
            const lng = document.getElementById('longitude').value;
            
            if (!lat || !lng) {
                e.preventDefault();
                showSearchError('Please click on the map to set a center point for radius search.');
            }
        }
    });
}

/**
 * Setup AJAX search functionality
 */
function setupAjaxSearch() {
    const searchForm = document.getElementById('search-form');
    const searchResults = document.getElementById('search-results');
    
    if (!searchForm || !searchResults) return;
    
    let searchTimeout = null;
    
    // Add input event listeners for live search
    const lotInput = document.getElementById('lot_number');
    const addressInput = document.getElementById('address');
    
    if (lotInput) {
        lotInput.addEventListener('input', function() {
            const searchType = document.querySelector('input[name="search_type"]:checked').value;
            if (searchType === 'lot' && this.value.trim().length >= 3) {
                triggerLiveSearch();
            }
        });
    }
    
    if (addressInput) {
        addressInput.addEventListener('input', function() {
            const searchType = document.querySelector('input[name="search_type"]:checked').value;
            if (searchType === 'address' && this.value.trim().length >= 3) {
                triggerLiveSearch();
            }
        });
    }
    
    function triggerLiveSearch() {
        // Clear previous timeout
        if (searchTimeout) {
            clearTimeout(searchTimeout);
        }
        
        // Set new timeout to avoid too many requests
        searchTimeout = setTimeout(function() {
            performAjaxSearch();
        }, 500);
    }
    
    function performAjaxSearch() {
        const formData = new FormData(searchForm);
        const searchParams = new URLSearchParams();
        
        for (const [key, value] of formData.entries()) {
            if (value) {
                searchParams.append(key, value);
            }
        }
        
        // Show loading indicator
        searchResults.innerHTML = '<div class="text-center p-3"><i class="fas fa-spinner fa-spin"></i> Searching...</div>';
        
        // Perform AJAX request
        fetch(`/search/?${searchParams.toString()}`, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.json())
        .then(data => {
            displaySearchResults(data);
        })
        .catch(error => {
            console.error('Error during search:', error);
            searchResults.innerHTML = '<div class="alert alert-danger">An error occurred during search. Please try again.</div>';
            // Clear any existing markers to avoid confusion
            if (typeof window.markerLayer !== 'undefined' && window.markerLayer) {
                window.markerLayer.clearLayers();
            }
        });
    }
    
    function displaySearchResults(data) {
        if (data.properties && data.properties.length > 0) {
            let resultsHtml = `
                <h6 class="mt-3">Found ${data.total_count} properties</h6>
                <div class="list-group">
            `;
            
            data.properties.forEach(property => {
                resultsHtml += `
                    <a href="${property.detail_url}" class="list-group-item list-group-item-action">
                        <div class="d-flex w-100 justify-content-between">
                            <h6 class="mb-1">${property.address || property.lot_number}</h6>
                        </div>
                        <p class="mb-1">Lot #: ${property.lot_number}</p>
                        <small>${property.property_type || 'N/A'}</small>
                    </a>
                `;
            });
            
            resultsHtml += '</div>';
            
            // Add pagination if needed
            if (data.has_next || data.has_previous) {
                resultsHtml += '<div class="d-flex justify-content-between mt-2">';
                
                if (data.has_previous) {
                    resultsHtml += '<button class="btn btn-sm btn-outline-primary load-more" data-direction="prev">Previous</button>';
                } else {
                    resultsHtml += '<div></div>';
                }
                
                resultsHtml += `<small>Page ${data.page_number} of ${data.total_pages}</small>`;
                
                if (data.has_next) {
                    resultsHtml += '<button class="btn btn-sm btn-outline-primary load-more" data-direction="next">Next</button>';
                } else {
                    resultsHtml += '<div></div>';
                }
                
                resultsHtml += '</div>';
            }
            
            searchResults.innerHTML = resultsHtml;
            
            // Add event listeners for pagination buttons
            const paginationButtons = searchResults.querySelectorAll('.load-more');
            paginationButtons.forEach(button => {
                button.addEventListener('click', function() {
                    const direction = this.getAttribute('data-direction');
                    const newPage = direction === 'next' ? data.page_number + 1 : data.page_number - 1;
                    
                    const formData = new FormData(searchForm);
                    const searchParams = new URLSearchParams();
                    
                    for (const [key, value] of formData.entries()) {
                        if (value) {
                            searchParams.append(key, value);
                        }
                    }
                    
                    searchParams.append('page', newPage);
                    
                    // Show loading indicator
                    searchResults.innerHTML = '<div class="text-center p-3"><i class="fas fa-spinner fa-spin"></i> Loading...</div>';
                    
                    // Perform AJAX request
                    fetch(`/search/?${searchParams.toString()}`, {
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest'
                        }
                    })
                    .then(response => response.json())
                    .then(data => {
                        displaySearchResults(data);
                    })
                    .catch(error => {
                        console.error('Error during pagination:', error);
                        searchResults.innerHTML = '<div class="alert alert-danger">An error occurred. Please try again.</div>';
                        // Clear any existing markers to avoid confusion
                        if (typeof window.markerLayer !== 'undefined' && window.markerLayer) {
                            window.markerLayer.clearLayers();
                        }
                    });
                });
            });
            
            // If we have markers to show, update the map
            if (typeof addPropertyMarkers === 'function' && data.properties.some(p => p.latitude && p.longitude)) {
                addPropertyMarkers(data.properties);
            }
        } else {
            searchResults.innerHTML = '<div class="alert alert-info mt-3">No properties found matching your search criteria.</div>';
        }
    }
}

/**
 * Show search error message
 * @param {string} message - Error message to display
 */
function showSearchError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'alert alert-danger mt-2';
    errorDiv.textContent = message;
    
    const searchForm = document.getElementById('search-form');
    searchForm.appendChild(errorDiv);
    
    // Remove after 5 seconds
    setTimeout(() => {
        errorDiv.remove();
    }, 5000);
}

/**
 * Initialize search form behavior on the search results page
 */
function initSearchFormBehavior() {
    setupSearchTypeToggle();
    
    // Add event listener for radius change
    const radiusInput = document.getElementById('radius');
    if (radiusInput) {
        radiusInput.addEventListener('input', function() {
            // Update radius circle on map if lat/lng are already set
            const lat = parseFloat(document.getElementById('latitude').value);
            const lng = parseFloat(document.getElementById('longitude').value);
            const radius = parseFloat(this.value);
            
            if (!isNaN(lat) && !isNaN(lng) && !isNaN(radius)) {
                // If we're on the search results page with a map
                const resultsMap = document.getElementById('results-map');
                if (resultsMap && resultsMap._leaflet_id) {
                    // Remove existing circle
                    const existingCircle = document.querySelector('.leaflet-interactive');
                    if (existingCircle) {
                        existingCircle._leaflet_id.remove();
                    }
                    
                    // Create new circle
                    L.circle([lat, lng], {
                        radius: radius * 1000, // Convert to meters
                        fillColor: '#3388ff',
                        fillOpacity: 0.1,
                        stroke: true,
                        color: '#3388ff',
                        weight: 2
                    }).addTo(resultsMap._leaflet_id);
                }
            }
        });
    }
}

/**
 * Add property markers to the map
 * @param {array} properties - Array of property objects
 */
function addPropertyMarkers(properties) {
    // Check if we're on the main page with the map
    if (!window.propertyMap || !window.markerLayer) return;
    
    // Clear existing markers
    window.markerLayer.clearLayers();
    window.propertyMarkers = {};
    
    // Add markers for each property
    properties.forEach(property => {
        if (property.latitude && property.longitude) {
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
            window.propertyMarkers[property.id] = marker;
            marker.addTo(window.markerLayer);
        }
    });
    
    // Adjust map view to show all markers
    if (Object.keys(window.propertyMarkers).length > 0) {
        const bounds = L.featureGroup(Object.values(window.propertyMarkers)).getBounds();
        window.propertyMap.fitBounds(bounds, { padding: [50, 50] });
    }
}
