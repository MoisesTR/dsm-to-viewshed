import os
import sys
import json
import tempfile

import numpy as np
import rasterio
from rasterio.features import shapes
from pyproj import Transformer, CRS
from subprocess import run, CalledProcessError, PIPE

def calculate_los(dsm_path, lng, lat, equipment_height_ft, max_distance):
    """
    Calculate line of sight from an observer point using GDAL viewshed.
    
    Key Implementation Notes:
    - Coverage is calculated only within the circular max_distance range
    - Uses 0.75 curvature coefficient for RF propagation modeling
    - Handles coordinate transforms: WGS84 <-> DSM CRS
    - Accounts for surface elevation + equipment height
    - Returns GeoJSON with visible areas and analysis boundary
    
    Args:
        dsm_path: Path to the Digital Surface Model (DSM) file
        lng: Observer longitude in WGS84
        lat: Observer latitude in WGS84
        equipment_height_ft: Height of equipment above ground in feet
        max_distance: Maximum analysis radius in feet
    
    Returns:
        GeoJSON FeatureCollection containing:
        - MultiPolygon of visible areas (with lat/lng centroids)
        - Observer point with elevation metadata
        - Analysis range circle showing max_distance boundary
    """
    try:
        # Create temporary file for viewshed output
        with tempfile.NamedTemporaryFile(suffix='.tif', delete=False) as tmp:
            viewshed_path = tmp.name
        
        # Open DSM and get observer location
        with rasterio.open(dsm_path) as dsm:
            # Check if DSM is in feet (US units)
            crs_wkt = dsm.crs.to_wkt().lower()
            is_feet = 'foot' in crs_wkt or 'ft' in crs_wkt
            if not is_feet:
                print("Warning: DSM might not be in US feet", file=sys.stderr)
            
            # Convert WGS84 lat/lng to DSM coordinate system
            transformer = Transformer.from_crs(CRS("EPSG:4326"), dsm.crs, always_xy=True)
            observer_x, observer_y = transformer.transform(float(lng), float(lat))
            
             # Get surface elevation from DSM at observer point (includes buildings)
            surface_elevation = next(dsm.sample([(observer_x, observer_y)]))[0]
            if surface_elevation is None:
                print("Error: Could not get surface elevation from DSM", file=sys.stderr)
                return None
            
            print(f"Surface elevation from DSM: {surface_elevation:.1f}{'ft' if is_feet else 'm'}", file=sys.stderr)
            print(f"Equipment height above surface: {equipment_height_ft:.1f}{'ft' if is_feet else 'm'}", file=sys.stderr)
            print(f"Observer will be at: {surface_elevation + equipment_height_ft:.1f}{'ft' if is_feet else 'm'} total", file=sys.stderr)
            
            # Get elevation stats from the analysis area
            window_size = int(max_distance / dsm.res[0])  # Convert distance to pixels
            row = int((observer_y - dsm.bounds.top) / dsm.res[1])
            col = int((observer_x - dsm.bounds.left) / dsm.res[0])
            window = dsm.read(1,
                window=((max(0, row - window_size), min(dsm.height, row + window_size)),
                       (max(0, col - window_size), min(dsm.width, col + window_size))))
            valid_elevations = window[window != dsm.nodata]
            min_elev = float(np.min(valid_elevations))
            max_elev = float(np.max(valid_elevations))
            
            print(f"Elevation range in analysis area: {min_elev:.1f} to {max_elev:.1f}{'ft' if is_feet else 'm'}", file=sys.stderr)
            print(f"Observer elevation relative to surroundings: {surface_elevation - min_elev:.1f}{'ft' if is_feet else 'm'} above lowest point", file=sys.stderr)
            
            # Use equipment height for viewshed calculation
            # -ox: Observer X coordinate
            # -oy: Observer Y coordinate
            # -oz: Observer height (equipment height)
            # -md: Maximum distance to analyze
            # -cc: Curvature coefficient (0.75 for radio/equipment LOS - accounts for RF refraction)
            cmd = f"gdal_viewshed -ox {observer_x} -oy {observer_y} -oz {equipment_height_ft} -md {max_distance} -cc 0.75 {dsm_path} {viewshed_path}"
            print(f"Running: {cmd}", file=sys.stderr)
            
            try:
                run(cmd, shell=True, check=True, stderr=PIPE, text=True)
            except CalledProcessError as e:
                print(f"GDAL error: {e.stderr}", file=sys.stderr)
                return None
            
            # Read results and convert to GeoJSON
            with rasterio.open(viewshed_path) as viewshed:
                data = viewshed.read(1)
                
                # Verify viewshed calculation worked
                unique_vals = np.unique(data)
                if not np.array_equal(unique_vals, [0, 255]):
                    print(f"Warning: Unexpected viewshed values: {unique_vals}", file=sys.stderr)
                
                # GDAL viewshed output values:
                # 0 = not visible (out of sight)
                # 255 = visible from observer point
                mask = data == 255  # Get visible areas
                
                # Create a distance grid to identify pixels within max_distance
                y, x = np.ogrid[:data.shape[0], :data.shape[1]]
                center_y, center_x = data.shape[0] // 2, data.shape[1] // 2
                distances = np.sqrt((x - center_x)**2 + (y - center_y)**2)
                pixels_in_range = distances <= (max_distance / dsm.res[0])  # Convert max_distance to pixels
                
                # Calculate visibility statistics (only within circle)
                visible_count = np.sum(mask & pixels_in_range)
                total_pixels = np.sum(pixels_in_range)
                coverage_percent = (visible_count/total_pixels*100)
                area_width = data.shape[1] * dsm.res[0]
                area_height = data.shape[0] * dsm.res[1]
                units = 'feet' if is_feet else 'meters'
                
                print(f"\nAnalysis Results:", file=sys.stderr)
                print(f"- Coverage Area: {area_width:.1f} x {area_height:.1f} {units}", file=sys.stderr)
                print(f"- Grid Size: {data.shape[1]} x {data.shape[0]} pixels", file=sys.stderr)
                print(f"- Visible Coverage: {coverage_percent:.1f}% ({visible_count:,} of {total_pixels:,} pixels)", file=sys.stderr)
                
                # Convert visible areas to GeoJSON polygons
                features = []
                
                # Add observer point as a feature
                transformer_back = Transformer.from_crs(dsm.crs, CRS("EPSG:4326"), always_xy=True)
                observer_lng, observer_lat = transformer_back.transform(observer_x, observer_y)
                features.append({
                    'type': 'Feature',
                    'geometry': {
                        'type': 'Point',
                        'coordinates': [float(observer_lng), float(observer_lat)]
                    },
                    'properties': {
                        'type': 'observer',
                        'elevation': float(surface_elevation + equipment_height_ft),
                        'units': 'feet' if is_feet else 'meters',
                        'marker-color': '#ff0000',  # Red marker
                        'marker-size': 'medium',
                        'marker-symbol': 'camera'
                    }
                })

                
                # Add visible areas
                polygons_added = 0
                # Note: shapes() will return 1 for True values in the mask
                for geom, val in shapes(mask.astype('uint8'), transform=viewshed.transform):
                    if val == 1:  # val == 1 means True in our mask (area was visible)
                        # Transform geometry coordinates from DSM CRS to WGS84
                        coords = geom['coordinates']
                        transformed_coords = []
                        for ring in coords:
                            transformed_ring = []
                            for point in ring:
                                lng, lat = transformer_back.transform(point[0], point[1])
                                transformed_ring.append([lng, lat])
                            transformed_coords.append(transformed_ring)
                        geom['coordinates'] = transformed_coords
                        
                        # Calculate centroid of the first ring (outer boundary)
                        if transformed_coords and transformed_coords[0]:
                            points = transformed_coords[0]
                            centroid_lng = sum(p[0] for p in points) / len(points)
                            centroid_lat = sum(p[1] for p in points) / len(points)
                        
                        polygons_added += 1
                        features.append({
                            'type': 'Feature',
                            'geometry': geom,
                            'properties': {
                                'type': 'viewshed',
                                'visible': True,
                                'latitude': float(centroid_lat),
                                'longitude': float(centroid_lng),
                                'fill': '#00ff00',  # Green fill
                                'fill-opacity': 0.2,  # Semi-transparent
                                'stroke': '#00ff00',  # Green border
                                'stroke-width': 1
                            }
                        })
                print(f"\nPolygons added to GeoJSON: {polygons_added}", file=sys.stderr)

                # Add analysis range circle using NumPy
                num_points = 64  # Number of points to make the circle smooth
                angles = np.linspace(0, 2 * np.pi, num_points, endpoint=True)
                # Calculate points on circle in DSM coordinates
                circle_x = observer_x + max_distance * np.cos(angles)
                circle_y = observer_y + max_distance * np.sin(angles)
                # Transform all points back to WGS84 at once
                circle_lng, circle_lat = transformer_back.transform(circle_x, circle_y)
                # Convert to list of [lng, lat] points
                circle_points = [[float(lng), float(lat)] for lng, lat in zip(circle_lng, circle_lat)]
                
                # Add the circle as a feature
                features.append({
                    'type': 'Feature',
                    'geometry': {
                        'type': 'LineString',
                        'coordinates': circle_points
                    },
                    'properties': {
                        'type': 'analysis_range',
                        'radius': float(max_distance),
                        'units': 'feet' if is_feet else 'meters',
                        'stroke': '#0000ff',  # Blue circle
                        'stroke-width': 2,
                        'stroke-dasharray': [5, 5],  # Dashed line
                        'stroke-opacity': 0.8
                    }
                })

                result = {
                    'type': 'FeatureCollection',
                    'features': features
                }
                
                # Cleanup temporary file
                try:
                    os.unlink(viewshed_path)
                except Exception as e:
                    print(f"Warning: Could not delete temporary file: {e}", file=sys.stderr)
                
                return result
                
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        return None

if __name__ == "__main__":
    if len(sys.argv) != 6:  # Script name + 5 arguments = 6 total
        print("Usage: python process_dsm.py <dsm_path> <longitude> <latitude> <height_ft> <max_distance>", file=sys.stderr)
        sys.exit(1)
    
    try:
        dsm_path = sys.argv[1]
        longitude = float(sys.argv[2])
        latitude = float(sys.argv[3])
        height_ft = float(sys.argv[4])
        max_distance = float(sys.argv[5])   
        
        result = calculate_los(dsm_path, longitude, latitude, height_ft, max_distance)
    except ValueError as e:
        print(f"Error: Invalid number format - {str(e)}", file=sys.stderr)
        sys.exit(1)
    if result:
        print(json.dumps(result))