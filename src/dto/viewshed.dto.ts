export interface ViewshedFeature {
  type: 'Feature';
  geometry: {
    type: 'Polygon' | 'Point';
    coordinates: number[][] | [number, number];
  };
  properties: {
    type?: 'viewshed';
    visibility?: 'visible';
    observer_height?: number;
    name?: string;
  };
}

export interface ViewshedResponse {
  type: 'FeatureCollection';
  features: ViewshedFeature[];
}
