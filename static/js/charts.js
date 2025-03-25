/**
 * Charts and data visualization for Property Mapper application
 * Uses Chart.js for creating charts and visualizations
 */

/**
 * Initialize a pie chart showing property types distribution
 * @param {string} elementId - Canvas element ID
 * @param {object} data - Data object with labels and values
 */
function createPropertyTypeChart(elementId, data) {
    const ctx = document.getElementById(elementId).getContext('2d');
    
    return new Chart(ctx, {
        type: 'pie',
        data: {
            labels: data.labels,
            datasets: [{
                data: data.values,
                backgroundColor: [
                    '#4e73df',
                    '#1cc88a',
                    '#36b9cc',
                    '#f6c23e',
                    '#e74a3b',
                    '#6f42c1',
                    '#fd7e14',
                    '#20c9a6',
                    '#5a5c69'
                ],
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom'
                },
                title: {
                    display: true,
                    text: 'Property Types Distribution'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.raw || 0;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = Math.round((value / total) * 100);
                            return `${label}: ${value} (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });
}

/**
 * Initialize a bar chart showing quality score distribution
 * @param {string} elementId - Canvas element ID
 * @param {object} data - Data object with labels and values
 */
function createQualityScoreChart(elementId, data) {
    const ctx = document.getElementById(elementId).getContext('2d');
    
    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.labels,
            datasets: [{
                label: 'Number of Properties',
                data: data.values,
                backgroundColor: [
                    '#4CAF50',  // Excellent - Green
                    '#8BC34A',  // Good - Light Green
                    '#FFC107',  // Average - Amber
                    '#FF9800',  // Fair - Orange
                    '#F44336',  // Poor - Red
                    '#9E9E9E'   // Unknown - Gray
                ],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        precision: 0
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                title: {
                    display: true,
                    text: 'Property Quality Distribution'
                }
            }
        }
    });
}

/**
 * Initialize a line chart showing property values by year built
 * @param {string} elementId - Canvas element ID
 * @param {object} data - Data object with labels and values
 */
function createPropertyValueChart(elementId, data) {
    const ctx = document.getElementById(elementId).getContext('2d');
    
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.years,
            datasets: [{
                label: 'Average Value ($)',
                data: data.values,
                fill: false,
                borderColor: '#4e73df',
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: false,
                    ticks: {
                        callback: function(value) {
                            return '$' + value.toLocaleString();
                        }
                    }
                }
            },
            plugins: {
                title: {
                    display: true,
                    text: 'Property Value by Year Built'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const value = context.raw;
                            return 'Average Value: $' + value.toLocaleString();
                        }
                    }
                }
            }
        }
    });
}

/**
 * Initialize a radar chart comparing property attributes
 * @param {string} elementId - Canvas element ID
 * @param {object} data - Data object with attributes and values
 */
function createPropertyComparisonChart(elementId, data) {
    const ctx = document.getElementById(elementId).getContext('2d');
    
    return new Chart(ctx, {
        type: 'radar',
        data: {
            labels: data.attributes,
            datasets: data.properties.map((property, index) => {
                const colors = ['#4e73df', '#1cc88a', '#e74a3b'];
                return {
                    label: property.name,
                    data: property.values,
                    backgroundColor: hexToRgba(colors[index % colors.length], 0.2),
                    borderColor: colors[index % colors.length],
                    pointBackgroundColor: colors[index % colors.length],
                    pointBorderColor: '#fff'
                };
            })
        },
        options: {
            responsive: true,
            scales: {
                r: {
                    beginAtZero: true,
                    max: 100
                }
            },
            plugins: {
                title: {
                    display: true,
                    text: 'Property Comparison'
                }
            }
        }
    });
}

/**
 * Initialize an area chart showing property area breakdown
 * @param {string} elementId - Canvas element ID
 * @param {object} data - Data object with building and land area
 */
function createAreaComparisonChart(elementId, data) {
    const ctx = document.getElementById(elementId).getContext('2d');
    
    const buildingArea = data.buildingArea;
    const remainingLandArea = data.landArea - data.buildingArea;
    
    return new Chart(ctx, {
        type: 'pie',
        data: {
            labels: ['Building Area', 'Remaining Land Area'],
            datasets: [{
                data: [buildingArea, remainingLandArea],
                backgroundColor: [
                    '#4e73df',
                    '#1cc88a'
                ],
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom'
                },
                title: {
                    display: true,
                    text: 'Property Area Comparison'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.raw || 0;
                            return `${label}: ${value.toLocaleString()} m²`;
                        }
                    }
                }
            }
        }
    });
}

/**
 * Create a horizontal bar chart showing nearby property values
 * @param {string} elementId - Canvas element ID
 * @param {object} data - Data object with properties and values
 */
function createNearbyPropertiesChart(elementId, data) {
    const ctx = document.getElementById(elementId).getContext('2d');
    
    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.properties.map(p => p.name),
            datasets: [{
                label: 'Assessed Value ($)',
                data: data.properties.map(p => p.value),
                backgroundColor: data.properties.map((p, i) => 
                    p.isSelected ? '#4e73df' : '#1cc88a'
                ),
                borderWidth: 1
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            scales: {
                x: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return '$' + value.toLocaleString();
                        }
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                title: {
                    display: true,
                    text: 'Nearby Property Values'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const value = context.raw;
                            return 'Value: $' + value.toLocaleString();
                        }
                    }
                }
            }
        }
    });
}

/**
 * Create a gauge chart for property quality score
 * @param {string} elementId - Canvas element ID
 * @param {number} score - Quality score (0-100)
 */
function createQualityGaugeChart(elementId, score) {
    const ctx = document.getElementById(elementId).getContext('2d');
    
    // Convert score to a 0-1 range for gauge
    const normalizedScore = score / 100;
    
    return new Chart(ctx, {
        type: 'doughnut',
        data: {
            datasets: [{
                data: [score, 100 - score],
                backgroundColor: [
                    getScoreColor(score),
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
            id: 'gauge-center-text',
            afterDraw: (chart) => {
                const width = chart.width;
                const height = chart.height;
                const ctx = chart.ctx;
                
                ctx.restore();
                ctx.font = 'bold 24px Arial';
                ctx.textBaseline = 'middle';
                ctx.textAlign = 'center';
                ctx.fillStyle = getScoreColor(score);
                ctx.fillText(score, width / 2, height - 20);
                
                ctx.font = '16px Arial';
                ctx.fillStyle = '#666';
                ctx.fillText(getQualityLabel(score), width / 2, height - 45);
                
                ctx.save();
            }
        }]
    });
}

/**
 * Get color for quality score
 * @param {number} score - Quality score (0-100)
 * @returns {string} - CSS color string
 */
function getScoreColor(score) {
    if (score >= 80) return '#4CAF50';      // Excellent - Green
    if (score >= 60) return '#8BC34A';      // Good - Light Green
    if (score >= 40) return '#FFC107';      // Average - Amber
    if (score >= 20) return '#FF9800';      // Fair - Orange
    return '#F44336';                       // Poor - Red
}

/**
 * Get label for quality score
 * @param {number} score - Quality score (0-100)
 * @returns {string} - Quality label
 */
function getQualityLabel(score) {
    if (score >= 80) return 'Excellent';
    if (score >= 60) return 'Good';
    if (score >= 40) return 'Average';
    if (score >= 20) return 'Fair';
    return 'Poor';
}

/**
 * Convert hex color to rgba
 * @param {string} hex - Hex color code
 * @param {number} alpha - Alpha value (0-1)
 * @returns {string} - RGBA color string
 */
function hexToRgba(hex, alpha = 1) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
