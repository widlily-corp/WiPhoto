// ═══ WiPhoto Geo-Map Module (Offline Leaflet + Supercluster) ═══

const WiPhotoMap = (() => {
  let mapInstance = null;
  let superclusterInstance = null;
  let markerLayerGroup = null;
  let currentGeoPoints = [];
  let isInitialized = false;

  // Validate latitude and longitude bounds
  function isValidCoordinate(lat, lon) {
    if (typeof lat !== 'number' || typeof lon !== 'number') return false;
    if (isNaN(lat) || isNaN(lon)) return false;
    return lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180;
  }

  // Convert photo object into GeoJSON Point Feature for Supercluster
  function photoToGeoJsonPoint(photo) {
    if (!photo || !photo.gps_location || !Array.isArray(photo.gps_location) || photo.gps_location.length < 2) {
      return null;
    }
    const [lat, lon] = photo.gps_location;
    if (!isValidCoordinate(lat, lon)) {
      return null;
    }

    return {
      type: 'Feature',
      properties: {
        id: photo.id || photo.path,
        path: photo.path,
        filename: photo.filename || 'Photo',
        thumbnail: photo.thumbnail || '',
        rating: photo.rating || 0,
        gps_location: [lat, lon]
      },
      geometry: {
        type: 'Point',
        coordinates: [lon, lat] // GeoJSON format: [longitude, latitude]
      }
    };
  }

  // Initialize Leaflet Map instance
  function initMapContainer() {
    const container = document.getElementById('map-container');
    if (!container) return null;

    if (!mapInstance && typeof L !== 'undefined') {
      mapInstance = L.map('map-container', {
        center: [55.7558, 37.6173], // Default center: Moscow
        zoom: 4,
        zoomControl: true
      });

      // Add local tile layer
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors'
      }).addTo(mapInstance);

      markerLayerGroup = L.layerGroup().addTo(mapInstance);

      // Register map movement listeners for smooth cluster updates
      mapInstance.on('moveend zoomend', () => {
        updateClusters();
      });

      isInitialized = true;
    }

    return mapInstance;
  }

  // Initialize Supercluster spatial index
  function initSupercluster() {
    if (typeof Supercluster !== 'undefined') {
      superclusterInstance = new Supercluster({
        radius: 45,
        maxZoom: 16,
        minZoom: 0,
        extent: 512,
        nodeSize: 64
      });
    }
  }

  // Load photos, process EXIF GPS coords, and render map
  function render(photos) {
    initMapContainer();
    if (!mapInstance) return;

    if (!superclusterInstance) {
      initSupercluster();
    }

    const photoList = Array.isArray(photos) ? photos : (typeof Gallery !== 'undefined' ? Gallery.getFilteredImages() : []);
    
    // Extract valid GeoJSON points
    currentGeoPoints = [];
    const bounds = [];

    photoList.forEach(photo => {
      const point = photoToGeoJsonPoint(photo);
      if (point) {
        currentGeoPoints.push(point);
        bounds.push([photo.gps_location[0], photo.gps_location[1]]);
      }
    });

    // Load points into Supercluster
    if (superclusterInstance) {
      superclusterInstance.load(currentGeoPoints);
    }

    // Fit map bounds to show all geotagged photo points
    if (bounds.length > 0) {
      mapInstance.fitBounds(bounds, { padding: [40, 40] });
    } else {
      updateClusters();
    }

    // Invalidate map size to prevent incomplete container rendering
    setTimeout(() => {
      if (mapInstance) {
        mapInstance.invalidateSize();
      }
    }, 150);
  }

  // Update visible clusters and markers based on current viewport & zoom level
  function updateClusters() {
    if (!mapInstance || !markerLayerGroup) return;

    markerLayerGroup.clearLayers();

    if (!superclusterInstance || currentGeoPoints.length === 0) return;

    const bounds = mapInstance.getBounds();
    const bbox = [
      bounds.getSouthWest().lng,
      bounds.getSouthWest().lat,
      bounds.getNorthEast().lng,
      bounds.getNorthEast().lat
    ];
    const zoom = Math.floor(mapInstance.getZoom());

    const clusters = superclusterInstance.getClusters(bbox, zoom);

    clusters.forEach(feature => {
      const [lon, lat] = feature.geometry.coordinates;

      if (feature.properties.cluster) {
        // Render Cluster Badge
        const count = feature.properties.point_count;
        const sizeClass = count < 10 ? 'wiphoto-cluster-small' : (count < 100 ? 'wiphoto-cluster-medium' : 'wiphoto-cluster-large');
        const diameter = Math.min(60, Math.max(32, 28 + Math.log2(count) * 4));

        const clusterIcon = L.divIcon({
          html: `<div class="wiphoto-cluster-marker ${sizeClass}" style="width: ${diameter}px; height: ${diameter}px; line-height: ${diameter}px;">${feature.properties.point_count_abbreviated || count}</div>`,
          className: 'wiphoto-cluster-icon',
          iconSize: [diameter, diameter],
          iconAnchor: [diameter / 2, diameter / 2]
        });

        const clusterMarker = L.marker([lat, lon], { icon: clusterIcon });

        // Click to expand cluster smoothly
        clusterMarker.on('click', () => {
          const expansionZoom = superclusterInstance.getClusterExpansionZoom(feature.properties.cluster_id);
          mapInstance.setView([lat, lon], Math.min(18, expansionZoom));
        });

        markerLayerGroup.addLayer(clusterMarker);

      } else {
        // Render Individual Photo Marker
        const photo = feature.properties;
        const thumbUrl = photo.thumbnail ? Utils.assetUrl(photo.thumbnail) : '';

        const photoIcon = L.divIcon({
          html: thumbUrl
            ? `<div class="wiphoto-photo-marker" style="background-image: url('${thumbUrl}');"></div>`
            : `<div class="wiphoto-photo-marker" style="background: #6366f1;"></div>`,
          className: 'wiphoto-photo-icon',
          iconSize: [32, 32],
          iconAnchor: [16, 16]
        });

        const photoMarker = L.marker([lat, lon], { icon: photoIcon });

        // Popup HTML with zero-copy thumbnail preview
        const zeroCopyUrl = photo.path ? Utils.assetUrl(photo.path) : thumbUrl;
        const popupHtml = `
          <div class="map-popup-card">
            <img src="${thumbUrl || zeroCopyUrl}" class="map-popup-thumb" onclick="WiPhotoMap.openPhotoView('${photo.path}')" alt="${photo.filename}" />
            <div class="map-popup-title">${photo.filename}</div>
            <div class="map-popup-coords">${lat.toFixed(4)}, ${lon.toFixed(4)}</div>
          </div>
        `;

        photoMarker.bindPopup(popupHtml, {
          className: 'wiphoto-map-popup'
        });

        // Show photo preview in sidebar on marker click
        photoMarker.on('click', () => {
          if (typeof Sidebar !== 'undefined' && typeof Sidebar.showPreview === 'function') {
            Sidebar.showPreview(photo);
          }
        });

        markerLayerGroup.addLayer(photoMarker);
      }
    });
  }

  // Open photo in full viewer when clicking popup thumbnail
  function openPhotoView(path) {
    if (typeof Gallery !== 'undefined' && typeof Viewer !== 'undefined') {
      const images = Gallery.getFilteredImages();
      const img = images.find(i => i.path === path);
      if (img) {
        Viewer.open(img);
      }
    }
  }

  return {
    init: initMapContainer,
    render,
    updateClusters,
    isValidCoordinate,
    photoToGeoJsonPoint,
    openPhotoView,
    get isInitialized() { return isInitialized; }
  };
})();

if (typeof module !== 'undefined' && module.exports) {
  module.exports = WiPhotoMap;
}
