# DSM-to-Viewshed Service

A service that processes Digital Surface Models (DSM) to produce GeoJSON viewsheds from observer points, built with NestJS and Python/GDAL. Optimized for RF/radio line-of-sight analysis with accurate coverage calculations.

## Architecture: Sidecar Pattern

This service implements the **sidecar pattern**, where our main application is augmented by a specialized helper process. Like a motorcycle sidecar, the helper process runs alongside the main application while handling a specific task better suited to different technology.

In our implementation:

* **Main Application (Node.js)**: Handles web requests and API endpoints
* **Sidecar (Python/GDAL)**: Performs geospatial calculations on demand

Our Node.js application spawns Python processes using `child_process.exec()` when a viewshed calculation is needed. It passes coordinates and DSM file information via command-line arguments and receives the processed GeoJSON viewshed results via stdout.

### Sidecar Pattern Implementation
* **Process-based approach**: Node.js spawns Python script as needed
* **Data flow**: Parameters via CLI args, results via stdout as GeoJSON
* **Key advantage**: Uses GDAL's built-in `gdal_viewshed` tool without complex custom algorithms
* **Deployment**: Single container with both Node.js and Python+GDAL installed

## Development with Docker

### Prerequisites
- Docker Desktop

### Start Development
```bash
# Start the service
$ docker compose up

# Stop the service
$ docker compose down
```

The service will be available at http://localhost:3000

### What's Included
- Node.js 20 for the web service
- Python 3 with GDAL for geospatial processing
- Hot reload enabled (changes are reflected automatically)

## Viewshed Analysis Features

### RF Propagation Modeling
- Uses 0.75 curvature coefficient for standard RF refraction
- Accounts for earth's curvature in long-range calculations
- Coverage calculated within circular analysis boundary

### Elevation Handling
- Supports DSMs in feet (US) or meters
- Combines surface elevation with equipment height
- Reports min/max elevations in analysis area

### GeoJSON Output
- Visible areas with lat/lng centroids
- Observer point with elevation metadata
- Analysis range boundary circle
- Coverage statistics within max range

## Deployment
- **Local**: Uses Docker Compose
- **Production**: Single container with Node.js and Python+GDAL
