import asyncio
from aiosmtpd.controller import Controller

class CustomSMTPHandler:
    async def handle_DATA(self, server, session, envelope):
        print('Message from:', envelope.mail_from)
        print('Message for:', envelope.rcpt_tos)
        print('Message data:\n', envelope.content.decode())
        return '250 Message accepted for delivery'

    async def handle_RCPT(self, server, session, envelope, rcpt_options):
        print('RCPT to:', rcpt_options)
        return '250 Message accepted for delivery'

if __name__ == '__main__':
    handler = CustomSMTPHandler()
    controller = Controller(handler, port=2525)
    controller.start()
    print("SMTP server is running on localhost:2525")
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        controller.stop()