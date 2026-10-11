import importlib.util,json,subprocess
from pathlib import Path
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa,padding
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import base64
path=Path(__file__).resolve().parents[1]/'scripts/publish_encrypted_manager_result.py'
spec=importlib.util.spec_from_file_location('encrypted_result',path)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def jwk(key):
    p=key.public_key().public_numbers()
    def b64(n):return base64.urlsafe_b64encode(n.to_bytes((n.bit_length()+7)//8,'big')).decode().rstrip('=')
    return dict(kty='RSA',alg='RSA-OAEP-256',n=b64(p.n),e=b64(p.e))
def test_only_requesting_browser_can_decrypt_exact_plan():
    private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    plan=dict(manager_state_sha256='abc',locked_model_active=False,player='Ødegaard',bank=7)
    envelope=m.seal(plan,jwk(private))
    key=private.decrypt(base64.b64decode(envelope['key']),padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
    raw=AESGCM(key).decrypt(base64.b64decode(envelope['nonce']),base64.b64decode(envelope['ciphertext']),b'fpl-manager-result-v1')
    assert json.loads(raw)==plan
    assert 'Ødegaard' not in json.dumps(envelope)
    with pytest.raises(Exception):AESGCM(key).decrypt(base64.b64decode(envelope['nonce']),base64.b64decode(envelope['ciphertext']),b'changed')
def test_reject_small_or_wrong_public_keys():
    with pytest.raises(ValueError,match='RSA'):m.seal({},dict(kty='EC'))
    with pytest.raises(ValueError,match='size'):m.seal({},jwk(rsa.generate_private_key(public_exponent=65537,key_size=1024)))

def test_browser_webcrypto_opens_python_result():
    private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    plan=dict(manager_state_sha256='cutoff-bound-state',locked_model_active=False,player='Ødegaard')
    envelope=m.seal(plan,jwk(private))
    key=private.private_bytes(serialization.Encoding.DER,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
    result=subprocess.run(['node',str(path.parents[1]/'tests/test_manager_webcrypto.cjs')],input=json.dumps(dict(envelope=envelope,private_key=base64.b64encode(key).decode())),text=True,capture_output=True,check=True)
    assert json.loads(result.stdout)==plan

def test_online_publication_retains_ciphertext_only(tmp_path,monkeypatch,capsys):
    private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    plan={'manager_state_source':'PRIVATE_SOURCE_SENTINEL','bank_tenths':7}
    monkeypatch.chdir(tmp_path)
    (tmp_path/'work').mkdir()
    (tmp_path/'work/manager-plan.json').write_text(json.dumps(plan))
    for k,v in {'MANAGER_REQUEST_ID':'00000000-0000-4000-8000-000000000000',
                'MANAGER_PUBLIC_KEY':json.dumps(jwk(private)),
                'GITHUB_REPOSITORY':'pdamkier-del/fpl-analytics-app',
                'GITHUB_TOKEN':'TEST_ONLY'}.items():monkeypatch.setenv(k,v)
    requests=[]
    class Response:
        status=201
        def __enter__(self):return self
        def __exit__(self,*args):return False
    def send(request,timeout):
        requests.append(json.loads(request.data))
        return Response()
    monkeypatch.setattr(m.urllib.request,'urlopen',send)
    m.main()
    stored=json.loads((tmp_path/'work/encrypted-manager-plan.json').read_text())
    published=json.loads(base64.b64decode(requests[0]['content']))
    assert stored==published
    assert 'PRIVATE_SOURCE_SENTINEL' not in json.dumps(stored)
    assert 'PRIVATE_SOURCE_SENTINEL' not in capsys.readouterr().out
    key=private.decrypt(base64.b64decode(stored['key']),padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
    assert json.loads(AESGCM(key).decrypt(base64.b64decode(stored['nonce']),base64.b64decode(stored['ciphertext']),b'fpl-manager-result-v1'))==plan
