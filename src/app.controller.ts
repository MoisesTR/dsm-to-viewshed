import { Controller, Post, Res, HttpStatus, Body } from '@nestjs/common';
import { FastifyReply } from 'fastify';
import { AppService } from './app.service';
import { ViewshedResponse } from './dto/viewshed.dto';

interface ViewshedRequest {
  lng: number;
  lat: number;
}

@Controller()
export class AppController {
  constructor(private readonly appService: AppService) { }

  @Post('viewshed')
  async getViewshed(
    @Body() body: ViewshedRequest,
    @Res() reply: FastifyReply,
  ): Promise<void> {
    const dsmPath = 'uploads/usgs_l_lasda.tif';
    try {
      const { lng, lat } = body;
      const geojson: ViewshedResponse = await this.appService.runPythonViewshed(
        dsmPath,
        lng,
        lat
      );

      reply.send(geojson);
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
