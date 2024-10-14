# A Very "Basic" RabbitMQ Exporter

Provides a "super simple" RabbitMq exporter that exposes metrics and healthz endpoints.  Only a handful of global celery queue metrics are reported:
 - `rabbitmq_queue_messages` - The message queue length
 - `rabbitmq_queue_message_bytes` - The message queue size in bytes
 - `rabbitmq_queue_messages_ready` - The number of messages ready to be consumed
 - `rabbitmq_queue_messages_unacknowledged` - The number of messages that have been delivered but not yet acknowledged
 - `rabbitmq_queue_consumers` - The number of consumers on the queue

 Each metric exposes a 'queue' label with the queue name.

 ### Endpoints
 - `/metrics` - The metrics endpoint
 - `/healthz` - The healthz endpoint.  Returns a non-200 response when it can't reach RabbitMQ successfuly.
Endpoints are hard-coded to listen on port 9090.

 # Why?

 RabbitMQ exposes a native prometheus management plugin.  If you're able to use that its much better, but services like AmazonMQ don't expose that
 endpoint/plugin becaus they'd rather you pay a lot of money to deal with their eccentric CloudWatch API.  This is a burden if you're just running a 
 simple prometheus stack, so this little script exists to export some simple information from RabbitMQ's management API directly.  Its designed to 
 work well in a prometheus/kubernetes environment.

 This exporter is simple, stateless, low resource, and reliable.  The server is implemented using pure async methods.  Each request to the `/metrics` triggers its own http request to RabbitMQ to get the queue information in real-time (eg no side-polling).

 # Usage
 ### Run it
 You can call the script directly with a `--url` encoding the user/pass/host:

 ```bash
 python exporter.py --url amqps://user:pass@XXX-XXX-XXX.mq.us-west-1.amazonaws.com
 ```
 The scheme/port/path for the url is always ignored and https:443 is used against the specified hostname.  The user and pass can also be specified using `--user` and `--password`.


 ### Run it in Docker
 ```bash
 docker run -p 9090:9090 -e MQ_URL=https://user:pass@XXX-XXX-XXX.mq.us-west-1.amazonaws.com ghcr.io/sabeechen/rabbitmq_exporter
 ```

The args can also be specified as environment variables:
 - `MQ_URL` - The RabbitMQ API endpoint (amqp:// or https:// with or without credentials)
 - `MQ_USER` - RabbitMQ username
 - `MQ_PASSWORD` - RabbitMQ password
 - `MQ_TIMEOUT` - RabbitMQ http timeout (seconds)
