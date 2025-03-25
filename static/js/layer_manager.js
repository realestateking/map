/**
 * Advanced Layer Manager for handling tons of map layers efficiently
 * This module provides a custom layer control with:
 * - Layer categorization
 * - Pagination for large layer sets
 * - Searching and filtering
 * - Memory optimization for inactive layers
 */

/**
 * Custom Layer Manager Class
 */
class LayerManager {
    /**
     * Initialize the Layer Manager
     * @param {L.Map} map - Leaflet map instance
     * @param {Object} baseMaps - Base map layers
     * @param {Object} options - Configuration options
     */
    constructor(map, baseMaps, options = {}) {
        this.map = map;
        this.baseMaps = baseMaps;
        this.overlayMaps = {};
        this.visibleLayers = {};
        this.categories = {};
        this.loadingLayers = {};
        
        // Default options
        this.options = {
            position: 'topleft',
            collapsed: true,
            layersPerPage: 15,
            autoZoomPanning: true,
            sortLayers: true,
            ...options
        };
        
        // Current state
        this.state = {
            currentPage: 1,
            searchTerm: '',
            activeCategory: null,
            expandedCategories: {},
            filters: {}
        };
        
        // Create the control container
        this.container = L.DomUtil.create('div', 'leaflet-control leaflet-control-layers custom-layer-control');
        this.container.setAttribute('aria-haspopup', true);
        
        if (this.options.collapsed) {
            L.DomUtil.addClass(this.container, 'leaflet-control-layers-collapsed');
            
            // Toggle button
            this.toggleButton = L.DomUtil.create('a', 'leaflet-control-layers-toggle', this.container);
            this.toggleButton.href = '#';
            this.toggleButton.title = 'Layers';
            
            // Toggle functionality
            L.DomEvent.on(this.toggleButton, 'click', (e) => {
                L.DomEvent.preventDefault(e);
                if (L.DomUtil.hasClass(this.container, 'leaflet-control-layers-expanded')) {
                    this.collapse();
                } else {
                    this.expand();
                }
            });
            
            // Collapse on map click
            this.map.on('click', () => this.collapse());
        }
        
        // Create the form element
        this.form = L.DomUtil.create('form', 'leaflet-control-layers-list', this.container);
        
        // Prevent clicks from propagating to map
        L.DomEvent.disableClickPropagation(this.container);
        L.DomEvent.disableScrollPropagation(this.container);
        
        // Add search box
        this.createSearchBox();
        
        // Setup base layers section
        this.baseLayersSection = L.DomUtil.create('div', 'leaflet-control-layers-base', this.form);
        this.baseLayersSection.innerHTML = '<div class="layer-category-title">Base Maps</div>';
        this.baseLayersContent = L.DomUtil.create('div', 'layer-category-content', this.baseLayersSection);
        
        // Add base layers
        this.addBaseLayers(baseMaps);
        
        // Setup overlay layers section
        this.overlaysSection = L.DomUtil.create('div', 'leaflet-control-layers-overlays', this.form);
        
        // Create pagination controls
        this.createPagination();
        
        // Add the control to the map
        return this;
    }
    
    /**
     * Create search box for filtering layers
     */
    createSearchBox() {
        const searchContainer = L.DomUtil.create('div', 'layer-search-container', this.form);
        this.searchInput = L.DomUtil.create('input', 'layer-search', searchContainer);
        this.searchInput.type = 'text';
        this.searchInput.placeholder = 'Search layers...';
        
        // Add search functionality
        L.DomEvent.on(this.searchInput, 'input', this.debounce((e) => {
            this.state.searchTerm = e.target.value.toLowerCase();
            this.state.currentPage = 1; // Reset to first page on search
            this.renderLayers();
        }, 300));
    }
    
    /**
     * Create pagination controls
     */
    createPagination() {
        this.paginationContainer = L.DomUtil.create('div', 'layer-pagination', this.form);
        this.paginationContainer.style.display = 'none'; // Hide initially
        
        this.prevButton = L.DomUtil.create('button', 'pagination-button prev-button', this.paginationContainer);
        this.prevButton.innerHTML = '&laquo; Prev';
        this.prevButton.type = 'button';
        
        this.pageInfo = L.DomUtil.create('span', 'page-info', this.paginationContainer);
        
        this.nextButton = L.DomUtil.create('button', 'pagination-button next-button', this.paginationContainer);
        this.nextButton.innerHTML = 'Next &raquo;';
        this.nextButton.type = 'button';
        
        // Add event listeners
        L.DomEvent.on(this.prevButton, 'click', (e) => {
            L.DomEvent.preventDefault(e);
            if (this.state.currentPage > 1) {
                this.state.currentPage--;
                this.renderLayers();
            }
        });
        
        L.DomEvent.on(this.nextButton, 'click', (e) => {
            L.DomEvent.preventDefault(e);
            const totalPages = this.calculateTotalPages();
            if (this.state.currentPage < totalPages) {
                this.state.currentPage++;
                this.renderLayers();
            }
        });
    }
    
    /**
     * Add base layers to the control
     * @param {Object} baseMaps - Base layer definitions
     */
    addBaseLayers(baseMaps) {
        this.baseLayersContent.innerHTML = '';
        
        // Track selected base layer
        let hasSelectedLayer = false;
        
        // Add each base layer
        Object.entries(baseMaps).forEach(([name, layer]) => {
            const isSelected = this.map.hasLayer(layer);
            if (isSelected) hasSelectedLayer = true;
            
            const layerItem = this.createLayerItem(name, layer, 'base', isSelected);
            this.baseLayersContent.appendChild(layerItem);
        });
        
        // If no layer is selected, select the first one
        if (!hasSelectedLayer && Object.keys(baseMaps).length > 0) {
            const firstLayer = Object.values(baseMaps)[0];
            firstLayer.addTo(this.map);
        }
    }
    
    /**
     * Add overlay layers to the control with categorization
     * @param {Object} overlays - Overlay layer definitions
     */
    addOverlays(overlays) {
        // Store the layers
        Object.entries(overlays).forEach(([name, layer]) => {
            // Get or create category
            const category = layer.options?.category || 'Other';
            
            if (!this.categories[category]) {
                this.categories[category] = {};
            }
            
            this.categories[category][name] = layer;
            this.overlayMaps[name] = layer;
            
            // Track if initially visible
            if (this.map.hasLayer(layer)) {
                this.visibleLayers[name] = true;
            }
        });
        
        // Render all layers
        this.renderLayers();
    }
    
    /**
     * Add a single overlay layer
     * @param {L.Layer} layer - Layer to add
     * @param {string} name - Name of the layer
     * @param {Object} options - Additional options
     */
    addOverlay(layer, name, options = {}) {
        // Get or create category
        const category = options.category || layer.options?.category || 'Other';
        
        if (!this.categories[category]) {
            this.categories[category] = {};
        }
        
        this.categories[category][name] = layer;
        this.overlayMaps[name] = layer;
        
        // Add to map if visible by default
        if (options.addToMap) {
            layer.addTo(this.map);
            this.visibleLayers[name] = true;
        }
        
        // Re-render if expanded
        if (L.DomUtil.hasClass(this.container, 'leaflet-control-layers-expanded')) {
            this.renderLayers();
        }
    }
    
    /**
     * Remove a layer from the control
     * @param {L.Layer|string} layer - Layer or layer name to remove
     */
    removeLayer(layer) {
        let layerName = layer;
        
        // If passed a layer object, find its name
        if (typeof layer !== 'string') {
            Object.entries(this.overlayMaps).forEach(([name, l]) => {
                if (l === layer) layerName = name;
            });
        }
        
        // Remove from map if it's there
        if (this.overlayMaps[layerName]) {
            if (this.map.hasLayer(this.overlayMaps[layerName])) {
                this.map.removeLayer(this.overlayMaps[layerName]);
            }
            
            // Remove from all collections
            delete this.overlayMaps[layerName];
            delete this.visibleLayers[layerName];
            
            // Remove from categories
            Object.keys(this.categories).forEach(category => {
                if (this.categories[category][layerName]) {
                    delete this.categories[category][layerName];
                }
            });
            
            // Clean up empty categories
            Object.keys(this.categories).forEach(category => {
                if (Object.keys(this.categories[category]).length === 0) {
                    delete this.categories[category];
                }
            });
            
            // Re-render if expanded
            if (L.DomUtil.hasClass(this.container, 'leaflet-control-layers-expanded')) {
                this.renderLayers();
            }
        }
    }
    
    /**
     * Set a layer as loading
     * @param {string} layerName - Name of the layer
     * @param {boolean} isLoading - Whether the layer is loading
     */
    /**
     * Set a layer as loading
     * @param {string} layerName - Name of the layer
     * @param {boolean} isLoading - Whether the layer is loading
     * @param {Object} loadingInfo - Additional loading information (percentage, feature count, etc.)
     */
    setLayerLoading(layerName, isLoading, loadingInfo = {}) {
        if (isLoading) {
            this.loadingLayers[layerName] = {
                isLoading: true,
                ...loadingInfo
            };
        } else {
            delete this.loadingLayers[layerName];
        }
        
        // Update UI if rendered
        const layerItem = document.querySelector(`.layer-item[data-name="${layerName}"]`);
        if (layerItem) {
            let loadingIndicator = layerItem.querySelector('.layer-loading');
            
            if (isLoading) {
                if (!loadingIndicator) {
                    loadingIndicator = document.createElement('div');
                    loadingIndicator.className = 'layer-loading';
                    layerItem.appendChild(loadingIndicator);
                }
                
                // Update loading indicator with loading info
                if (loadingInfo.percent) {
                    loadingIndicator.title = `Loading: ${loadingInfo.percent}% complete`;
                    
                    // Optional: Add a mini progress bar inside the spinner
                    loadingIndicator.style.background = `conic-gradient(
                        var(--primary-color) ${loadingInfo.percent * 3.6}deg, 
                        rgba(0, 0, 0, 0.1) ${loadingInfo.percent * 3.6}deg
                    )`;
                }
                
                loadingIndicator.style.display = 'block';
            } else if (loadingIndicator) {
                loadingIndicator.style.display = 'none';
            }
        }
    }
    
    /**
     * Create a layer item element
     * @param {string} name - Layer name
     * @param {L.Layer} layer - Layer object
     * @param {string} type - 'base' or 'overlay'
     * @param {boolean} checked - Whether the layer is initially selected
     * @returns {HTMLElement} - The layer item element
     */
    createLayerItem(name, layer, type, checked = false) {
        const item = L.DomUtil.create('div', 'layer-item');
        item.setAttribute('data-name', name);
        
        const input = L.DomUtil.create('input', 'layer-checkbox', item);
        input.type = type === 'base' ? 'radio' : 'checkbox';
        input.name = type === 'base' ? 'leaflet-base-layers' : 'leaflet-overlay-layers';
        input.checked = checked;
        
        const label = L.DomUtil.create('label', '', item);
        label.innerHTML = name;
        
        // Add loading indicator
        const loadingIndicator = L.DomUtil.create('span', 'layer-loading', item);
        loadingIndicator.style.display = this.loadingLayers[name] ? 'block' : 'none';
        
        // Handle layer toggling
        L.DomEvent.on(input, 'change', () => {
            if (type === 'base') {
                // For base layers, remove all other base layers first
                Object.values(this.baseMaps).forEach(baseLayer => {
                    if (this.map.hasLayer(baseLayer) && baseLayer !== layer) {
                        this.map.removeLayer(baseLayer);
                    }
                });
                
                if (input.checked) {
                    this.map.addLayer(layer);
                }
            } else {
                // For overlay layers
                if (input.checked) {
                    this.map.addLayer(layer);
                    this.visibleLayers[name] = true;
                    
                    // For large layers, show loading indicator
                    if (layer.options && layer.options.isLarge) {
                        this.setLayerLoading(name, true);
                        
                        // Clear loading state after a timeout (or use events if available)
                        setTimeout(() => {
                            this.setLayerLoading(name, false);
                        }, 2000);
                    }
                } else {
                    this.map.removeLayer(layer);
                    delete this.visibleLayers[name];
                }
            }
        });
        
        return item;
    }
    
    /**
     * Render all layers with pagination and filtering
     */
    renderLayers() {
        // Clear overlays section
        this.overlaysSection.innerHTML = '';
        
        // Get all categories
        const categories = Object.keys(this.categories).sort();
        
        // Filter layers based on search term
        const filteredCategories = {};
        let totalFilteredLayers = 0;
        
        categories.forEach(category => {
            filteredCategories[category] = {};
            
            Object.entries(this.categories[category]).forEach(([name, layer]) => {
                if (!this.state.searchTerm || name.toLowerCase().includes(this.state.searchTerm)) {
                    filteredCategories[category][name] = layer;
                    totalFilteredLayers++;
                }
            });
        });
        
        // Handle pagination
        const layersPerPage = this.options.layersPerPage;
        const totalPages = Math.ceil(totalFilteredLayers / layersPerPage);
        
        // Update pagination controls
        this.paginationContainer.style.display = totalPages > 1 ? 'flex' : 'none';
        this.pageInfo.textContent = `Page ${this.state.currentPage} of ${totalPages}`;
        this.prevButton.disabled = this.state.currentPage <= 1;
        this.nextButton.disabled = this.state.currentPage >= totalPages;
        
        // Calculate start and end indices for current page
        const startIdx = (this.state.currentPage - 1) * layersPerPage;
        let endIdx = startIdx + layersPerPage;
        let currentIdx = 0;
        
        // Create a category-based display
        categories.forEach(category => {
            // Skip empty categories
            if (Object.keys(filteredCategories[category]).length === 0) {
                return;
            }
            
            // Create category section
            const categorySection = L.DomUtil.create('div', 'layer-category', this.overlaysSection);
            
            // Category title with toggle
            const categoryTitle = L.DomUtil.create('div', 'layer-category-title', categorySection);
            categoryTitle.innerHTML = `${category} <span class="count">(${Object.keys(filteredCategories[category]).length})</span>`;
            categoryTitle.innerHTML += '<span class="toggle">▾</span>';
            
            // Category content (collapsible)
            const categoryContent = L.DomUtil.create('div', 'layer-category-content', categorySection);
            
            // Check if category should be expanded
            if (!this.state.expandedCategories[category] && category !== this.state.activeCategory) {
                categoryContent.style.maxHeight = '0';
                categoryContent.style.overflow = 'hidden';
                categoryTitle.querySelector('.toggle').innerHTML = '▸';
            }
            
            // Add click handler for category toggle
            L.DomEvent.on(categoryTitle, 'click', (e) => {
                L.DomEvent.preventDefault(e);
                L.DomEvent.stopPropagation(e);
                
                if (categoryContent.style.maxHeight === '0px') {
                    // Expand
                    categoryContent.style.maxHeight = '300px';
                    categoryContent.style.overflow = 'auto';
                    categoryTitle.querySelector('.toggle').innerHTML = '▾';
                    this.state.expandedCategories[category] = true;
                } else {
                    // Collapse
                    categoryContent.style.maxHeight = '0';
                    categoryContent.style.overflow = 'hidden';
                    categoryTitle.querySelector('.toggle').innerHTML = '▸';
                    delete this.state.expandedCategories[category];
                }
            });
            
            // Get layers for this category
            const categoryLayers = filteredCategories[category];
            
            // Sort layers if option is set
            let layerEntries = Object.entries(categoryLayers);
            if (this.options.sortLayers) {
                layerEntries.sort((a, b) => a[0].localeCompare(b[0]));
            }
            
            // Add layers for this category
            layerEntries.forEach(([name, layer]) => {
                // Skip layers that aren't in the current page range
                if (currentIdx < startIdx || currentIdx >= endIdx) {
                    currentIdx++;
                    return;
                }
                
                const isSelected = this.map.hasLayer(layer);
                const layerItem = this.createLayerItem(name, layer, 'overlay', isSelected);
                categoryContent.appendChild(layerItem);
                
                currentIdx++;
            });
        });
    }
    
    /**
     * Debounce function for search
     * @param {Function} func - Function to debounce
     * @param {number} wait - Wait time in ms
     * @returns {Function} - Debounced function
     */
    debounce(func, wait) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }
    
    /**
     * Calculate total pages based on current filters
     * @returns {number} - Total number of pages
     */
    calculateTotalPages() {
        let totalLayers = 0;
        
        // Count filtered layers
        Object.keys(this.categories).forEach(category => {
            Object.keys(this.categories[category]).forEach(name => {
                if (!this.state.searchTerm || name.toLowerCase().includes(this.state.searchTerm)) {
                    totalLayers++;
                }
            });
        });
        
        return Math.ceil(totalLayers / this.options.layersPerPage);
    }
    
    /**
     * Expand the control
     */
    expand() {
        L.DomUtil.addClass(this.container, 'leaflet-control-layers-expanded');
    }
    
    /**
     * Collapse the control
     */
    collapse() {
        L.DomUtil.removeClass(this.container, 'leaflet-control-layers-expanded');
    }
    
    /**
     * Add the control to a map
     * @param {L.Map} map - Map to add control to
     * @returns {LayerManager} - This instance
     */
    addTo(map) {
        this.remove();
        this._map = map;
        
        const controlContainer = map._controlContainer;
        const controlCorner = controlContainer.querySelector(`.leaflet-${this.options.position}`);
        
        controlCorner.appendChild(this.container);
        return this;
    }
    
    /**
     * Remove the control from its map
     */
    remove() {
        if (!this._map) {
            return;
        }
        
        this.container.remove();
        this._map = null;
        return this;
    }
}

// Create a global factory function to create layer managers
function createLayerManager(map, baseLayers, options) {
    return new LayerManager(map, baseLayers, options);
}