"""Contraseñas con hash scrypt y tokens de sesión. Solo usa la biblioteca estándar."""

import base64
import hashlib
import hmac
import secrets

# Parámetros de scrypt: unos 16 MB de memoria y decenas de milisegundos por verificación.
_N, _R, _P = 2**14, 8, 1


def _b64(datos: bytes) -> str:
    return base64.b64encode(datos).decode()


def hash_clave(clave: str) -> str:
    """Devuelve el hash de la contraseña con una sal aleatoria propia."""
    sal = secrets.token_bytes(16)
    derivada = hashlib.scrypt(clave.encode(), salt=sal, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${_b64(sal)}${_b64(derivada)}"


def verificar_clave(clave: str, guardado: str) -> bool:
    """Compara en tiempo constante la contraseña con el hash guardado."""
    try:
        _, n, r, p, sal, derivada = guardado.split("$")
        calculada = hashlib.scrypt(clave.encode(), salt=base64.b64decode(sal), n=int(n),
                                   r=int(r), p=int(p), dklen=32)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(calculada, base64.b64decode(derivada))


def nuevo_token() -> str:
    """Token opaco que recibe el navegador. En la base solo se guarda su huella."""
    return secrets.token_urlsafe(32)


def huella(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
