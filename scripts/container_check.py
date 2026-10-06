"""Optional Docker integration test. Creates/removes its own container and test volume."""
import http.client
import json
import secrets
import subprocess
import tempfile
import time
import uuid
from pathlib import Path


def main():
    prefix='klimanwaves-check-'+uuid.uuid4().hex[:10]
    volume=prefix+'-data'
    def docker(*args):
        return subprocess.run(['docker','--config','/tmp/klimanwaves-docker-config',*args],
                              check=True,capture_output=True,text=True).stdout.strip()
    def call(path,port,data=None,cookie=None,origin=None):
        connection=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
        headers={}
        if data is not None:headers['Content-Type']='application/json'
        if cookie:headers['Cookie']=cookie
        if origin:headers['Origin']=origin
        connection.request('POST' if data is not None else 'GET',path,
                           json.dumps(data) if data is not None else None,headers)
        response=connection.getresponse()
        result=(response.status,dict(response.getheaders()),json.loads(response.read()))
        connection.close()
        return result
    def ready(port,cookie=None):
        for _ in range(50):
            try:
                result=call('/api/state' if cookie else '/api/health',port,cookie=cookie)
                if result[0]==200:return result
            except (OSError,ValueError):pass
            time.sleep(.2)
        raise RuntimeError('Container readiness failed')
    with tempfile.TemporaryDirectory() as directory:
        secret=secrets.token_urlsafe(48)
        file=Path(directory)/'test.env'
        file.write_text('APP_PUBLIC_ORIGIN=https://pilot.example.com\nAPP_ADMIN_TOKEN='+secret+'\n')
        file.chmod(0o600)
        try:
            docker('volume','create',volume)
            docker('run','--detach','--name',prefix,'--env-file',str(file),'--mount',
                   'type=volume,source='+volume+',target=/data','--publish','127.0.0.1::8000','klimanwaves-pilot:local')
            port=int(docker('port',prefix,'8000/tcp').rsplit(':',1)[1])
            ready(port)
            assert call('/api/state',port)[0]==401, 'Unauthenticated state not protected'
            status,headers,_=call('/api/login',port,dict(token=secret),origin='https://pilot.example.com')
            assert status==200,'Login failed'
            cookie=headers['Set-Cookie']
            assert all(x in cookie for x in ['Secure','HttpOnly','SameSite=Strict']),'Cookie flags missing'
            product=dict(name='TEST ONLY — container persistence',url='https://example.com/product',
                         source='TEST fixture; never customer data',facts='TEST',
                         economics=dict(sale_price=100,purchase_cost=20,vat_rate=0))
            assert call('/api/products',port,product,cookie=cookie,origin='https://pilot.example.com')[0]==200,'Product write failed'
            assert call('/api/analyze',port,{},cookie=cookie,origin='https://evil.example')[0]==403,'Cross-origin request accepted'
            # docker exec runs as the image default user; inspect the actual server PID instead.
            uid=docker('exec',prefix,'python','-c',
                       "from pathlib import Path;print(next(x for x in Path('/proc/1/status').read_text().splitlines() if x.startswith('Uid:')).split()[1])")
            assert uid=='10001','Server process must run as non-root'
            docker('restart',prefix)
            # An automatically assigned Docker host port can change after restart.
            port=int(docker('port',prefix,'8000/tcp').rsplit(':',1)[1])
            result=ready(port,cookie=cookie)
            assert len(result[2]['products'])==1,'Persistent database was lost on restart'
            print('PASS: container HTTP health/login, authorization, Secure cookie, foreign-origin rejection, non-root server UID, database and session persistence after restart.')
        finally:
            subprocess.run(['docker','rm','--force',prefix],capture_output=True)
            subprocess.run(['docker','volume','rm',volume],capture_output=True)


if __name__=='__main__':main()
