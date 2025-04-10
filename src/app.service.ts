import { Injectable, InternalServerErrorException, BadRequestException } from '@nestjs/common';
import { spawn } from 'child_process';
import { existsSync } from 'fs';
import { ViewshedResponse } from './dto/viewshed.dto';

@Injectable()
export class AppService {
  async runPythonViewshed(dsmPath: string, lng: number, lat: number): Promise<ViewshedResponse> {
    if (!existsSync(dsmPath)) {
      throw new BadRequestException(`DSM file not found: ${dsmPath}`);
    }

    if (lng < -180 || lng > 180 || lat < -90 || lat > 90) {
      throw new BadRequestException('Invalid longitude or latitude values');
    }

    console.log(`============================================`);
    console.log(`Starting Python viewshed calculation...`);
    console.log(`============================================`);

    return new Promise<ViewshedResponse>((resolve, reject) => {
      const pythonProcess = spawn('python3', [
        './process_dsm.py',
        dsmPath,
        lng.toString(),
        lat.toString()
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
          // Get the last non-empty line as JSON output
          const outputLines = stdoutData.split('\n').filter(line => line.trim() !== '');
          const jsonLine = outputLines[outputLines.length - 1];

          if (!jsonLine) {
            throw new Error('Empty response from Python script');
          }

          // Parse and validate the GeoJSON
          const result = JSON.parse(jsonLine);
          if (result.type !== 'FeatureCollection' || !Array.isArray(result.features)) {
            throw new Error('Invalid GeoJSON format');
          }

          resolve(result as ViewshedResponse);
        } catch (e) {
          console.error('Failed to parse Python output:', e);
          console.error('Raw output:', stdoutData.substring(0, 100));
          reject(new InternalServerErrorException(`Invalid viewshed format: ${e.message}`));
        }
      });

      // Handle process errors
      pythonProcess.on('error', (err) => {
        console.error('Failed to start Python process:', err);
        reject(new InternalServerErrorException('Failed to start viewshed calculation'));
      });
    });
  }
}
