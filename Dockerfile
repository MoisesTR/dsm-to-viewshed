FROM node:20

# Install Python, GDAL and build dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    gdal-bin \
    libgdal-dev \
    gcc \
    g++ \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Set up Python virtual environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python packages one by one to better handle errors
RUN pip install --upgrade pip wheel setuptools
RUN pip install rasterio
RUN pip install pyproj
RUN pip install scipy

# Install Node.js dependencies
COPY package.json yarn.lock ./
RUN yarn install

# Copy app files
COPY . .

EXPOSE 3000

CMD ["yarn", "start:dev"]
