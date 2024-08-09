from flask import Flask
from flask_sock import Sock
from cashmere import Cashmere

app = Flask(__name__)
sock = Sock(app)

@sock.route('/chat')
def chat(ws):
  # initialize assistant
  cashmere = Cashmere()
  ws.send(cashmere.process())

  while True:
    message = ws.receive()
    if message == 'quit':
      cashmere.end_conversation()
      break

    cashmere.add_message(message)
    ws.send(cashmere.process())


