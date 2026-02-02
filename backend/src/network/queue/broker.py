from dramatiq.broker import MessageProxy
from dramatiq.brokers.stub import StubBroker


class EagerBroker(StubBroker):
    """Used to simulate CELERY_ALWAYS_EAGER behavior"""

    def process_message(self, message):
        message_proxy = MessageProxy(message=message)
        try:
            actor = self.get_actor(message.actor_name)

            if 'pipe_target' in message.options:
                result = actor(*message.args, **message.kwargs)
                actor = self.get_actor(message.options['pipe_target']['actor_name'])
                if message.options['pipe_target']['options'].get('pipe_ignore', False):
                    extra_args = tuple()
                else:
                    extra_args = (result,)
                actor.send_with_options(
                    args=message.options['pipe_target']['args'] + extra_args,
                    kwargs=message.options['pipe_target']['kwargs'],
                    **message.options['pipe_target']['options'],
                )
            else:
                actor(*message.args, **message.kwargs)
        except Exception as exc:
            message_proxy.stuff_exception(exc)
            message_proxy.fail()

        # @TODO Middlewares are not called with Eager atm
        # self.emit_after('process_message', message_proxy)

    def enqueue(self, message, *, delay=None):
        self.process_message(message)
