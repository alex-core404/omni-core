import os
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

SECRET_KEY = os.getenv("AES_SECRET_KEY", "12345678901234567890123456789012")

def encrypt_message(message: str) -> str:
    iv = os.urandom(16)
    key = SECRET_KEY.encode()[:32]
    cipher = Cipher(algorithms.AES(key), modes.CFB(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(message.encode()) + encryptor.finalize()
    return base64.b64encode(iv + encrypted).decode()

def decrypt_message(encrypted_message: str) -> str:
    data = base64.b64decode(encrypted_message)
    iv = data[:16]
    encrypted = data[16:]
    key = SECRET_KEY.encode()[:32]
    cipher = Cipher(algorithms.AES(key), modes.CFB(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    return (decryptor.update(encrypted) + decryptor.finalize()).decode()

