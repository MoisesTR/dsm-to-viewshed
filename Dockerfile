FROM node:20-slim

# Install Python and GDAL
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    gdal-bin \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Set up Python virtual environment and install packages
RUN python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir rasterio pyproj
ENV PATH="/opt/venv/bin:$PATH"

# Install Node.js dependencies
COPY package.json yarn.lock ./
RUN yarn install

# Copy app files
COPY . .

EXPOSE 3000

CMD ["yarn", "start:dev"]
