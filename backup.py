import sys
import json
import rasterio
from rasterio.features import shapes
from pyproj import Transformer, CRS
from subprocess import run, CalledProcessError
import os

def process_dsm(dsm_path, lat, lon):
    viewshed_path = 'viewshed.tif'
    try:
        print(f"DEBUG: Starting process_dsm with dsm_path={dsm_path}, lon={lon}, lat={lat}", file=sys.stderr)
        # Open DSM to get CRS and transform
        try:
            with rasterio.open(dsm_path) as src:
                print("DEBUG: Successfully opened DSM file.", file=sys.stderr)
                dsm_crs = src.crs
                transform = src.transform

                # Transform point from WGS84 to DSM CRS
                transformer = Transformer.from_crs(CRS("EPSG:4326"), dsm_crs, always_xy=True)
                x, y = transformer.transform(float(lon), float(lat))
                print(f"DEBUG: Transformed point to DSM CRS: ({x}, {y})", file=sys.stderr)

                # Check if point is within DSM bounds
                if not (src.bounds.left <= x <= src.bounds.right and src.bounds.bottom <= y <= src.bounds.top):
                    print("DEBUG: Point is outside the DSM extent.", file=sys.stderr)
                    return
        except Exception as e:
            print(f"ERROR: Failed to open DSM file: {e}", file=sys.stderr)
            return
        
        # Compute viewshed using gdal_viewshed
        cmd = f"gdal_viewshed -ox {x} -oy {y} -oz 0 -b 1 {dsm_path} {viewshed_path}"
        print(f"DEBUG: Running command: {cmd}", file=sys.stderr)
        try:
            run(cmd, shell=True, check=True)
            print("DEBUG: gdal_viewshed command executed successfully.", file=sys.stderr)
        except CalledProcessError as e:
            print(f"ERROR: gdal_viewshed failed with error: {e}", file=sys.stderr)
            return

        # Convert viewshed to GeoJSON
        try:
            with rasterio.open(viewshed_path) as viewshed_src:
                print("DEBUG: Opened viewshed file successfully.", file=sys.stderr)
                viewshed_data = viewshed_src.read(1)
                print("DEBUG: Read viewshed data.", file=sys.stderr)
                visible_shapes = shapes(viewshed_data, transform=viewshed_src.transform, mask=viewshed_data == 255)
                print("DEBUG: Extracted shapes from viewshed data.", file=sys.stderr)
                
                # Transform coordinates back to WGS84
                transformer_back = Transformer.from_crs(dsm_crs, CRS("EPSG:4326"), always_xy=True)
                features = []
                for shape, value in visible_shapes:
                    if value == 255:
                        transformed_coords = []
                        for coord in shape['coordinates'][0]:
                            cx, cy = transformer_back.transform(coord[0], coord[1])
                            transformed_coords.append([cx, cy])
                        polygon = {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [transformed_coords]}}
                        features.append(polygon)
                
                # Output GeoJSON to stdout
                geojson = {"type": "FeatureCollection", "features": features}
                print("DEBUG: GeoJSON prepared. Outputting now.", file=sys.stderr)
                json.dump(geojson, sys.stdout)
                sys.stdout.flush()
        except Exception as e:
            print(f"ERROR: Failed during viewshed processing: {e}", file=sys.stderr)
    finally:
        # Cleanup temporary file
        try:
            os.remove(viewshed_path)
            print("DEBUG: Cleaned up temporary viewshed file.", file=sys.stderr)
        except Exception as e:
            print(f"WARNING: Could not remove temporary file {viewshed_path}: {e}", file=sys.stderr)

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python process_dsm.py <dsm_path> <lon> <lat>", file=sys.stderr)
        sys.exit(1)
    dsm_path, lon, lat = sys.argv[1], sys.argv[2], sys.argv[3]
    process_dsm(dsm_path, lon, lat)
