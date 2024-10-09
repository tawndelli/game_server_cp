import pika, sys, os

connection = pika.BlockingConnection(pika.ConnectionParameters('127.0.0.1'))
channel = connection.channel()

# channel.queue_declare(queue='game')

# channel.basic_publish(exchange='',
#                       routing_key='game',
#                       body='Hello World!')

# print(" [x] Sent 'Hello World!'")

# connection.close()

def main():
    def callback(ch, method, properties, body):
        print(f" [x] Received {body}")

    channel.basic_consume(queue='game',
                        auto_ack=True,
                        on_message_callback=callback)

    print(' [*] Waiting for messages. To exit press CTRL+C')
    
    channel.start_consuming()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)

