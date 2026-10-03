import { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import type { StyleSpecification } from 'maplibre-gl';
import type { FeatureCollection } from 'geojson';
import 'maplibre-gl/dist/maplibre-gl.css';
import { layers, namedFlavor } from '@protomaps/basemaps';
import { CATEGORY } from './i18n';
import type { Lang, Listing } from './types';

const WAYANAD_CENTER: [number, number] = [76.1, 11.66];
// The offline tiles cover this box; keep the camera inside it.
const BOUNDS: [[number, number], [number, number]] = [[75.6, 11.3], [76.6, 12.1]];
const ASSETS = new URL(`${import.meta.env.BASE_URL}basemap/`, location.href).href;

// Warm the light basemap so it sits with the app's cream-and-amber palette.
const WARM_LIGHT = { background: '#e9e2d6', earth: '#f3eee6', water: '#a9d3e0', city_label_halo: '#f3eee6', subplace_label_halo: '#f3eee6' };

function buildStyle(tiles: string, dark: boolean, lang: Lang): StyleSpecification {
  const flavor = dark ? 'dark' : 'light';
  const colors = dark ? namedFlavor('dark') : { ...namedFlavor('light'), ...WARM_LIGHT };
  return {
    version: 8,
    glyphs: `${ASSETS}fonts/{fontstack}/{range}.pbf`,
    sprite: `${ASSETS}sprites/v4/${flavor}`,
    sources: {
      protomaps: {
        type: 'vector',
        url: tiles,
        attribution: '<a href="https://protomaps.com">Protomaps</a> © <a href="https://openstreetmap.org/copyright">OpenStreetMap</a>',
      },
    },
    layers: layers('protomaps', colors, { lang }),
  };
}

/** Map padding that keeps content clear of the floating top bar and bottom cards. */
function overlayPadding(extra: number) {
  const wide = matchMedia('(min-width: 760px)').matches;
  return { top: (wide ? 120 : 130) + extra, bottom: 210 + extra, left: extra, right: extra };
}

/** Closed polygon approximating a circle, for "approximate area" listings. */
function circle([lon, lat]: [number, number], radiusM: number, steps = 48): [number, number][] {
  const dLat = radiusM / 111_320;
  const dLon = radiusM / (111_320 * Math.cos((lat * Math.PI) / 180));
  return Array.from({ length: steps + 1 }, (_, i) => {
    const a = (i / steps) * 2 * Math.PI;
    return [lon + dLon * Math.cos(a), lat + dLat * Math.sin(a)];
  });
}

function areaGeoJSON(listings: Listing[]): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: listings
      .filter((l) => l.properties.privacy === 'area')
      .map((l) => ({
        type: 'Feature',
        properties: { id: l.properties.id },
        geometry: { type: 'Polygon', coordinates: [circle(l.geometry.coordinates, (l.properties.radius_m ?? 200) * 0.75)] },
      })),
  };
}

function addAreaLayers(map: maplibregl.Map, listings: Listing[]) {
  if (map.getSource('areas')) {
    (map.getSource('areas') as maplibregl.GeoJSONSource).setData(areaGeoJSON(listings));
    return;
  }
  map.addSource('areas', { type: 'geojson', data: areaGeoJSON(listings) });
  map.addLayer({ id: 'areas-fill', type: 'fill', source: 'areas', minzoom: 12, paint: { 'fill-color': '#f2a33a', 'fill-opacity': 0.16 } });
  map.addLayer({
    id: 'areas-line', type: 'line', source: 'areas', minzoom: 12,
    paint: { 'line-color': '#e08a1e', 'line-width': 1.5, 'line-dasharray': [2, 2] },
  });
}

function pinElement(l: Listing, onSelect: (id: number) => void): HTMLButtonElement {
  const p = l.properties;
  const el = document.createElement('button');
  el.type = 'button';
  el.className = 'pin';
  el.dataset.id = String(p.id);
  el.style.setProperty('--hue', String(CATEGORY[p.category].hue));
  const days = p.days_since_checkin;
  if (days !== null && days < 1) el.classList.add('is-on');
  if (days === null || days > 7) el.classList.add('is-stale');
  el.innerHTML = `<span class="pin-glow"></span><span class="pin-body">${CATEGORY[p.category].icon}</span>${
    p.privacy === 'meeting' ? '<span class="pin-flag">🚩</span>' : ''
  }`;
  el.setAttribute('aria-label', p.title.en);
  el.addEventListener('click', (e) => {
    e.stopPropagation();
    onSelect(p.id);
  });
  return el;
}

interface Props {
  listings: Listing[];
  selectedId: number | null;
  onSelect: (id: number | null) => void;
  tiles: string;
  dark: boolean;
  lang: Lang;
  locateSignal: number;
}

export default function MapView({ listings, selectedId, onSelect, tiles, dark, lang, locateSignal }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markers = useRef(new Map<number, maplibregl.Marker>());
  const listingsRef = useRef(listings);
  listingsRef.current = listings;
  const geolocate = useRef<maplibregl.GeolocateControl | null>(null);
  const fitted = useRef(false);

  // Create the map once.
  useEffect(() => {
    const map = new maplibregl.Map({
      container: container.current!,
      style: buildStyle(tiles, dark, lang),
      center: WAYANAD_CENTER,
      zoom: 10,
      minZoom: 8,
      maxZoom: 16,
      maxBounds: BOUNDS,
      attributionControl: { compact: true },
    });
    geolocate.current = new maplibregl.GeolocateControl({ positionOptions: { enableHighAccuracy: true }, trackUserLocation: false });
    map.addControl(geolocate.current, 'top-right'); // hidden; triggered by our own button
    map.on('style.load', () => addAreaLayers(map, listingsRef.current));
    map.on('click', () => onSelect(null));
    mapRef.current = map;
    return () => map.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Restyle on theme, language or tile-source change (markers are DOM, so they survive).
  useEffect(() => {
    mapRef.current?.setStyle(buildStyle(tiles, dark, lang), { diff: false });
  }, [tiles, dark, lang]);

  // Sync markers and area circles with the listings.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const seen = new Set<number>();
    for (const l of listings) {
      seen.add(l.properties.id);
      markers.current.get(l.properties.id)?.remove();
      const marker = new maplibregl.Marker({ element: pinElement(l, onSelect), anchor: 'bottom' })
        .setLngLat(l.geometry.coordinates)
        .addTo(map);
      markers.current.set(l.properties.id, marker);
    }
    for (const [id, m] of markers.current) if (!seen.has(id)) (m.remove(), markers.current.delete(id));
    if (map.isStyleLoaded()) addAreaLayers(map, listings);

    // First time listings arrive, frame them all, clear of the top bar and cards.
    if (!fitted.current && listings.length) {
      fitted.current = true;
      const bounds = new maplibregl.LngLatBounds();
      listings.forEach((l) => bounds.extend(l.geometry.coordinates));
      map.fitBounds(bounds, { padding: overlayPadding(48), maxZoom: 12, animate: false });
    }
  }, [listings, onSelect]);

  // Highlight and bring the selected pin into view.
  useEffect(() => {
    for (const [id, m] of markers.current) m.getElement().classList.toggle('is-selected', id === selectedId);
    const l = listings.find((x) => x.properties.id === selectedId);
    const map = mapRef.current;
    if (l && map) {
      // Centre the pin in the part of the map the detail sheet leaves visible.
      const narrow = matchMedia('(max-width: 759px)').matches;
      map.easeTo({
        center: l.geometry.coordinates,
        zoom: Math.max(map.getZoom(), 12.5),
        padding: narrow ? { top: 120, bottom: innerHeight * 0.55, left: 0, right: 0 } : { left: 420, top: 0, bottom: 0, right: 0 },
        duration: 600,
      });
    }
  }, [selectedId, listings]);

  useEffect(() => {
    if (locateSignal) geolocate.current?.trigger();
  }, [locateSignal]);

  return <div ref={container} className="map" />;
}
