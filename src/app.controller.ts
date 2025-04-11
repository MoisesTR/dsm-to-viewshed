import { Controller, Post, Res, HttpStatus, Body } from '@nestjs/common';
import { FastifyReply } from 'fastify';
import { AppService } from './app.service';
import { ViewshedResponse } from './dto/viewshed.dto';
import { ViewshedRequest } from './dto/viewshed.dto';

@Controller()
export class AppController {
  constructor(private readonly appService: AppService) { }

  @Post('viewshed')
  async calculateViewshed(
    @Body() body: ViewshedRequest,
    @Res() reply: FastifyReply,
  ): Promise<void> {
    try {
      const geojson: ViewshedResponse = await this.appService.runPythonViewshed(body);

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
