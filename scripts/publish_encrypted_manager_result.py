#!/usr/bin/env python3
"""Publish an encrypted, request-scoped result; never publish manager input."""
import base64, json, os, re, urllib.request
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def encode(value):
    return base64.b64encode(value).decode("ascii")

def seal(plan, jwk):
    if jwk.get("kty") != "RSA" or jwk.get("alg") not in (None, "RSA-OAEP-256"):
        raise ValueError("Expected RSA-OAEP-256 public key")
    def integer(value):
        return int.from_bytes(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)), "big")
    public = rsa.RSAPublicNumbers(integer(jwk["e"]), integer(jwk["n"])).public_key()
    if public.key_size < 2048 or public.key_size > 4096:
        raise ValueError("Invalid RSA size")
    key, nonce = AESGCM.generate_key(bit_length=256), os.urandom(12)
    encrypted = AESGCM(key).encrypt(nonce, json.dumps(plan, separators=(",", ":")).encode(), b"fpl-manager-result-v1")
    wrapped = public.encrypt(key, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    return dict(version=1, algorithm="RSA-OAEP-256+A256GCM", key=encode(wrapped), nonce=encode(nonce), ciphertext=encode(encrypted))

def main():
    request_id = os.environ["MANAGER_REQUEST_ID"]
    if not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", request_id):
        raise ValueError("Invalid request ID")
    envelope = seal(json.loads(Path("work/manager-plan.json").read_text()), json.loads(os.environ["MANAGER_PUBLIC_KEY"]))
    repo = os.environ["GITHUB_REPOSITORY"]
    if repo != "pdamkier-del/fpl-analytics-app":
        raise ValueError("Unexpected repository")
    body = dict(message="Publish encrypted manager result " + request_id, branch="free-github-static-20261010", content=encode((json.dumps(envelope) + "\n").encode()))
    request = urllib.request.Request("https://api.github.com/repos/" + repo + "/contents/app/manager-results/" + request_id + ".json", data=json.dumps(body).encode(), method="PUT", headers={"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"], "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2026-03-10", "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        if response.status != 201:
            raise ValueError("Result creation failed")
    print("Encrypted manager result published; no plaintext state committed")
if __name__ == "__main__":
    main()
