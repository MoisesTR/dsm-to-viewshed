import { NestFactory } from '@nestjs/core';
import { FastifyAdapter } from '@nestjs/platform-fastify';
import { AppModule } from './app.module';
import fastify from 'fastify';

async function bootstrap() {
  const server = fastify({ logger: false });
  const app = await NestFactory.create(AppModule, new FastifyAdapter(server));
  await app.init();
  await app.listen(3000, '0.0.0.0');
}
bootstrap();
