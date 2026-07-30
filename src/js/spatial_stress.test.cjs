// ═══ WiPhoto Spatial Clustering (Leaflet + Supercluster) Empirical Stress Test ═══
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

// Load Supercluster via VM
const scPath = path.join(__dirname, '../lib/supercluster.min.js');
const scCode = fs.readFileSync(scPath, 'utf8');
const scMod = { exports: {} };
vm.runInNewContext(scCode, { module: scMod, exports: scMod.exports });
const Supercluster = scMod.exports;

// Load WiPhotoMap via VM
const mapPath = path.join(__dirname, 'map.js');
const mapCode = fs.readFileSync(mapPath, 'utf8');
const mapMod = { exports: {} };
vm.runInNewContext(mapCode, { module: mapMod, exports: mapMod.exports });
const WiPhotoMap = mapMod.exports;

test('Spatial Clustering — 1,000 Points Global Distribution Benchmark', (t) => {
  const points = [];
  for (let i = 0; i < 1000; i++) {
    const lat = -80 + (i * 160) / 1000;
    const lon = -170 + (i * 340) / 1000;
    points.push({
      id: `photo_${i}`,
      path: `/photos/photo_${i}.jpg`,
      filename: `photo_${i}.jpg`,
      gps_location: [lat, lon],
      rating: (i % 5) + 1
    });
  }

  // 1. Convert to GeoJSON Points
  const startGeo = performance.now();
  const geoPoints = points.map(p => WiPhotoMap.photoToGeoJsonPoint(p)).filter(Boolean);
  const geoTime = performance.now() - startGeo;
  assert.equal(geoPoints.length, 1000, 'All 1,000 points should convert to valid GeoJSON features');
  assert.ok(geoTime < 50, `GeoJSON conversion for 1,000 points took ${geoTime.toFixed(2)}ms`);

  // 2. Load into Supercluster
  const index = new Supercluster({
    radius: 45,
    maxZoom: 16,
    minZoom: 0,
    extent: 512,
    nodeSize: 64
  });

  const startLoad = performance.now();
  index.load(geoPoints);
  const loadTime = performance.now() - startLoad;
  assert.ok(loadTime < 100, `Supercluster.load() for 1,000 points took ${loadTime.toFixed(2)}ms (<100ms requirement)`);

  // 3. Zoom level query latency across all zoom levels 0..18
  let totalQueryTime = 0;
  const bbox = [-180, -90, 180, 90];
  
  for (let zoom = 0; zoom <= 18; zoom++) {
    const startQuery = performance.now();
    const clusters = index.getClusters(bbox, zoom);
    const queryTime = performance.now() - startQuery;
    totalQueryTime += queryTime;
    assert.ok(clusters.length > 0, `Clusters should be returned for zoom ${zoom}`);

    let totalPointsInZoom = 0;
    clusters.forEach(c => {
      if (c.properties.cluster) {
        totalPointsInZoom += c.properties.point_count;
      } else {
        totalPointsInZoom += 1;
      }
    });
    assert.equal(totalPointsInZoom, 1000, `Total points at zoom ${zoom} must equal 1,000`);
  }

  const avgQueryTime = totalQueryTime / 19;
  assert.ok(avgQueryTime < 5, `Average zoom query latency was ${avgQueryTime.toFixed(2)}ms (<5ms requirement)`);

  console.log(`  ✓ 1,000 Points Global Distribution: Load ${loadTime.toFixed(2)}ms, Avg Query ${avgQueryTime.toFixed(2)}ms`);
});

test('Spatial Clustering — 1,000 Points Dense Single-City Cluster Benchmark', (t) => {
  const points = [];
  const centerLat = 55.7558;
  const centerLon = 37.6173;

  for (let i = 0; i < 1000; i++) {
    const lat = centerLat + (Math.random() - 0.5) * 0.01;
    const lon = centerLon + (Math.random() - 0.5) * 0.01;
    points.push({
      id: `dense_${i}`,
      path: `/photos/dense_${i}.jpg`,
      filename: `dense_${i}.jpg`,
      gps_location: [lat, lon],
      rating: 5
    });
  }

  const geoPoints = points.map(p => WiPhotoMap.photoToGeoJsonPoint(p)).filter(Boolean);
  assert.equal(geoPoints.length, 1000);

  const index = new Supercluster({ radius: 45, maxZoom: 16 });
  const startLoad = performance.now();
  index.load(geoPoints);
  const loadTime = performance.now() - startLoad;

  const lowZoomClusters = index.getClusters([37.0, 55.0, 38.0, 56.0], 4);
  assert.equal(lowZoomClusters.length, 1, 'Should form 1 cluster at zoom 4');
  assert.equal(lowZoomClusters[0].properties.point_count, 1000, 'Cluster point count should be 1,000');

  const clusterId = lowZoomClusters[0].properties.cluster_id;
  const startExpand = performance.now();
  const expansionZoom = index.getClusterExpansionZoom(clusterId);
  const expandTime = performance.now() - startExpand;

  assert.ok(expansionZoom > 4, 'Expansion zoom should be > 4');
  assert.ok(expandTime < 10, `Expansion zoom calculation took ${expandTime.toFixed(2)}ms`);

  console.log(`  ✓ 1,000 Points Dense Cluster: Load ${loadTime.toFixed(2)}ms, Expansion Calc ${expandTime.toFixed(2)}ms`);
});

test('Spatial Clustering — Scalability Profile (1k, 2.5k, 5k, 10k Points)', (t) => {
  [1000, 2500, 5000, 10000].forEach(count => {
    const geoPoints = [];
    for (let i = 0; i < count; i++) {
      const lat = -80 + (i * 160) / count;
      const lon = -170 + (i * 340) / count;
      geoPoints.push({
        type: 'Feature',
        properties: { id: i, path: `/p/${i}.jpg` },
        geometry: { type: 'Point', coordinates: [lon, lat] }
      });
    }

    const index = new Supercluster({ radius: 45, maxZoom: 16 });
    const startLoad = performance.now();
    index.load(geoPoints);
    const loadTime = performance.now() - startLoad;

    const startQuery = performance.now();
    const clusters = index.getClusters([-180, -90, 180, 90], 10);
    const queryTime = performance.now() - startQuery;

    assert.ok(loadTime < 3500, `Load for ${count} points took ${loadTime.toFixed(2)}ms (<3500ms target)`);
    assert.ok(queryTime < 50, `Query for ${count} points took ${queryTime.toFixed(2)}ms (<50ms target)`);

    console.log(`  ✓ ${count} Points Profile: Load ${loadTime.toFixed(2)}ms, Query @ z=10: ${queryTime.toFixed(2)}ms, Cluster Count: ${clusters.length}`);
  });
});

test('Spatial Clustering — Boundary Coordinates & Error Robustness', (t) => {
  assert.equal(WiPhotoMap.isValidCoordinate(90, 180), true, 'North Pole + Anti-meridian (+90, +180)');
  assert.equal(WiPhotoMap.isValidCoordinate(-90, -180), true, 'South Pole + Anti-meridian (-90, -180)');
  assert.equal(WiPhotoMap.isValidCoordinate(0, 0), true, 'Equator + Prime Meridian (0, 0)');
  
  assert.equal(WiPhotoMap.isValidCoordinate(90.0001, 0), false, 'Lat > 90');
  assert.equal(WiPhotoMap.isValidCoordinate(-90.0001, 0), false, 'Lat < -90');
  assert.equal(WiPhotoMap.isValidCoordinate(0, 180.0001), false, 'Lon > 180');
  assert.equal(WiPhotoMap.isValidCoordinate(0, -180.0001), false, 'Lon < -180');

  assert.equal(WiPhotoMap.isValidCoordinate(NaN, 50), false, 'NaN lat');
  assert.equal(WiPhotoMap.isValidCoordinate(50, NaN), false, 'NaN lon');
  assert.equal(WiPhotoMap.isValidCoordinate('55.75', '37.61'), false, 'String coords');
  assert.equal(WiPhotoMap.isValidCoordinate(null, undefined), false, 'Null / undefined');

  assert.equal(WiPhotoMap.photoToGeoJsonPoint(null), null);
  assert.equal(WiPhotoMap.photoToGeoJsonPoint({}), null);
  assert.equal(WiPhotoMap.photoToGeoJsonPoint({ gps_location: [55.75] }), null);
  assert.equal(WiPhotoMap.photoToGeoJsonPoint({ gps_location: [100, 37.61] }), null);

  const validPhoto = {
    path: '/path/to/img.jpg',
    filename: 'img.jpg',
    gps_location: [55.7558, 37.6173],
    rating: 4
  };
  const feature = WiPhotoMap.photoToGeoJsonPoint(validPhoto);
  assert.equal(feature.geometry.coordinates[0], 37.6173, 'GeoJSON lon is 1st element');
  assert.equal(feature.geometry.coordinates[1], 55.7558, 'GeoJSON lat is 2nd element');

  console.log('  ✓ Boundary Coordinates & Error Robustness verified');
});
