"""Minimal client for the public JSON service behind https://www.lob.gov.jo/ .

The Legislation and Opinion Bureau portal is a single-page application. Its browser code
(Config.js, Controller/Master.js) talks to /OPSHandler/OPS.ashx. The server sends per-session
RSA keys in the X-Request-Key / X-Response-Key headers (wrapped with the passphrase that the
portal's own JavaScript uses), and responses are AES-encrypted with a key wrapped by RSA.
This module re-implements that documented client behaviour so the public legislation pages
can be read without a browser. It identifies itself as LawCodex and adds a delay between calls.
"""
import base64
import hashlib
import json
import os
import time
import uuid
from urllib.parse import unquote, urlencode

import requests
from cryptography.hazmat.primitives import padding as sympad, serialization
from cryptography.hazmat.primitives.asymmetric import padding as asympad
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

UA = "LawCodex/1.0 (+https://github.com/LawCodex)"
BASE = "https://www.lob.gov.jo"
SERVICE = "Customization/LobJo/LobJo.asmx"


def _evp(passphrase: bytes, salt: bytes, klen=32, ivlen=16):
    d, prev = b"", b""
    while len(d) < klen + ivlen:
        prev = hashlib.md5(prev + passphrase + salt).digest()
        d += prev
    return d[:klen], d[klen:klen + ivlen]


def cjs_decrypt(b64: str, passphrase: str) -> bytes:
    raw = base64.b64decode(b64)
    assert raw[:8] == b"Salted__"
    key, iv = _evp(passphrase.encode(), raw[8:16])
    dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    pt = dec.update(raw[16:]) + dec.finalize()
    unp = sympad.PKCS7(128).unpadder()
    return unp.update(pt) + unp.finalize()


def cjs_encrypt(data: bytes, passphrase: str) -> str:
    salt = os.urandom(8)
    key, iv = _evp(passphrase.encode(), salt)
    p = sympad.PKCS7(128).padder()
    data = p.update(data) + p.finalize()
    enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return base64.b64encode(b"Salted__" + salt + enc.update(data) + enc.finalize()).decode()


def _pem(s: str, kind: str) -> bytes:
    s = s.strip()
    if "BEGIN" in s:
        return s.encode()
    return f"-----BEGIN {kind}-----\n{s}\n-----END {kind}-----\n".encode()


class LobClient:
    def __init__(self, delay=1.0):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "X-Requested-With": "XMLHttpRequest",
                               "Accept": "application/json, text/javascript, */*; q=0.01"})
        self.delay = delay
        self.req_key = None
        self.resp_key = None
        self.access = None
        self.refresh = None
        self._last = 0.0

    def _wait(self):
        dt = time.time() - self._last
        if dt < self.delay:
            time.sleep(self.delay - dt)
        self._last = time.time()

    def _keys_from(self, r):
        for h, attr in (("X-Response-Key", "resp_key"), ("X-Request-Key", "req_key")):
            v = r.headers.get(h)
            if v:
                setattr(self, attr, cjs_decrypt(unquote(v), "UniversalOPS").decode())
        if r.headers.get("AccessToken"):
            self.access = r.headers["AccessToken"]
        if r.headers.get("RefreshToken"):
            self.refresh = r.headers["RefreshToken"]

    def _decode(self, text):
        obj = json.loads(text)
        if isinstance(obj, dict) and "enc" in obj and "_" in obj and self.resp_key:
            priv = serialization.load_pem_private_key(_pem(self.resp_key, "RSA PRIVATE KEY"), None)
            k = priv.decrypt(base64.b64decode(obj["_"]), asympad.PKCS1v15()).decode()
            obj = json.loads(cjs_decrypt(obj["enc"], k).decode("utf-8"))
        return obj

    def call(self, method, params=None, auth=False, tries=5):
        params = dict(params or {"id": -1})
        path = ("OPS_Auth.asmx" if auth else SERVICE) + "/" + method
        params["$$path"] = path
        for attempt in range(tries):
            if self.req_key is None and method != "GetPortalVersion":
                self.call("GetPortalVersion", {"id": -1}, auth=True)
            body = params
            if self.req_key and method != "GetPortalVersion":
                k = str(uuid.uuid4())
                pub = serialization.load_pem_public_key(_pem(self.req_key, "PUBLIC KEY"))
                body = {"enc": cjs_encrypt(urlencode(params).encode(), k),
                        "_": base64.b64encode(pub.encrypt(k.encode(), asympad.PKCS1v15())).decode()}
            hdr = {}
            if self.access:
                hdr["Authorization"] = "Bearer " + self.access
            if self.refresh:
                hdr["RefreshToken"] = self.refresh
            self._wait()
            try:
                r = self.s.post(BASE + "/OPSHandler/OPS.ashx", data=body, headers=hdr, timeout=90)
            except requests.RequestException as e:
                time.sleep(5 * (attempt + 1))
                continue
            self._keys_from(r)
            if r.status_code == 200:
                return self._decode(r.text)
            if r.status_code in (403, 429, 502, 503, 504):
                time.sleep(10 * (attempt + 1))
                continue
            raise RuntimeError(f"{method}: HTTP {r.status_code}: {r.text[:300]}")
        raise RuntimeError(f"{method}: failed after {tries} tries")
