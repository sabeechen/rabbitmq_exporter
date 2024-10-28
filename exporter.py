"""
Uses the RabbitMQ management API to fetch "queue global" information, such as queue length, and then expose it in a
prometheus compatible format on a /metrics endpoint.
Reference: https://rawcdn.githack.com/rabbitmq/rabbitmq-server/v4.0.2/deps/rabbitmq_management/priv/www/api/index.html
"""

import base64
from io import StringIO
import os
from urllib.parse import urlparse
import aiohttp
from aiohttp import web
import async_timeout
import argparse
import asyncio
import logging

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

class Server:
    def __init__(self, url: str, auth: bytes|None, timeout: float, verify_ssl: bool):
        self.url = url
        self.auth = auth
        self.timeout = timeout
        self.verify_ssl = verify_ssl

        self.up = False

    async def fetch(self, session, url):
        headers = {}
        if self.auth:
            headers = {'Authorization': f'Basic {self.auth}'}
        async with async_timeout.timeout(self.timeout):
            async with session.get(url, headers=headers, verify_ssl=self.verify_ssl) as response:
                return await response.json()

    async def _healthz(self, _request = None):
        return web.Response(status=200 if self.up else 500)

    async def _metrics(self, _request = None):
        async with aiohttp.ClientSession() as session:
            try:
                queues = await self.fetch(session, self.url + '/api/queues')

                # Find only queues that are not ephemeral (this filters out consumer queues)
                queues = [queue for queue in queues if 'x-expires' not in queue.get('arguments', {})]

                # produce a prometheus-style response with metric data
                resp = StringIO()
                for queue in queues:
                    name = queue['name']
                    resp.write(f"rabbitmq_queue_messages{{queue=\"{name}\"}} {queue.get('messages', 0)}\n")
                    resp.write(f"rabbitmq_queue_message_bytes{{queue=\"{name}\"}} {queue.get('message_bytes', 0)}\n")
                    resp.write(f"rabbitmq_queue_messages_ready{{queue=\"{name}\"}} {queue.get('messages_ready', 0)}\n")
                    resp.write(f"rabbitmq_queue_messages_unacknowledged{{queue=\"{name}\"}} {queue.get('messages_unacknowledged', 0)}\n")
                    resp.write(f"rabbitmq_queue_consumers{{queue=\"{name}\"}} {queue.get('consumers', 0)}\n")
                self.up = True
                return web.Response(status=200, text=resp.getvalue())
            except Exception as e:
                self.up = False
                logger.exception("Error fetching metrics")
                return web.Response(status=500, text=str(e))

    async def _index(self, _request = None):
        return web.HTTPMovedPermanently(location='/metrics')

    async def ping(self):
        await self._metrics()

    async def run(self):
        app = web.Application()
        app.router.add_get('/healthz', self._healthz)
        app.router.add_get('/metrics', self._metrics)
        app.router.add_get('/', self._index)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', 9090)
        logger.info("Starting server on 0.0.0.0:9090")
        await site.start()

async def main():
    parser = argparse.ArgumentParser(description="Python app exposing metrics and healthz endpoints")
    parser.add_argument("--url", default=os.environ.get("MQ_URL", ""), help="The RabbitMQ API endpoint (amqp:// or http(s):// with or without credentials)")
    parser.add_argument("--user", default=os.environ.get("MQ_USER", ""), help="RabbitMQ username")
    parser.add_argument("--password", default=os.environ.get("MQ_PASSWORD", ""), help="RabbitMQ password")
    parser.add_argument("--timeout", default=float(os.environ.get("MQ_TIMEOUT", "30")), type=float, help="RabbitMQ http timeout (seconds)")
    parser.add_argument("--verify-ssl", default=os.environ.get("MQ_VERIFY_SSL", "true").lower() == "true", type=bool, help="Verify SSL")
    args = parser.parse_args()

    host = ""
    user = ""
    password = ""

    parsed_url = urlparse(args.url)
    host = parsed_url.hostname
    user = parsed_url.username
    password = parsed_url.password

    if args.user:
        user = args.user
    if args.password:
        password = args.password

    if not host:
        raise ValueError("Host must be specified")

    auth =  None
    if user and password:
        auth = base64.b64encode(f"{user}:{password}".encode()).decode()


    server = Server(f"https://{host}", auth, args.timeout, args.verify_ssl)
    await server.run()

    while True:
        # Even if we nobody ask for metrics, periodically ping rabbitmq so the /healthz metric stays fresh.
        try:
            await server.ping()
        except Exception:
            logger.exception("Error pinging rabbitmq")
        await asyncio.sleep(120)


if __name__ == '__main__':
    asyncio.run(main())
