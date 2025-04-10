import sys
import json
import numpy as np
import rasterio
from rasterio.features import shapes
from pyproj import Transformer, CRS
from subprocess import run, CalledProcessError, PIPE

def calculate_los(dsm_path, lng, lat):
    """
    Calculate line of sight from an observer point using GDAL viewshed.
    
    Args:
        dsm_path: Path to the Digital Surface Model (DSM) file
        lng: Observer longitude
        lat: Observer latitude
        
    Returns:
        GeoJSON FeatureCollection of visible areas
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
            max_distance = 500    # feet radius (about 0.19 miles)
            if not is_feet:
                # Convert feet to meters if DSM is in meters
                max_distance = max_distance * 0.3048
            
            # Convert lat/lng to DSM coordinates
            transformer = Transformer.from_crs(CRS("EPSG:4326"), dsm.crs, always_xy=True)
            obs_x, obs_y = transformer.transform(float(lng), float(lat))
            
            # Get elevation directly from DSM (already includes ground/roof height)
            obs_height = next(dsm.sample([(obs_x, obs_y)]))[0]
            if obs_height is None:
                print("Error: Could not get elevation", file=sys.stderr)
                return None
            
            print(f"Observer elevation from DSM: {obs_height:.1f}{'ft' if is_feet else 'm'}", file=sys.stderr)
            
            # Run GDAL viewshed in NORMAL mode (default)
            # Output will be Byte type where:
            # 0 = not visible (out of sight)
            # 1 = visible
            observer_offset = 6  # Negative of surface height to get to zero
            cmd = f"gdal_viewshed -ox {obs_x} -oy {obs_y} -oz {observer_offset} -md {max_distance} {dsm_path} {viewshed_path}"
            print(f"Running: {cmd}", file=sys.stderr)
            
            try:
                run(cmd, shell=True, check=True, stderr=PIPE, text=True)
            except CalledProcessError as e:
                print(f"GDAL error: {e.stderr}", file=sys.stderr)
                return None
            
            # Read results and convert to GeoJSON
            with rasterio.open(viewshed_path) as viewshed:
                data = viewshed.read(1)
                
                # Debug viewshed values
                unique_vals = np.unique(data)
                print(f"Unique values in viewshed: {unique_vals}", file=sys.stderr)
                
                # GDAL viewshed output values:
                # 0 = not visible (out of sight)
                # 255 = visible from observer point
                mask = data == 255  # Get visible areas
                
                # Print visibility stats
                visible = np.sum(mask)
                total = mask.size
                print(f"Viewshed analysis:", file=sys.stderr)
                print(f"- Total pixels: {total}", file=sys.stderr)
                print(f"- Visible pixels: {visible} ({visible/total*100:.1f}%)", file=sys.stderr)
                print(f"- Data shape: {data.shape}", file=sys.stderr)
                print(f"- Non-zero mask values: {np.count_nonzero(mask)}", file=sys.stderr)
                
                # Convert visible areas to GeoJSON polygons
                features = []
                
                # Add observer point as a feature
                transformer_back = Transformer.from_crs(dsm.crs, CRS("EPSG:4326"), always_xy=True)
                obs_lng, obs_lat = transformer_back.transform(obs_x, obs_y)
                features.append({
                    'type': 'Feature',
                    'geometry': {
                        'type': 'Point',
                        'coordinates': [float(obs_lng), float(obs_lat)]
                    },
                    'properties': {
                        'type': 'observer',
                        'elevation': float(obs_height),
                        'units': 'feet' if is_feet else 'meters',
                        'marker-color': '#ff0000',  # Red marker
                        'marker-size': 'medium',
                        'marker-symbol': 'camera'
                    }
                })
                
                # Debug first few visible pixels if any
                if visible > 0:
                    visible_y, visible_x = np.where(mask)
                    print("\nFirst 5 visible pixels:", file=sys.stderr)
                    for i in range(min(5, len(visible_y))):
                        px_x, px_y = visible_x[i], visible_y[i]
                        geo_x, geo_y = viewshed.transform * (px_x, px_y)
                        lng, lat = transformer_back.transform(geo_x, geo_y)
                        print(f"  Pixel {i+1}: ({lng:.6f}, {lat:.6f})", file=sys.stderr)
                
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
    if len(sys.argv) != 4:
        print("Usage: python process_dsm.py <dsm_path> <longitude> <latitude>", file=sys.stderr)
        sys.exit(1)
        
    result = calculate_los(sys.argv[1], sys.argv[2], sys.argv[3])
    if result:
        print(json.dumps(result))