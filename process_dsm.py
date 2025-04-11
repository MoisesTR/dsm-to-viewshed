import sys
import json
import numpy as np
import rasterio
from rasterio.features import shapes
from pyproj import Transformer, CRS
from subprocess import run, CalledProcessError, PIPE

def calculate_los(dsm_path, lng, lat, equipment_height_ft, max_distance):
    """
    Calculate line of sight from an observer point using GDAL viewshed.
    
    Args:
        dsm_path: Path to the Digital Surface Model (DSM) file
        lng: Observer longitude in WGS84
        lat: Observer latitude in WGS84
        equipment_height_ft: Height of equipment above ground in feet
        
    Returns:
        GeoJSON FeatureCollection containing:
        - MultiPolygon of visible areas
        - Point feature of observer location with elevation metadata
    """
    try:
        # Create temporary file for viewshed output
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.tif', delete=False) as tmp:
            viewshed_path = tmp.name
        
        # Open DSM and get observer location
        with rasterio.open(dsm_path) as dsm:
            # Check if DSM is in feet (US units)
            crs_wkt = dsm.crs.to_wkt().lower()
            is_feet = 'foot' in crs_wkt or 'ft' in crs_wkt
            if not is_feet:
                print("Warning: DSM might not be in US feet", file=sys.stderr)
            
            # Set max distance in DSM units
            if not is_feet:
                # Convert feet to meters if DSM is in meters
                max_distance = max_distance * 0.3048
            
            # Convert WGS84 lat/lng to DSM coordinate system
            transformer = Transformer.from_crs(CRS("EPSG:4326"), dsm.crs, always_xy=True)
            observer_x, observer_y = transformer.transform(float(lng), float(lat))
            
            # Get surface elevation from DSM at observer point (includes buildings)
            surface_elevation = next(dsm.sample([(observer_x, observer_y)]))[0]
            if surface_elevation is None:
                print("Error: Could not get surface elevation from DSM", file=sys.stderr)
                return None
            
            # Calculate total height by adding equipment height to surface elevation
            equipment_height = equipment_height_ft
            if not is_feet:
                equipment_height = equipment_height * 0.3048  # Convert to meters if needed
            
            total_height = surface_elevation + equipment_height
            
            print(f"Surface elevation from DSM: {surface_elevation:.1f}{'ft' if is_feet else 'm'}", file=sys.stderr)
            print(f"Equipment height above surface: {equipment_height:.1f}{'ft' if is_feet else 'm'}", file=sys.stderr)
            print(f"Total height for visibility: {total_height:.1f}{'ft' if is_feet else 'm'}", file=sys.stderr)
            
            # GDAL viewshed parameters explanation:
            # -ox: Observer X coordinate in the DSM's coordinate system
            # -oy: Observer Y coordinate in the DSM's coordinate system
            # -oz: Height above ground to calculate visibility from
            # -md: Maximum distance to calculate visibility (in DSM units)
            # Additional optional parameters (not used here):
            # -vv: Vertical angle of vision in degrees (default is 180)
            # -b: Input band to use (default is 1)
            # -a: Algorithm (default=NORMAL):
            #     NORMAL = Visible/Not visible binary output
            #     INTERPOLATE = Account for earth curvature
            #
            # Note: We don't use -ov (observer height) as it would add extra height
            # on top of -oz. Instead, we directly specify the desired height with -oz.
            
            # Use total height for viewshed calculation
            cmd = f"gdal_viewshed -ox {observer_x} -oy {observer_y} -oz {total_height} -md {max_distance} {dsm_path} {viewshed_path}"
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
                
                # Calculate visibility statistics
                visible_count = np.sum(mask)
                total_pixels = mask.size
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
                        'elevation': float(total_height),
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
                        
                        polygons_added += 1
                        features.append({
                            'type': 'Feature',
                            'geometry': geom,
                            'properties': {
                                'type': 'viewshed',
                                'visible': True,
                                'fill': '#00ff00',  # Green fill
                                'fill-opacity': 0.2,  # Semi-transparent
                                'stroke': '#00ff00',  # Green border
                                'stroke-width': 1
                            }
                        })
                print(f"\nPolygons added to GeoJSON: {polygons_added}", file=sys.stderr)
                
                result = {
                    'type': 'FeatureCollection',
                    'features': features
                }
                
                # Cleanup temporary file
                import os
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