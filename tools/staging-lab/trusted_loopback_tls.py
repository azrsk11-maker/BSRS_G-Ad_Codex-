"""Normal TLS validation for the fixed synthetic loopback origin."""
import socket
import ssl


def server_context(cert, key):
    if not cert or not key:
        raise ValueError('Explicit test TLS certificate and key required')
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    return context


def verify_loopback_tls(port):
    context = ssl.create_default_context()
    with socket.create_connection(('127.0.0.1', port), timeout=3) as connection:
        with context.wrap_socket(connection, server_hostname='127.0.0.1'):
            pass
