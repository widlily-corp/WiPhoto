# WiPhoto Development Roadmap

This document outlines planned features and enhancements for WiPhoto.

## Version 1.5.0 - Geolocation & Metadata Enhancement

### Geotag Support
- **GPS Data Display**: Show location information from EXIF GPS tags
- **Map Integration**: Display photo locations on interactive map
  - Library: `folium` or `plotly` for map visualization
  - Click on map to see photos taken at that location
- **Geotag Editing**: Add/modify GPS coordinates
- **Location-based Collections**: Auto-organize photos by location
- **Reverse Geocoding**: Convert coordinates to place names (city, country)
  - Library: `geopy` with OpenStreetMap/Google Maps API

**Implementation Priority**: HIGH

## Version 1.6.0 - AI-Powered Recognition

### Face Detection & Recognition
- **Face Detection**: Identify faces in photos
  - Library: `face_recognition` or `dlib`
  - Alternative: `opencv-python` Haar Cascades (lighter weight)
- **Face Recognition**: Group photos by person
- **Auto-tagging**: Assign names to recognized faces
- **Privacy Mode**: Option to blur faces in exports

**Implementation Priority**: MEDIUM

### Animal Detection
- **Pet Recognition**: Detect and classify common pets (dogs, cats, etc.)
  - Library: `tensorflow` with pre-trained models (MobileNet, YOLO)
  - Alternative: `pytorch` with torchvision models
- **Wildlife Detection**: Identify wildlife in nature photography
- **Smart Collections**: "Photos with Pets", "Wildlife Photos"
- **Species Classification**: Identify specific animal species (advanced)

**Implementation Priority**: MEDIUM

## Version 1.7.0 - Document Scanning

### Document Processing
- **Auto Document Detection**:
  - Detect document boundaries automatically
  - Library: `opencv-python` for edge detection and perspective transform
- **Perspective Correction**:
  - Auto-straighten scanned documents
  - Dewarp curved pages
- **OCR Integration**:
  - Extract text from scanned documents
  - Library: `pytesseract` (Tesseract OCR)
  - Support multiple languages
- **PDF Export**: Convert scanned pages to searchable PDF
  - Library: `reportlab` or `fpdf`

**Implementation Priority**: LOW

## Version 2.0.0 - Advanced Features

### Cloud Integration
- **Backup & Sync**: Cloud storage integration (Google Drive, OneDrive, Dropbox)
- **Photo Sharing**: Share collections with others
- **Cross-device Sync**: Sync edits across devices

### Export Enhancements
- **Batch Export**: Export multiple images with applied edits
- **Preset System**: Save and apply editing presets
- **Watermarking**: Add custom watermarks to exports
- **HEIC/AVIF Support**: Modern format support

### Performance Improvements
- **GPU Acceleration**: Use GPU for faster image processing
  - Library: `cupy` for CUDA support
- **Better Caching**: Smarter preview cache management
- **Lazy Loading**: Load thumbnails on-demand for huge collections

### UI/UX Enhancements
- **Internationalization**: Multi-language support (English, Russian, etc.)
- **Custom Themes**: User-selectable color themes
- **Keyboard Customization**: Customizable hotkeys
- **Grid/Timeline Views**: Alternative visualization modes

## Technical Debt & Improvements

### Code Quality
- **Type Hints**: Add complete type annotations throughout codebase
- **Unit Tests**: Comprehensive test coverage
  - Framework: `pytest`
- **Documentation**: API documentation with `sphinx`
- **Logging**: Replace print statements with proper logging

### Architecture
- **Plugin System**: Allow third-party extensions
- **Database Backend**: SQLite for metadata instead of file-based storage
- **Async Operations**: Use asyncio for non-blocking operations

### Cross-Platform
- **Linux Full Support**:
  - Replace ExifTool.exe with cross-platform solution
  - Test on Ubuntu, Fedora, Arch
- **macOS Support**: Build and test on macOS
  - Universal binary for M1/M2 chips

## Library Dependencies for Planned Features

```python
# Geolocation
geopy>=2.3.0
folium>=0.14.0  # or plotly>=5.0.0

# Face/Animal Detection
face-recognition>=1.3.0
dlib>=19.24.0
# OR
tensorflow>=2.13.0
opencv-python>=4.8.0

# Document Scanning
pytesseract>=0.3.10
reportlab>=4.0.0

# Cloud Integration
google-api-python-client>=2.0.0
dropbox>=11.0.0

# GPU Acceleration
cupy>=12.0.0  # CUDA required
```

## Timeline (Estimated)

- **Q2 2026**: v1.5.0 (Geotags)
- **Q3 2026**: v1.6.0 (AI Recognition)
- **Q4 2026**: v1.7.0 (Document Scanning)
- **Q1 2027**: v2.0.0 (Advanced Features)

---

*This roadmap is subject to change based on user feedback and technical constraints.*
