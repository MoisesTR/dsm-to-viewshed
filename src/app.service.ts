import { Injectable, InternalServerErrorException, BadRequestException } from '@nestjs/common';
import { spawn } from 'child_process';
import { existsSync } from 'fs';
import { ViewshedResponse } from './dto/viewshed.dto';

export interface RunPythonViewshedParams {
  lng: number;
  lat: number;
  mountHeightFt: number;
  maxDistance?: number;
}

const DSM_PATH = 'uploads/usgs_l_lasda.tif';
@Injectable()
export class AppService {
  async runPythonViewshed({ lng, lat, mountHeightFt }: RunPythonViewshedParams): Promise<ViewshedResponse> {
    if (!existsSync(DSM_PATH)) {
      throw new BadRequestException(`DSM file not found: ${DSM_PATH}`);
    }

    if (lng < -180 || lng > 180 || lat < -90 || lat > 90) {
      throw new BadRequestException('Invalid longitude or latitude values');
    }

    if (!mountHeightFt) {
      throw new BadRequestException('Mount height is required');
    }

    console.log(`============================================`);
    console.log(`Starting Python viewshed calculation...`);
    console.log(`============================================`);

    return new Promise<ViewshedResponse>((resolve, reject) => {
      const pythonProcess = spawn('python3', [
        './process_dsm.py',
        DSM_PATH,
        lng.toString(),
        lat.toString(),
        mountHeightFt.toString()
      ]);

      let stdoutData = '';
      let stderrData = '';

      pythonProcess.stderr.on('data', (data) => {
        const message = data.toString();
        process.stderr.write(message);
        stderrData += message;
      });

      pythonProcess.stdout.on('data', (data) => {
        stdoutData += data.toString();
      });

      pythonProcess.on('close', (code) => {
        if (code !== 0) {
          console.error('Python process exited with code:', code);
          reject(new InternalServerErrorException('Viewshed calculation failed'));
          return;
        }

        try {
          const lastLine = stdoutData.trim().split('\n').pop();
          if (!lastLine) {
            throw new Error('Empty response from Python script');
          }

          const result = JSON.parse(lastLine);
          if (result.type !== 'FeatureCollection' || !Array.isArray(result.features)) {
            throw new Error('Invalid GeoJSON format');
          }

          resolve(result as ViewshedResponse);
        } catch (e) {
          console.error('Failed to parse Python output:', e);
          console.error('Raw output:', stdoutData);
          reject(new InternalServerErrorException(`Invalid viewshed format: ${e.message}`));
        }
      });

      pythonProcess.on('error', (err) => {
        console.error('Failed to start Python process:', err);
        reject(new InternalServerErrorException('Failed to start viewshed calculation'));
      });
    });
  }
}
