interface BaseFeatureProperties {
  type: string;
  stroke?: string;
  'stroke-width'?: number;
  'stroke-opacity'?: number;
  'stroke-dasharray'?: number[];
  fill?: string;
  'fill-opacity'?: number;
}

interface ObserverProperties extends BaseFeatureProperties {
  type: 'observer';
  elevation: number;
  units: 'feet' | 'meters';
  'marker-color': string;
  'marker-size': 'medium';
  'marker-symbol': 'camera';
}

interface ViewshedProperties extends BaseFeatureProperties {
  type: 'viewshed';
  visible: boolean;
  latitude: number;
  longitude: number;
}

interface AnalysisRangeProperties extends BaseFeatureProperties {
  type: 'analysis_range';
  radius: number;
  units: 'feet' | 'meters';
}

export interface ViewshedFeature {
  type: 'Feature';
  geometry: {
    type: 'Polygon' | 'Point' | 'LineString';
    coordinates: number[][] | [number, number];
  };
  properties: ObserverProperties | ViewshedProperties | AnalysisRangeProperties;
}

export interface ViewshedResponse {
  type: 'FeatureCollection';
  features: ViewshedFeature[];
}
