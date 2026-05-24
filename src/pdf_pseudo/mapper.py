from __future__ import annotations

import base64
import json
import re

from cryptography.fernet import Fernet

_TOKEN_RE = re.compile(r"<<[A-Z_]+_\d+>>")


class TokenMapper:
    """Mapeador bidireccional de tokens para pseudonimización reversible.

    Mantiene un diccionario interno que asocia texto original con tokens
    de la forma ``<<TIPO_N>>``. Genera una clave Fernet para cifrar y
    descifrar el mapeo al exportarlo/importarlo.
    """

    def __init__(self):
        """Crea un nuevo mapeador. Genera una clave Fernet automáticamente."""
        self._forward: dict[tuple[str, str], str] = {}
        self._reverse: dict[str, str] = {}
        self._counters: dict[str, int] = {}
        self._fernet_key: bytes = Fernet.generate_key()

    def pseudonymize(self, original_text: str, entity_type: str) -> str:
        """Dado un texto original y su tipo de entidad, devuelve un token consistente.

        Ejemplo: ``pseudonymize("Juan Pérez", "PERSON")`` devuelve ``"<<PERSON_1>>"``.
        Si se llama otra vez con los mismos argumentos, devuelve el mismo token.
        Si se llama con otro nombre, devuelve ``"<<PERSON_2>>"``, etc.

        Args:
            original_text: Texto original del dato sensible.
            entity_type: Tipo de entidad (ej. ``"PERSON"``, ``"DNI"``).

        Returns:
            Token generado con el formato ``<<TIPO_N>>``.
        """
        key = (original_text, entity_type.upper())
        if key in self._forward:
            return self._forward[key]

        etype = entity_type.upper()
        count = self._counters.get(etype, 0) + 1
        self._counters[etype] = count
        token = f"<<{etype}_{count}>>"
        self._forward[key] = token
        self._reverse[token] = original_text
        return token

    def depseudonymize(self, text_with_tokens: str) -> str:
        """Recibe un texto con tokens y restaura los valores originales.

        Busca todos los tokens con formato ``<<TIPO_N>>`` y los reemplaza
        por el valor original almacenado. Los tokens que no estén registrados
        en el mapeo se dejan intactos.

        Args:
            text_with_tokens: Texto que contiene tokens del tipo ``<<PERSON_1>>``.

        Returns:
            Texto con los tokens reemplazados por sus valores originales.
        """
        def _replacer(match: re.Match) -> str:
            token = match.group(0)
            return self._reverse.get(token, token)

        return _TOKEN_RE.sub(_replacer, text_with_tokens)

    def to_encrypted_bytes(self) -> bytes:
        """Serializa el mapa de sustituciones y la clave Fernet a bytes cifrados.

        Formato del archivo resultante:

        - Primera línea: clave Fernet codificada en base64 URL-safe.
        - Segunda línea: JSON del mapa ``_forward`` cifrado con Fernet y
          codificado en base64 URL-safe.

        Returns:
            Bytes listos para escribir en un archivo ``.key``.
        """
        fernet = Fernet(self._fernet_key)

        entries: list[list[str]] = [
            [orig, etype, token]
            for (orig, etype), token in self._forward.items()
        ]
        json_bytes = json.dumps(entries, ensure_ascii=False).encode("utf-8")
        encrypted = fernet.encrypt(json_bytes)

        key_b64 = base64.urlsafe_b64encode(self._fernet_key)
        encrypted_b64 = base64.urlsafe_b64encode(encrypted)
        return key_b64 + b"\n" + encrypted_b64

    @staticmethod
    def from_encrypted_bytes(data: bytes) -> "TokenMapper":
        """Reconstruye un ``TokenMapper`` a partir de los bytes de un archivo ``.key``.

        Extrae la clave Fernet, descifra el JSON interno y reconstruye
        los diccionarios ``_forward``, ``_reverse`` y ``_counters``.

        Args:
            data: Bytes tal cual los produce ``to_encrypted_bytes()``.

        Returns:
            Una instancia de ``TokenMapper`` con el mapeo original restaurado.

        Raises:
            ValueError: Si el formato de los bytes no es válido.
        """
        mapper = TokenMapper()
        parts = data.split(b"\n", 1)
        if len(parts) != 2:
            raise ValueError("Formato de archivo .key inválido: falta el separador de línea")

        key_b64 = parts[0]
        encrypted_b64 = parts[1]

        mapper._fernet_key = base64.urlsafe_b64decode(key_b64)
        fernet = Fernet(mapper._fernet_key)
        encrypted = base64.urlsafe_b64decode(encrypted_b64)
        json_bytes = fernet.decrypt(encrypted)
        entries: list[list[str]] = json.loads(json_bytes.decode("utf-8"))

        for orig, etype, token in entries:
            mapper._forward[(orig, etype)] = token
            mapper._reverse[token] = orig

        for token in mapper._reverse:
            m = re.match(r"<<([A-Z_]+)_(\d+)>>", token)
            if m:
                etype = m.group(1)
                n = int(m.group(2))
                if n > mapper._counters.get(etype, 0):
                    mapper._counters[etype] = n

        return mapper
