import { NestFactory } from '@nestjs/core';
import { FastifyAdapter } from '@nestjs/platform-fastify';
import { AppModule } from './app.module';
import fastifyMultipart from '@fastify/multipart';
import fastify from 'fastify';

async function bootstrap() {
  const server = fastify({ logger: false });

  server.register(fastifyMultipart, {
    limits: { fileSize: 4 * 1024 * 1024 * 1024 }, // 4GB limit
  });

  const app = await NestFactory.create(AppModule, new FastifyAdapter(server));
  await app.init();
  await app.listen(3000, '0.0.0.0');
}
bootstrap();
