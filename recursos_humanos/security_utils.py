import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from django.conf import settings

def get_master_key():
    """Obtiene la MASTER_KEY del entorno o settings."""
    key_str = getattr(settings, 'MASTER_KEY', os.environ.get('MASTER_KEY', 'default-key-change-this-in-env'))
    # Aseguramos que sea una llave de 32 bytes para AES-256
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'sat-integration-salt',
        iterations=100000,
    )
    return kdf.derive(key_str.encode())

def generate_data_key():
    """Genera una llave aleatoria para una empresa específica."""
    return AESGCM.generate_key(bit_length=256)

def encrypt_data(data, key):
    """Cifra datos usando AES-256-GCM."""
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, data, None)
    return base64.b64encode(nonce + ciphertext).decode('utf-8')

def decrypt_data(token_b64, key):
    """Descifra datos usando AES-256-GCM."""
    data = base64.b64decode(token_b64)
    nonce = data[:12]
    ciphertext = data[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)

def cifrar_archivos_fiel(cer_content, key_content, master_key_bytes):
    """
    Cifra ambos archivos de la FIEL usando la misma Data Key.
    Retorna (cer_cifrado, key_cifrado, data_key_cifrada).
    """
    data_key = generate_data_key()
    
    # Ciframos ambos con la misma data_key
    cer_cifrado = encrypt_data(cer_content, data_key)
    key_cifrado = encrypt_data(key_content, data_key)
    
    # Protegemos la data_key con la Master Key
    data_key_cifrada = encrypt_data(data_key, master_key_bytes)
    
    return cer_cifrado, key_cifrado, data_key_cifrada

def descifrar_archivo(content_b64, data_key_cifrada_b64, master_key_bytes):
    """
    Descifra un archivo usando Envelope Encryption con errores descriptivos.
    """
    try:
        # 1. Desciframos la Data Key con la Master Key
        try:
            data_key = decrypt_data(data_key_cifrada_b64, master_key_bytes)
        except Exception as e:
            raise Exception(f"La Llave Maestra no pudo abrir la llave de datos. (Error técnico: {type(e).__name__})")
        
        # 2. Desciframos el contenido con la Data Key
        try:
            return decrypt_data(content_b64, data_key)
        except Exception as e:
            raise Exception(f"La llave de datos no coincide con el archivo cifrado. (Error técnico: {type(e).__name__})")
            
    except Exception as e:
        # Si el error es de tag inválido (MAC fail), avisamos explícitamente
        msg = str(e)
        if "InvalidTag" in msg or not msg:
            msg = "Fallo de integridad: La llave es incorrecta o los datos están corruptos."
        raise Exception(f"Error en descifrado de seguridad: {msg}")
