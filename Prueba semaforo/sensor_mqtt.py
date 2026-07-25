"""Puente entre el sensor (ESP32/Wokwi vía MQTT) y el loop del simulador.

Corre el cliente MQTT en un hilo aparte; cada mensaje recibido se mete
en una queue.Queue que el loop principal de pygame drena cada frame.
"""

import logging
import ssl
import threading

import paho.mqtt.client as mqtt

from mqtt_config import MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASSWORD, MQTT_TOPIC

DIRECCIONES_VALIDAS = {"derecha", "izquierda", "abajo", "arriba"}
TIPOS_VALIDOS = {"auto", "ambulancia", "bomberos"}

# Registro de señales recibidas del sensor (ESP32/Wokwi), aparte de logChoques.log
log_sensores = logging.getLogger("sensores")
log_sensores.setLevel(logging.INFO)
_handler = logging.FileHandler("logSensores.log")
_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
log_sensores.addHandler(_handler)


def iniciar_hilo_mqtt(cola_eventos):
    """Conecta al broker y arranca el hilo. Cada botón de la cruceta publica
    un payload "direccion:tipo" (ej. "derecha:bomberos") en MQTT_TOPIC;
    se valida y se encola como tupla (direccion, tipo) para que el loop
    principal despache el vehículo correspondiente."""

    def on_connect(client, userdata, flags, reason_code, properties=None):
        client.subscribe(MQTT_TOPIC)

    def on_message(client, userdata, msg):
        payload = msg.payload.decode(errors="replace")
        direccion, _, tipo = payload.partition(":")
        if direccion not in DIRECCIONES_VALIDAS or tipo not in TIPOS_VALIDOS:
            log_sensores.warning(f"payload inválido ignorado: {payload!r}")
            return
        log_sensores.info(f"topic={msg.topic} payload={payload}")
        cola_eventos.put((direccion, tipo))

    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    threading.Thread(target=client.loop_forever, daemon=True).start()
    return client
