import { Controller, Post, Req, Res, HttpStatus } from '@nestjs/common';
import { FastifyRequest, FastifyReply } from 'fastify';
import { AppService } from './app.service';

@Controller()
export class AppController {
  constructor(private readonly appService: AppService) {}

  @Post('viewshed')
  async getViewshed(
    @Req() req: FastifyRequest,
    @Res() reply: FastifyReply,
  ): Promise<void> {
    const dsmPath = 'uploads/usgs_l_lasda.tif';
    try {
      const [lon, lat] = [-96.21095, 41.1982];
      const geojson = await this.appService.runPythonViewshed(
        dsmPath,
        lon,
        lat,
      );

      reply.type('application/json').status(HttpStatus.OK).send(geojson);
    } catch (error) {
      const message =
        error.message || 'An error occurred while processing the viewshed.';
      reply
        .status(
          error.message.includes('outside the DSM extent')
            ? HttpStatus.BAD_REQUEST
            : HttpStatus.INTERNAL_SERVER_ERROR,
        )
        .send({ error: message });
    }
  }
}
