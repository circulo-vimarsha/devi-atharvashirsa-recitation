#!/usr/bin/env python3
"""Lock the page's content with a password, so the public repository holds it only encrypted.

    python3 tools/seal.py <password>

Reads private/text.json, private/timing.json and private/recitation.mp3 (never committed) and writes
sealed/lock.json, sealed/data.bin (text + timing) and sealed/audio.bin. Each .bin is a 12-byte IV
followed by AES-256-GCM ciphertext; the key is PBKDF2-SHA256 of the password with the salt and
iteration count in lock.json. The page derives the same key with WebCrypto and decrypts in the browser.

A short password stops casual visitors and search engines, not a determined guesser."""
import json, os, sys
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ROOT = Path(__file__).resolve().parent.parent
ITER = 250_000


def main():
    password = sys.argv[1].encode()
    salt = os.urandom(16)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITER).derive(password)
    aes = AESGCM(key)
    priv, out = ROOT / 'private', ROOT / 'sealed'
    out.mkdir(exist_ok=True)
    timing = json.loads((priv / 'timing.json').read_text())
    timing.pop('audio', None)
    data = json.dumps({'text': json.loads((priv / 'text.json').read_text()), 'timing': timing},
                      ensure_ascii=False, separators=(',', ':')).encode()
    for name, plain in (('data.bin', data), ('audio.bin', (priv / 'recitation.mp3').read_bytes())):
        iv = os.urandom(12)
        (out / name).write_bytes(iv + aes.encrypt(iv, plain, None))
    (out / 'lock.json').write_text(json.dumps({'kdf': 'PBKDF2-SHA256', 'iterations': ITER, 'salt': salt.hex(),
                                               'cipher': 'AES-256-GCM', 'audio': 'audio/mpeg'}) + '\n')
    print('sealed:', ', '.join(f'{p.name} {p.stat().st_size // 1024} KB' for p in sorted(out.iterdir())))


if __name__ == '__main__':
    main()
