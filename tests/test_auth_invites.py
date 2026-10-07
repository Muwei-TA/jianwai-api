from concurrent.futures import ThreadPoolExecutor
import httpx
from sqlalchemy import select
from conftest import Actor, register, join

def test_resend_registration_success_and_failure_rolls_back(env,monkeypatch):
    from app import auth
    from app.models import User
    app,settings=env
    settings.resend_api_key='test-key';settings.resend_from='heijz@muwei.xyz'
    calls=[]
    def send(url,**kwargs):
        calls.append((url,kwargs))
        return httpx.Response(201 if len(calls)==1 else 403,json={'id':'mail-id'} if len(calls)==1 else {'message':'denied'},request=httpx.Request('POST',url))
    monkeypatch.setattr(auth.httpx,'post',send)
    actor=Actor(app)
    payload={'email':'user@example.com','password':'Strong secret 123!','display_name':'测试用户'}
    assert actor.post('/auth/register',json=payload).status_code==201
    assert calls[0][0]=='https://api.resend.com/emails'
    assert calls[0][1]['json']['from']=='heijz@muwei.xyz'
    assert calls[0][1]['json']['to']==['user@example.com']
    assert calls[0][1]['headers']['Authorization']=='Bearer test-key'
    assert not list(settings.outbox_dir.glob('*.json'))
    payload['email']='failed@example.com'
    assert Actor(app).post('/auth/register',json=payload).status_code==503
    with app.state.session_factory() as db:
        assert db.scalar(select(User).where(User.email=='failed@example.com')) is None

def test_sessions_password_csrf_and_verification(env):
    app,settings=env
    a=register(env,'user@example.com',False)
    assert a.client.post('/api/v1/auth/logout',json={}).status_code==403
    old=a.client.cookies.get('jw_session')
    assert a.post('/auth/logout',json={}).status_code==200
    a.csrf=a.get('/auth/session').json()['csrf_token']
    assert a.post('/auth/login',json={'email':'USER@example.com','password':'wrong'}).status_code==401
    assert a.post('/auth/login',json={'email':'USER@example.com','password':'Strong secret 123!'}).status_code==200
    assert a.client.cookies.get('jw_session')!=old
    assert a.get('/auth/session').json()['user']['email_verified'] is False
    assert a.post('/auth/verify-email',json={'token':'fake'}).status_code==422
    assert 'token' not in a.get('/auth/session').json()

def test_invitation_verified_bound_and_retry(env,community):
    owner,cid=community
    a=register(env,'a@example.com',False)
    code=owner.post(f'/clubs/{cid}/invites',json={'bound_email':'a@example.com'}).json()['code']
    assert a.post('/invites/redeem',json={'code':code}).status_code==403
    b=register(env,'b@example.com')
    assert b.post('/invites/redeem',json={'code':code}).status_code==409
    import json
    msg=next(json.loads(p.read_text()) for p in env[1].outbox_dir.glob('*.json') if json.loads(p.read_text())['to']=='a@example.com')
    assert a.post('/auth/verify-email',json={'token':msg['token']}).status_code==200
    assert a.post('/invites/redeem',json={'code':code}).json()['already_member'] is False
    assert a.post('/invites/redeem',json={'code':code}).json()['already_member'] is True
    assert a.delete(f'/clubs/{cid}/membership').status_code==200
    assert a.get('/auth/session').json()['user']['is_member'] is True
    assert a.post('/invites/redeem',json={'code':code}).status_code==409
    assert owner.delete(f'/clubs/{cid}/membership').status_code==409

def test_existing_member_does_not_consume_and_permission_revokes(env,community):
    owner,cid=community
    a=join(env,owner,cid,'a@example.com')
    code=owner.post(f'/clubs/{cid}/invites',json={}).json()['code']
    assert a.post('/invites/redeem',json={'code':code}).json()['already_member'] is True
    b=register(env,'b@example.com')
    assert b.post('/invites/redeem',json={'code':code}).status_code==200
    assert a.post(f'/clubs/{cid}/invites',json={}).status_code==403
    assert owner.patch(f'/clubs/{cid}/members/{a.id}/invite-permission',json={'can_invite':True}).status_code==200
    code=a.post(f'/clubs/{cid}/invites',json={}).json()['code']
    assert owner.patch(f'/clubs/{cid}/members/{a.id}/invite-permission',json={'can_invite':False}).status_code==200
    assert Actor(env[0]).post('/invites/preview',json={'code':code}).status_code==409

def test_one_code_two_concurrent_accounts(env,community):
    owner,cid=community
    actors=[register(env,f'concurrent{i}@example.com') for i in range(2)]
    code=owner.post(f'/clubs/{cid}/invites',json={}).json()['code']
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses=list(pool.map(lambda a:a.post('/invites/redeem',json={'code':code}).status_code,actors))
    assert sorted(statuses)==[200,409]

def test_password_whitespace_is_preserved(env):
    a=Actor(env[0]);password='  significant spaces  '
    assert a.post('/auth/register',json={'email':'space@example.com','password':password,'display_name':'空白密码'}).status_code==201
    assert a.post('/auth/login',json={'email':'space@example.com','password':password.strip()}).status_code==401
    assert a.post('/auth/login',json={'email':'space@example.com','password':password}).status_code==200
