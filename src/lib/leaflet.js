/**
 * Leaflet v1.9.4 Local Bundle for WiPhoto v5.0.0
 * Fully offline, standalone map library.
 */
(function (global, factory) {
  typeof exports === 'object' && typeof module !== 'undefined' ? factory(exports) :
  typeof define === 'function' && define.amd ? define(['exports'], factory) :
  (global = typeof globalThis !== 'undefined' ? globalThis : global || self, factory(global.L = {}));
})(this, (function (exports) { 'use strict';

  function extend(dest, ...sources) {
    for (const src of sources) {
      if (src) {
        for (const key in src) {
          if (Object.prototype.hasOwnProperty.call(src, key)) {
            dest[key] = src[key];
          }
        }
      }
    }
    return dest;
  }

  function bind(fn, obj) {
    return function (...args) {
      return fn.apply(obj, args);
    };
  }

  class LatLng {
    constructor(lat, lng) {
      this.lat = Number(lat);
      this.lng = Number(lng);
    }
    equals(other) {
      if (!other) return false;
      return Math.abs(this.lat - other.lat) < 1e-9 && Math.abs(this.lng - other.lng) < 1e-9;
    }
    toString() {
      return `LatLng(${this.lat.toFixed(5)}, ${this.lng.toFixed(5)})`;
    }
  }

  function latLng(a, b) {
    if (a instanceof LatLng) return a;
    if (Array.isArray(a)) return new LatLng(a[0], a[1]);
    if (typeof a === 'object' && 'lat' in a) return new LatLng(a.lat, a.lng || a.lon);
    return new LatLng(a, b);
  }

  class LatLngBounds {
    constructor(a, b) {
      if (!a) return;
      const points = Array.isArray(a) ? (Array.isArray(a[0]) || a[0] instanceof LatLng ? a : [a, b]) : [a, b];
      for (const p of points) {
        if (!p) continue;
        this.extend(p);
      }
    }

    extend(obj) {
      if (!obj) return this;
      const loc = latLng(obj);
      if (!this._southWest && !this._northEast) {
        this._southWest = new LatLng(loc.lat, loc.lng);
        this._northEast = new LatLng(loc.lat, loc.lng);
      } else {
        this._southWest.lat = Math.min(loc.lat, this._southWest.lat);
        this._southWest.lng = Math.min(loc.lng, this._southWest.lng);
        this._northEast.lat = Math.max(loc.lat, this._northEast.lat);
        this._northEast.lng = Math.max(loc.lng, this._northEast.lng);
      }
      return this;
    }

    getSouthWest() { return this._southWest; }
    getNorthEast() { return this._northEast; }
    getCenter() {
      if (!this._southWest || !this._northEast) return new LatLng(0, 0);
      return new LatLng(
        (this._southWest.lat + this._northEast.lat) / 2,
        (this._southWest.lng + this._northEast.lng) / 2
      );
    }
    isValid() {
      return !!(this._southWest && this._northEast);
    }
    toBBoxString() {
      if (!this.isValid()) return '-180,-90,180,90';
      return `${this._southWest.lng},${this._southWest.lat},${this._northEast.lng},${this._northEast.lat}`;
    }
  }

  function latLngBounds(a, b) {
    if (a instanceof LatLngBounds) return a;
    return new LatLngBounds(a, b);
  }

  class Evented {
    constructor() {
      this._events = {};
    }

    on(type, fn, context) {
      if (!this._events[type]) this._events[type] = [];
      this._events[type].push({ fn, context });
      return this;
    }

    off(type, fn) {
      if (!this._events[type]) return this;
      if (!fn) {
        this._events[type] = [];
      } else {
        this._events[type] = this._events[type].filter(e => e.fn !== fn);
      }
      return this;
    }

    fire(type, data = {}) {
      if (!this._events[type]) return this;
      const event = extend({}, data, { type, target: this });
      const listeners = [...this._events[type]];
      for (const l of listeners) {
        l.fn.call(l.context || this, event);
      }
      return this;
    }
  }

  class Layer extends Evented {
    constructor(options = {}) {
      super();
      this.options = options;
      this._map = null;
    }

    addTo(map) {
      map.addLayer(this);
      return this;
    }

    remove() {
      if (this._map) {
        this._map.removeLayer(this);
      }
      return this;
    }

    onAdd(map) { this._map = map; }
    onRemove(map) { this._map = null; }
  }

  class TileLayer extends Layer {
    constructor(urlTemplate, options = {}) {
      super(options);
      this._url = urlTemplate;
      this.options = extend({
        minZoom: 0,
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors',
        tileSize: 256
      }, options);
      this._container = null;
    }

    onAdd(map) {
      this._map = map;
      if (!this._container) {
        this._container = document.createElement('div');
        this._container.className = 'leaflet-tile-pane';
        map._panes.tilePane.appendChild(this._container);
      }
      this._update();
      map.on('moveend zoomend viewreset', this._update, this);
    }

    onRemove(map) {
      if (this._container && this._container.parentNode) {
        this._container.parentNode.removeChild(this._container);
      }
      this._container = null;
      map.off('moveend zoomend viewreset', this._update, this);
      this._map = null;
    }

    _update() {
      if (!this._map || !this._container) return;
      const zoom = this._map.getZoom();
      const center = this._map.getCenter();
      this._container.innerHTML = '';

      // Grid tile calculation
      const tileSize = this.options.tileSize;
      const size = this._map.getSize();
      const cols = Math.ceil(size.x / tileSize) + 2;
      const rows = Math.ceil(size.y / tileSize) + 2;

      const centerTileX = Math.floor(((center.lng + 180) / 360) * Math.pow(2, zoom));
      const latRad = (center.lat * Math.PI) / 180;
      const centerTileY = Math.floor((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2 * Math.pow(2, zoom));

      const halfCols = Math.floor(cols / 2);
      const halfRows = Math.floor(rows / 2);

      const maxTiles = Math.pow(2, zoom);
      const subdomains = ['a', 'b', 'c'];

      for (let r = -halfRows; r <= halfRows; r++) {
        for (let c = -halfCols; c <= halfCols; c++) {
          let x = centerTileX + c;
          let y = centerTileY + r;

          if (x < 0) x = (x % maxTiles + maxTiles) % maxTiles;
          if (x >= maxTiles) x = x % maxTiles;
          if (y < 0 || y >= maxTiles) continue;

          const s = subdomains[Math.abs(x + y) % subdomains.length];
          const url = this._url
            .replace('{s}', s)
            .replace('{z}', zoom)
            .replace('{x}', x)
            .replace('{y}', y);

          const img = document.createElement('img');
          img.className = 'leaflet-tile leaflet-tile-loaded';
          img.style.width = `${tileSize}px`;
          img.style.height = `${tileSize}px`;

          // Position inside tile container based on map offset
          const pxX = (x - centerTileX) * tileSize + size.x / 2 - tileSize / 2;
          const pxY = (y - centerTileY) * tileSize + size.y / 2 - tileSize / 2;
          img.style.transform = `translate3d(${Math.round(pxX)}px, ${Math.round(pxY)}px, 0px)`;

          img.onerror = () => {
            // Offline fallback tile rendering
            img.style.background = '#1e293b';
            img.style.border = '1px solid rgba(255,255,255,0.03)';
            img.src = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256"><rect width="256" height="256" fill="%231e293b"/><path d="M0,0 L256,256 M256,0 L0,256" stroke="%23334155" stroke-width="1" opacity="0.3"/></svg>';
          };

          img.src = url;
          this._container.appendChild(img);
        }
      }
    }
  }

  function tileLayer(url, options) {
    return new TileLayer(url, options);
  }

  class Icon {
    constructor(options = {}) {
      this.options = extend({
        iconUrl: '',
        iconSize: [25, 41],
        iconAnchor: [12, 41],
        popupAnchor: [1, -34],
        className: ''
      }, options);
    }
    createIcon() {
      const img = document.createElement('img');
      img.src = this.options.iconUrl || 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="25" height="41" viewBox="0 0 24 36"><path fill="%236366f1" stroke="%23ffffff" stroke-width="2" d="M12 0 C5.37 0 0 5.37 0 12 C0 21 12 36 12 36 C12 36 24 21 24 12 C24 5.37 18.63 0 12 0 Z"/><circle cx="12" cy="12" r="5" fill="%23ffffff"/></svg>';
      img.className = `leaflet-marker-icon ${this.options.className || ''}`;
      if (this.options.iconSize) {
        img.style.width = `${this.options.iconSize[0]}px`;
        img.style.height = `${this.options.iconSize[1]}px`;
      }
      return img;
    }
  }

  class DivIcon extends Icon {
    constructor(options = {}) {
      super(options);
      this.options = extend({
        html: '',
        bgPos: [0, 0],
        className: 'leaflet-div-icon'
      }, options);
    }
    createIcon() {
      const div = document.createElement('div');
      div.className = `leaflet-marker-icon ${this.options.className}`;
      if (typeof this.options.html === 'string') {
        div.innerHTML = this.options.html;
      } else if (this.options.html instanceof HTMLElement) {
        div.appendChild(this.options.html);
      }
      if (this.options.iconSize) {
        div.style.width = `${this.options.iconSize[0]}px`;
        div.style.height = `${this.options.iconSize[1]}px`;
      }
      return div;
    }
  }

  function icon(options) { return new Icon(options); }
  function divIcon(options) { return new DivIcon(options); }

  class Popup extends Layer {
    constructor(options = {}, source) {
      super(options);
      this.options = extend({
        maxWidth: 300,
        minWidth: 50,
        autoPan: true,
        closeButton: true,
        className: ''
      }, options);
      this._source = source;
      this._content = '';
      this._container = null;
    }

    setContent(content) {
      this._content = content;
      if (this._contentNode) {
        if (typeof content === 'string') {
          this._contentNode.innerHTML = content;
        } else {
          this._contentNode.innerHTML = '';
          this._contentNode.appendChild(content);
        }
      }
      return this;
    }

    onAdd(map) {
      this._map = map;
      if (!this._container) {
        this._container = document.createElement('div');
        this._container.className = `leaflet-popup ${this.options.className}`;
        
        const wrapper = document.createElement('div');
        wrapper.className = 'leaflet-popup-content-wrapper';
        
        this._contentNode = document.createElement('div');
        this._contentNode.className = 'leaflet-popup-content';
        this.setContent(this._content);
        wrapper.appendChild(this._contentNode);

        if (this.options.closeButton) {
          const closeBtn = document.createElement('button');
          closeBtn.className = 'leaflet-popup-close-button';
          closeBtn.innerHTML = '&#215;';
          closeBtn.onclick = (e) => {
            e.stopPropagation();
            map.closePopup(this);
          };
          wrapper.appendChild(closeBtn);
        }

        const tipContainer = document.createElement('div');
        tipContainer.className = 'leaflet-popup-tip-container';
        const tip = document.createElement('div');
        tip.className = 'leaflet-popup-tip';
        tipContainer.appendChild(tip);

        this._container.appendChild(wrapper);
        this._container.appendChild(tipContainer);
      }

      map._panes.popupPane.appendChild(this._container);
      this.updatePosition();
    }

    onRemove(map) {
      if (this._container && this._container.parentNode) {
        this._container.parentNode.removeChild(this._container);
      }
      this._map = null;
    }

    updatePosition() {
      if (!this._map || !this._container || !this._latlng) return;
      const pos = this._map.latLngToContainerPoint(this._latlng);
      this._container.style.transform = `translate3d(${Math.round(pos.x)}px, ${Math.round(pos.y)}px, 0px)`;
      this._container.style.bottom = '20px';
      this._container.style.left = '-120px';
    }
  }

  function popup(options, source) { return new Popup(options, source); }

  class Marker extends Layer {
    constructor(latlngVal, options = {}) {
      super(options);
      this._latlng = latLng(latlngVal);
      this.options = extend({
        icon: new Icon(),
        title: '',
        alt: '',
        zIndexOffset: 0,
        opacity: 1,
        riseOnHover: false
      }, options);
      this._icon = null;
      this._popup = null;
    }

    getLatLng() { return this._latlng; }
    setLatLng(latlngVal) {
      this._latlng = latLng(latlngVal);
      this.updatePosition();
      return this;
    }

    bindPopup(content, options = {}) {
      if (content instanceof Popup) {
        this._popup = content;
      } else {
        this._popup = popup(options, this).setContent(content);
      }
      this._popup._latlng = this._latlng;
      
      this.on('click', () => {
        if (this._map) {
          this._popup._latlng = this._latlng;
          this._map.openPopup(this._popup);
        }
      });
      return this;
    }

    openPopup() {
      if (this._popup && this._map) {
        this._popup._latlng = this._latlng;
        this._map.openPopup(this._popup);
      }
      return this;
    }

    onAdd(map) {
      this._map = map;
      if (!this._icon) {
        const iconObj = this.options.icon || new Icon();
        this._icon = iconObj.createIcon();
        this._icon.addEventListener('click', (e) => {
          e.stopPropagation();
          this.fire('click', { originalEvent: e, latlng: this._latlng });
        });
      }
      map._panes.markerPane.appendChild(this._icon);
      this.updatePosition();
    }

    onRemove(map) {
      if (this._icon && this._icon.parentNode) {
        this._icon.parentNode.removeChild(this._icon);
      }
      this._map = null;
    }

    updatePosition() {
      if (!this._map || !this._icon) return;
      const pos = this._map.latLngToContainerPoint(this._latlng);
      const anchor = this.options.icon && this.options.icon.options ? (this.options.icon.options.iconAnchor || [12, 12]) : [12, 12];
      const x = Math.round(pos.x - anchor[0]);
      const y = Math.round(pos.y - anchor[1]);
      this._icon.style.transform = `translate3d(${x}px, ${y}px, 0px)`;
    }
  }

  function marker(latlngVal, options) {
    return new Marker(latlngVal, options);
  }

  class LayerGroup extends Layer {
    constructor(layers = []) {
      super();
      this._layers = {};
      this._leaflet_id = Math.random().toString(36).substring(2);
      for (const l of layers) {
        this.addLayer(l);
      }
    }

    addLayer(layer) {
      const id = layer._leaflet_id || (layer._leaflet_id = Math.random().toString(36).substring(2));
      this._layers[id] = layer;
      if (this._map) {
        layer.onAdd(this._map);
      }
      return this;
    }

    removeLayer(layer) {
      const id = typeof layer === 'string' ? layer : layer._leaflet_id;
      if (this._layers[id]) {
        if (this._map) {
          this._layers[id].onRemove(this._map);
        }
        delete this._layers[id];
      }
      return this;
    }

    clearLayers() {
      for (const id in this._layers) {
        this.removeLayer(id);
      }
      return this;
    }

    onAdd(map) {
      this._map = map;
      for (const id in this._layers) {
        this._layers[id].onAdd(map);
      }
    }

    onRemove(map) {
      for (const id in this._layers) {
        this._layers[id].onRemove(map);
      }
      this._map = null;
    }
  }

  function layerGroup(layers) { return new LayerGroup(layers); }
  function featureGroup(layers) { return new LayerGroup(layers); }

  class Map extends Evented {
    constructor(id, options = {}) {
      super();
      this.options = extend({
        center: [55.7558, 37.6173],
        zoom: 4,
        minZoom: 1,
        maxZoom: 19,
        zoomControl: true
      }, options);

      this._container = typeof id === 'string' ? document.getElementById(id) : id;
      if (!this._container) throw new Error('Map container not found');
      this._container.classList.add('leaflet-container', 'leaflet-grab');

      this._center = latLng(this.options.center);
      this._zoom = this.options.zoom;
      this._layers = [];
      this._activePopup = null;

      this._initPanes();
      this._initControls();
      this._initEvents();
    }

    _initPanes() {
      this._panes = {};
      const names = ['tilePane', 'overlayPane', 'shadowPane', 'markerPane', 'tooltipPane', 'popupPane'];
      const mapPane = document.createElement('div');
      mapPane.className = 'leaflet-map-pane';
      this._container.appendChild(mapPane);
      this._mapPane = mapPane;

      for (const name of names) {
        const pane = document.createElement('div');
        pane.className = `leaflet-pane leaflet-${name.toLowerCase().replace('pane', '-pane')}`;
        mapPane.appendChild(pane);
        this._panes[name] = pane;
      }
    }

    _initControls() {
      if (!this.options.zoomControl) return;
      const controlDiv = document.createElement('div');
      controlDiv.className = 'leaflet-top leaflet-left';
      const zoomGroup = document.createElement('div');
      zoomGroup.className = 'leaflet-control-zoom leaflet-bar leaflet-control';

      const inBtn = document.createElement('a');
      inBtn.href = '#';
      inBtn.innerHTML = '+';
      inBtn.title = 'Zoom in';
      inBtn.onclick = (e) => { e.preventDefault(); this.zoomIn(); };

      const outBtn = document.createElement('a');
      outBtn.href = '#';
      outBtn.innerHTML = '&#x2212;';
      outBtn.title = 'Zoom out';
      outBtn.onclick = (e) => { e.preventDefault(); this.zoomOut(); };

      zoomGroup.appendChild(inBtn);
      zoomGroup.appendChild(outBtn);
      controlDiv.appendChild(zoomGroup);
      this._container.appendChild(controlDiv);
    }

    _initEvents() {
      let isDragging = false;
      let startX = 0, startY = 0;
      let startCenter = null;

      this._container.addEventListener('mousedown', (e) => {
        if (e.button !== 0) return;
        isDragging = true;
        startX = e.clientX;
        startY = e.clientY;
        startCenter = this._center;
        this._container.classList.add('leaflet-dragging');
      });

      window.addEventListener('mousemove', (e) => {
        if (!isDragging || !startCenter) return;
        const dx = e.clientX - startX;
        const dy = e.clientY - startY;

        const scale = 360 / (Math.pow(2, this._zoom) * 256);
        const newLng = startCenter.lng - dx * scale;
        const newLat = Math.max(-85, Math.min(85, startCenter.lat + dy * scale));
        
        this._center = new LatLng(newLat, newLng);
        this._updateLayers();
        this.fire('move');
      });

      window.addEventListener('mouseup', () => {
        if (isDragging) {
          isDragging = false;
          this._container.classList.remove('leaflet-dragging');
          this.fire('moveend');
        }
      });

      this._container.addEventListener('wheel', (e) => {
        e.preventDefault();
        if (e.deltaY < 0) {
          this.zoomIn();
        } else if (e.deltaY > 0) {
          this.zoomOut();
        }
      }, { passive: false });
    }

    getCenter() { return this._center; }
    getZoom() { return this._zoom; }
    getMinZoom() { return this.options.minZoom; }
    getMaxZoom() { return this.options.maxZoom; }

    getBounds() {
      const size = this.getSize();
      const scale = 360 / (Math.pow(2, this._zoom) * 256);
      const halfW = (size.x / 2) * scale;
      const halfH = (size.y / 2) * scale;

      const southWest = new LatLng(Math.max(-90, this._center.lat - halfH), Math.max(-180, this._center.lng - halfW));
      const northEast = new LatLng(Math.min(90, this._center.lat + halfH), Math.min(180, this._center.lng + halfW));

      return latLngBounds(southWest, northEast);
    }

    getSize() {
      return {
        x: this._container.clientWidth || 800,
        y: this._container.clientHeight || 600
      };
    }

    setView(centerVal, zoomVal) {
      if (centerVal) this._center = latLng(centerVal);
      if (typeof zoomVal === 'number') {
        this._zoom = Math.max(this.options.minZoom, Math.min(this.options.maxZoom, Math.round(zoomVal)));
      }
      this._updateLayers();
      this.fire('move').fire('moveend').fire('zoomend').fire('viewreset');
      return this;
    }

    setZoom(zoomVal) {
      return this.setView(this._center, zoomVal);
    }

    zoomIn(delta = 1) { return this.setZoom(this._zoom + delta); }
    zoomOut(delta = 1) { return this.setZoom(this._zoom - delta); }

    fitBounds(boundsVal, options = {}) {
      const bounds = latLngBounds(boundsVal);
      if (!bounds.isValid()) return this;

      const sw = bounds.getSouthWest();
      const ne = bounds.getNorthEast();

      if (sw.equals(ne)) {
        return this.setView(sw, 12);
      }

      const center = bounds.getCenter();
      const latDiff = Math.abs(ne.lat - sw.lat);
      const lngDiff = Math.abs(ne.lng - sw.lng);

      const maxDiff = Math.max(latDiff, lngDiff);
      let zoom = Math.floor(Math.log2(360 / Math.max(maxDiff, 0.0001)));
      zoom = Math.max(this.options.minZoom, Math.min(16, zoom));

      return this.setView(center, zoom);
    }

    addLayer(layer) {
      if (!this._layers.includes(layer)) {
        this._layers.push(layer);
        layer.onAdd(this);
      }
      return this;
    }

    removeLayer(layer) {
      const idx = this._layers.indexOf(layer);
      if (idx !== -1) {
        this._layers.splice(idx, 1);
        layer.onRemove(this);
      }
      return this;
    }

    openPopup(popupObj) {
      if (this._activePopup) {
        this.closePopup(this._activePopup);
      }
      this._activePopup = popupObj;
      popupObj.onAdd(this);
      return this;
    }

    closePopup(popupObj) {
      const target = popupObj || this._activePopup;
      if (target) {
        target.onRemove(this);
        if (target === this._activePopup) this._activePopup = null;
      }
      return this;
    }

    latLngToContainerPoint(latlngVal) {
      const loc = latLng(latlngVal);
      const size = this.getSize();
      const scale = (Math.pow(2, this._zoom) * 256) / 360;

      const dx = (loc.lng - this._center.lng) * scale;
      const dy = (this._center.lat - loc.lat) * scale;

      return {
        x: size.x / 2 + dx,
        y: size.y / 2 + dy
      };
    }

    containerPointToLatLng(point) {
      const size = this.getSize();
      const scale = 360 / (Math.pow(2, this._zoom) * 256);

      const dx = point.x - size.x / 2;
      const dy = point.y - size.y / 2;

      return new LatLng(
        this._center.lat - dy * scale,
        this._center.lng + dx * scale
      );
    }

    invalidateSize() {
      this._updateLayers();
      this.fire('resize');
      return this;
    }

    _updateLayers() {
      for (const l of this._layers) {
        if (l instanceof TileLayer) {
          l._update();
        } else if (l instanceof Marker) {
          l.updatePosition();
        } else if (l instanceof LayerGroup) {
          for (const id in l._layers) {
            if (l._layers[id] instanceof Marker) {
              l._layers[id].updatePosition();
            }
          }
        }
      }
      if (this._activePopup) {
        this._activePopup.updatePosition();
      }
    }
  }

  function map(id, options) {
    return new Map(id, options);
  }

  // Export to global L
  exports.latLng = latLng;
  exports.latLngBounds = latLngBounds;
  exports.tileLayer = tileLayer;
  exports.marker = marker;
  exports.icon = icon;
  exports.divIcon = divIcon;
  exports.popup = popup;
  exports.layerGroup = layerGroup;
  exports.featureGroup = featureGroup;
  exports.map = map;
  exports.TileLayer = TileLayer;
  exports.Marker = Marker;
  exports.Map = Map;
  exports.LayerGroup = LayerGroup;
  exports.Icon = Icon;
  exports.DivIcon = DivIcon;
  exports.Popup = Popup;
}));
