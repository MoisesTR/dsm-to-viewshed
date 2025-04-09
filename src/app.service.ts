import { Injectable, InternalServerErrorException } from '@nestjs/common';
import { exec } from 'child_process';

@Injectable()
export class AppService {
  // Note: The function now expects dsmPath, lon, lat.
  runPythonViewshed(dsmPath: string, lon: number, lat: number): Promise<any> {
    return new Promise((resolve, reject) => {
      const pythonExecutable = './venv/bin/python';
      const scriptPath = './process_dsm.py';
      // Pass arguments in order: dsmPath, lon, lat
      const cmd = `${pythonExecutable} ${scriptPath} ${dsmPath} ${lon} ${lat}`;

      console.log(`Running Python script: ${cmd}`);

      const child = exec(cmd, (error, stdout, stderr) => {
        if (error) {
          console.error(`Error executing Python script: ${error.message}`);
          console.error(`stderr: ${stderr}`);
          return reject(
            new InternalServerErrorException('Error running viewshed script'),
          );
        }
        // Log stdout output from the Python script
        console.log(`stdout: ${stdout}`);
        resolve(stdout);
      });

      // Log real-time output from the Python process:
      if (child.stdout) {
        child.stdout.on('data', (data) => {
          console.log(`[Python stdout]: ${data}`);
        });
      }
      if (child.stderr) {
        child.stderr.on('data', (data) => {
          console.error(`[Python stderr]: ${data}`);
        });
      }
    });
  }
}
