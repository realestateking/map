/**
 * Property detail functionality for Property Mapper application
 * Handles displaying property details, maps, and visualizations
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    if (tooltips.length > 0) {
        tooltips.forEach(tooltip => {
            new bootstrap.Tooltip(tooltip);
        });
    }
    
    // Setup property detail map if element exists
    const propertyMapElement = document.getElementById('property-map');
    if (propertyMapElement) {
        initializePropertyMap(propertyMapElement);
    }
    
    // Setup property charts if elements exist
    const areaChartElement = document.getElementById('areaChart');
    if (areaChartElement) {
        initializeAreaChart(areaChartElement);
    }
    
    const qualityGaugeElement = document.getElementById('qualityGauge');
    if (qualityGaugeElement) {
        initializeQualityGauge(qualityGaugeElement);
    }
    
    // Setup image gallery if it exists
    const imageGalleryElement = document.getElementById('property-images');
    if (imageGalleryElement) {
        initializeImageGallery(imageGalleryElement);
    }
    
    // Setup property comparison if it exists
    const propertyComparisonElement = document.getElementById('property-comparison');
    if (propertyComparisonElement) {
        initializePropertyComparison(propertyComparisonElement);
    }
    
    // Setup street view if element exists
    const streetViewElement = document.getElementById('street-view');
    if (streetViewElement) {
        initializeStreetView(streetViewElement);
    }
});

/**
 * Initialize property detail map
 * @param {HTMLElement} mapElement - Map container element
 */
function initializePropertyMap(mapElement) {
    // Check if property location data is available in the data attribute
    const lat = parseFloat(mapElement.getAttribute('data-lat'));
    const lng = parseFloat(mapElement.getAttribute('data-lng'));
    const hasPolygon = mapElement.hasAttribute('data-polygon');
    
    if (isNaN(lat) || isNaN(lng)) {
        // Fallback to region center if no property location
        const regionLat = parseFloat(mapElement.getAttribute('data-region-lat') || 45.0);
        const regionLng = parseFloat(mapElement.getAttribute('data-region-lng') || -73.0);
        const zoom = parseInt(mapElement.getAttribute('data-region-zoom') || 10);
        
        // Initialize map with region center
        const map = L.map(mapElement.id).setView([regionLat, regionLng], zoom);
        
        // Add tile layer
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(map);
        
        // Add notice about missing location
        const noLocationNotice = L.control({position: 'bottomleft'});
        noLocationNotice.onAdd = function(map) {
            const div = L.DomUtil.create('div', 'no-location-notice');
            div.innerHTML = '<div class="alert alert-warning">No precise location data available for this property.</div>';
            return div;
        };
        noLocationNotice.addTo(map);
        
        return map;
    }
    
    // Initialize map with property location
    const map = L.map(mapElement.id).setView([lat, lng], 16);
    
    // Add tile layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
    
    // Add marker for property location
    const marker = L.marker([lat, lng]).addTo(map);
    
    // Add popup with basic property info
    const propertyAddress = mapElement.getAttribute('data-address') || 'Property';
    const propertyLotNumber = mapElement.getAttribute('data-lot-number') || '';
    
    marker.bindPopup(`
        <strong>${propertyAddress}</strong><br>
        Lot #: ${propertyLotNumber}
    `).openPopup();
    
    // Add polygon if available
    if (hasPolygon) {
        try {
            const polygonData = JSON.parse(mapElement.getAttribute('data-polygon'));
            
            // Create polygon with the provided coordinates
            const polygonCoordinates = polygonData.coordinates[0].map(coord => [coord[1], coord[0]]);
            
            const polygon = L.polygon(polygonCoordinates, {
                color: '#3388ff',
                weight: 2,
                opacity: 1,
                fillColor: '#3388ff',
                fillOpacity: 0.2
            }).addTo(map);
            
            // Fit map to polygon bounds
            map.fitBounds(polygon.getBounds());
        } catch (error) {
            console.error('Error parsing polygon data:', error);
        }
    }
    
    return map;
}

/**
 * Initialize property area comparison chart
 * @param {HTMLElement} chartElement - Chart canvas element
 */
function initializeAreaChart(chartElement) {
    const buildingArea = parseFloat(chartElement.getAttribute('data-building-area') || 0);
    const landArea = parseFloat(chartElement.getAttribute('data-land-area') || 0);
    
    if (buildingArea <= 0 || landArea <= 0) {
        // No valid data, show message
        const parentElement = chartElement.parentElement;
        parentElement.innerHTML = '<div class="alert alert-info">No area data available for comparison.</div>';
        return;
    }
    
    // Ensure land area is greater than or equal to building area
    const validLandArea = Math.max(landArea, buildingArea);
    const remainingArea = validLandArea - buildingArea;
    
    // Create the area chart
    const ctx = chartElement.getContext('2d');
    new Chart(ctx, {
        type: 'pie',
        data: {
            labels: ['Building Area', 'Remaining Land Area'],
            datasets: [{
                data: [buildingArea, remainingArea],
                backgroundColor: [
                    '#4e73df',
                    '#36b9cc'
                ],
                hoverBackgroundColor: [
                    '#2e59d9',
                    '#2c9faf'
                ],
                hoverBorderColor: "rgba(234, 236, 244, 1)",
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            var label = context.label || '';
                            var value = context.raw || 0;
                            return label + ': ' + value.toLocaleString() + ' m²';
                        }
                    }
                }
            }
        }
    });
}

/**
 * Initialize quality score gauge chart
 * @param {HTMLElement} gaugeElement - Gauge canvas element
 */
function initializeQualityGauge(gaugeElement) {
    const qualityScore = parseFloat(gaugeElement.getAttribute('data-quality-score'));
    
    if (isNaN(qualityScore)) {
        // No valid data, show message
        const parentElement = gaugeElement.parentElement;
        parentElement.innerHTML = '<div class="alert alert-info">No quality score available.</div>';
        return;
    }
    
    // Create the gauge chart
    const ctx = gaugeElement.getContext('2d');
    
    // Define colors based on score
    let gaugeColor;
    let qualityLabel;
    
    if (qualityScore >= 80) {
        gaugeColor = '#4CAF50';  // Green
        qualityLabel = 'Excellent';
    } else if (qualityScore >= 60) {
        gaugeColor = '#8BC34A';  // Light Green
        qualityLabel = 'Good';
    } else if (qualityScore >= 40) {
        gaugeColor = '#FFC107';  // Amber
        qualityLabel = 'Average';
    } else if (qualityScore >= 20) {
        gaugeColor = '#FF9800';  // Orange
        qualityLabel = 'Fair';
    } else {
        gaugeColor = '#F44336';  // Red
        qualityLabel = 'Poor';
    }
    
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            datasets: [{
                data: [qualityScore, 100 - qualityScore],
                backgroundColor: [
                    gaugeColor,
                    '#e0e0e0'
                ],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            circumference: 180,
            rotation: 270,
            cutout: '75%',
            plugins: {
                tooltip: {
                    enabled: false
                },
                legend: {
                    display: false
                }
            }
        },
        plugins: [{
            id: 'gaugeText',
            afterDraw: (chart) => {
                const width = chart.width;
                const height = chart.height;
                const ctx = chart.ctx;
                
                ctx.restore();
                ctx.font = 'bold 24px Arial';
                ctx.textBaseline = 'middle';
                ctx.textAlign = 'center';
                ctx.fillStyle = gaugeColor;
                ctx.fillText(Math.round(qualityScore), width / 2, height - 20);
                
                ctx.font = '16px Arial';
                ctx.fillStyle = '#666';
                ctx.fillText(qualityLabel, width / 2, height - 45);
                
                ctx.save();
            }
        }]
    });
}

/**
 * Initialize property image gallery
 * @param {HTMLElement} galleryElement - Gallery container element
 */
function initializeImageGallery(galleryElement) {
    // This is a simplified version for demonstration
    // In a real implementation, we would use a proper gallery library
    
    const images = galleryElement.querySelectorAll('img');
    const mainImage = document.getElementById('main-property-image');
    
    if (images.length === 0 || !mainImage) {
        return;
    }
    
    // Add click handlers to thumbnail images
    images.forEach(img => {
        img.addEventListener('click', function() {
            // Update main image
            mainImage.src = this.src;
            mainImage.alt = this.alt;
            
            // Remove active class from all thumbnails
            images.forEach(i => i.classList.remove('active'));
            
            // Add active class to clicked thumbnail
            this.classList.add('active');
        });
    });
}

/**
 * Initialize property comparison
 * @param {HTMLElement} comparisonElement - Comparison container element
 */
function initializePropertyComparison(comparisonElement) {
    // This would handle loading and comparing similar properties
    // For the demo, we'll just add a message
    
    comparisonElement.innerHTML = `
        <div class="alert alert-info">
            <i class="fas fa-info-circle"></i>
            Property comparison data is being loaded. This feature will allow comparing this property with similar properties in the area.
        </div>
    `;
}

/**
 * Initialize street view display
 * @param {HTMLElement} streetViewElement - Street view container element
 */
function initializeStreetView(streetViewElement) {
    // In a real implementation, this would integrate with a service like Google Street View
    // For this implementation, we'll show a placeholder
    
    const lat = parseFloat(streetViewElement.getAttribute('data-lat'));
    const lng = parseFloat(streetViewElement.getAttribute('data-lng'));
    
    if (isNaN(lat) || isNaN(lng)) {
        streetViewElement.innerHTML = `
            <div class="alert alert-warning">
                <i class="fas fa-exclamation-triangle"></i>
                Street view is not available for this location due to missing coordinates.
            </div>
        `;
        return;
    }
    
    streetViewElement.innerHTML = `
        <div class="text-center p-4 bg-light rounded">
            <svg width="100" height="100" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="feather feather-camera mb-3 text-muted">
                <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path>
                <circle cx="12" cy="13" r="4"></circle>
            </svg>
            <h5>Street View</h5>
            <p class="text-muted">Street view would be displayed here using the property's coordinates.</p>
            <p><strong>Coordinates:</strong> ${lat.toFixed(6)}, ${lng.toFixed(6)}</p>
        </div>
    `;
}

/**
 * Handle exporting property data
 * @param {string} format - Export format (pdf, csv, etc.)
 * @param {number} propertyId - Property ID
 */
function exportPropertyData(format, propertyId) {
    if (!propertyId) {
        alert('Property ID is required for export');
        return;
    }
    
    // In a real implementation, this would call an API endpoint to generate the export
    // For this implementation, we'll show an alert
    
    alert(`Exporting property data in ${format.toUpperCase()} format. This feature would download property details in the requested format.`);
}
