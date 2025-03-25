# Property Mapper Application

A web-based mapping application that provides comprehensive property data analysis with advanced visualization and user-centric design.

## Key Features

- Advanced property mapping and geospatial analysis
- Robust authentication and security features
- Machine learning-powered property insights
- Multi-source data integration (Excel, KML, OneDrive)
- Efficient handling of large shapefiles and numerous map layers

## Technical Highlights

- Custom layer management system with categorization and pagination
- Advanced progress tracking for large files
- Multi-level caching system (memory + file-based) to avoid reprocessing large shapefiles
- Zoom-specific feature limiting (5,000-25,000 features based on zoom level)
- OneDrive integration for storing and processing large shapefiles

## Installation

1. Clone the repository
2. Install the required dependencies:
   ```
   pip install django psycopg2-binary pandas numpy scikit-learn matplotlib tensorflow openpyxl django-leaflet pyshp
   ```
3. Run migrations:
   ```
   python manage.py makemigrations
   python manage.py migrate
   ```
4. Start the development server:
   ```
   python manage.py runserver 0.0.0.0:5000
   ```

## Project Structure

- `maps/` - Core Django app containing models, views, and business logic
- `property_mapper/` - Project settings and configuration
- `static/` - Static files (JS, CSS, images)
  - `static/js/layer_manager.js` - Custom layer management component
  - `static/js/map.js` - Map initialization and interaction
- `templates/` - HTML templates
- `media/` - User-uploaded content (property files, map layers)

## Map Layer Management

The application includes a custom layer management system designed to handle a large number of map layers efficiently:

1. **Layer Categorization**: Layers are grouped by type (base maps, shapefiles, GeoJSON, etc.)
2. **Pagination**: Large sets of layers can be paginated for easier navigation
3. **Search and Filtering**: Users can search for specific layers by name
4. **Memory Optimization**: Inactive layers are unloaded to save memory
5. **Progress Tracking**: Visual indicators show loading progress for large files
6. **Smart Feature Limiting**: The number of features displayed is adjusted based on zoom level

## Shapefile Optimization

Large shapefiles are handled through several optimization techniques:

1. **Multi-level Caching**: 
   - Memory cache for small datasets
   - File-based cache for large datasets
   - Zoom-specific variant caching
   
2. **Feature Limiting**:
   - 5,000 features when zoomed out
   - Up to 25,000 features when zoomed in
   - Dynamic simplification based on zoom level
   
3. **Progressive Loading**:
   - Stream-based loading with progress indication
   - Chunk-based processing for very large files

## OneDrive Integration

For very large files that exceed local storage limitations, the application includes OneDrive integration:

1. Files are uploaded to OneDrive
2. The application stores metadata (file ID, name, URL) in the database
3. Files are downloaded on-demand when needed for processing
4. Processed results are cached locally to avoid repeated downloads