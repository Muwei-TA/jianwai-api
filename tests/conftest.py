import json
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def env(tmp_path):
    try:
        from app.main import create_app
        from app.config import Settings
    except ImportError:
        pytest.fail('真实社区 API create_app 尚未实现')
    database_url=os.getenv('TEST_DATABASE_URL') or f'sqlite:///{tmp_path}/db.sqlite'
    if not database_url.startswith('sqlite') and not database_url.split('?',1)[0].endswith('/jianwai_test'):
        pytest.fail('TEST_DATABASE_URL 只能指向专用 jianwai_test 数据库')
    settings = Settings(app_env='test',cookie_secure=False,database_url=database_url, media_dir=tmp_path/'media', outbox_dir=tmp_path/'outbox', allowed_origins=['http://testserver'])
    app = create_app(settings)
    from app.db import Base
    if not database_url.startswith('sqlite'): Base.metadata.drop_all(app.state.engine)
    Base.metadata.create_all(app.state.engine)
    try:
        yield app, settings
    finally:
        app.state.engine.dispose()

class Actor:
    def __init__(self, app):
        self.client = TestClient(app)
        self.csrf = self.client.get('/api/v1/auth/session').json()['csrf_token']
    def req(self, method, path, **kwargs):
        headers = kwargs.pop('headers', {})
        headers.update({'Origin':'http://testserver','X-CSRF-Token':self.csrf})
        result = self.client.request(method, '/api/v1'+path, headers=headers, **kwargs)
        if result.status_code < 300 and 'application/json' in result.headers.get('content-type','') and 'csrf_token' in result.json():
            self.csrf=result.json()['csrf_token']
        return result
    def get(self,path,**kwargs): return self.req('GET',path,**kwargs)
    def post(self,path,**kwargs): return self.req('POST',path,**kwargs)
    def put(self,path,**kwargs): return self.req('PUT',path,**kwargs)
    def delete(self,path,**kwargs): return self.req('DELETE',path,**kwargs)
    def patch(self,path,**kwargs): return self.req('PATCH',path,**kwargs)

def register(env,email,verified=True):
    app,settings=env
    a=Actor(app)
    r=a.post('/auth/register',json={'email':email,'password':'Strong secret 123!','display_name':'用户'+email.split('@')[0]})
    assert r.status_code==201, r.text
    a.id=r.json()['user']['id']
    if verified:
        msg=next(json.loads(p.read_text()) for p in settings.outbox_dir.glob('*.json') if json.loads(p.read_text())['to']==email)
        assert a.post('/auth/verify-email',json={'token':msg['token']}).status_code==200
    return a

@pytest.fixture
def community(env):
    owner=register(env,'owner@example.com')
    from app.models import Club,Membership
    with env[0].state.session_factory.begin() as db:
        club=Club(slug='books',name='读书团',description='读书聊天')
        db.add(club); db.flush()
        db.add(Membership(club_id=club.id,user_id=owner.id,role='owner',can_invite=True))
        cid=club.id
    return owner,cid

def join(env,owner,cid,email):
    a=register(env,email)
    code=owner.post(f'/clubs/{cid}/invites',json={}).json()['code']
    assert a.post('/invites/redeem',json={'code':code}).status_code==200
    return a
