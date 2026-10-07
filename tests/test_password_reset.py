import json
from datetime import timedelta
from sqlalchemy import select
from conftest import Actor,register

def reset_mail(settings):
    return next(json.loads(p.read_text()) for p in settings.outbox_dir.glob('*.json') if '/reset-password?token=' in json.loads(p.read_text())['url'])

def test_password_reset_is_email_scoped_single_use_and_revokes_sessions(env):
    app,settings=env
    account=register(env,'reset@example.com')
    other=Actor(app)
    assert other.post('/auth/login',json={'email':'reset@example.com','password':'Strong secret 123!'}).status_code==200
    anonymous=Actor(app)
    unknown=anonymous.post('/auth/forgot-password',json={'email':'missing@example.com'})
    known=anonymous.post('/auth/forgot-password',json={'email':'RESET@example.com'})
    assert unknown.status_code==known.status_code==200
    assert unknown.json()==known.json()=={'ok':True}
    mail=reset_mail(settings)
    assert mail['to']=='reset@example.com'
    assert mail['url'].startswith(settings.public_web_url+'/reset-password?token=')
    assert all(p.stat().st_mode & 0o077==0 for p in settings.outbox_dir.glob('*.json'))
    count=len(list(settings.outbox_dir.glob('*.json')))
    assert anonymous.post('/auth/forgot-password',json={'email':'reset@example.com'}).json()=={'ok':True}
    assert len(list(settings.outbox_dir.glob('*.json')))==count
    assert anonymous.post('/auth/verify-email',json={'token':mail['token']}).status_code==422
    assert anonymous.post('/auth/reset-password',json={'token':mail['token'],'new_password':'short'}).status_code==422
    assert anonymous.post('/auth/reset-password',json={'token':mail['token'],'new_password':'A different strong secret 456!'}).status_code==200
    assert account.get('/auth/session').json()['user'] is None
    assert other.get('/auth/session').json()['user'] is None
    assert anonymous.post('/auth/reset-password',json={'token':mail['token'],'new_password':'Another strong secret 789!'}).status_code==422
    assert anonymous.post('/auth/login',json={'email':'reset@example.com','password':'Strong secret 123!'}).status_code==401
    assert anonymous.post('/auth/login',json={'email':'reset@example.com','password':'A different strong secret 456!'}).status_code==200

def test_reset_token_expires_and_is_not_accepted_as_email_verification(env):
    app,settings=env
    register(env,'unverified@example.com',False)
    anonymous=Actor(app)
    verification=next(json.loads(p.read_text())['token'] for p in settings.outbox_dir.glob('*.json'))
    assert anonymous.post('/auth/reset-password',json={'token':verification,'new_password':'A different strong secret 456!'}).status_code==422
    assert anonymous.post('/auth/forgot-password',json={'email':'unverified@example.com'}).status_code==200
    token=reset_mail(settings)['token']
    from app.models import PasswordReset,now
    with app.state.session_factory.begin() as db:
        row=db.scalar(select(PasswordReset))
        row.expires_at=now()-timedelta(seconds=1)
    assert anonymous.post('/auth/reset-password',json={'token':token,'new_password':'A different strong secret 456!'}).status_code==422
    assert anonymous.post('/auth/verify-email',json={'token':token}).status_code==422

def test_reset_request_stays_generic_when_mail_provider_fails(env,monkeypatch):
    import httpx
    from app import auth
    register(env,'delivery@example.com')
    settings=env[1]
    settings.resend_api_key='test-key';settings.resend_from='sender@example.com'
    calls=[]
    def reject(url,**kwargs):
        calls.append(kwargs['json']['to'])
        return httpx.Response(403,json={'message':'denied'},request=httpx.Request('POST',url))
    monkeypatch.setattr(auth.httpx,'post',reject)
    actor=Actor(env[0])
    unknown=actor.post('/auth/forgot-password',json={'email':'missing@example.com'})
    known=actor.post('/auth/forgot-password',json={'email':'delivery@example.com'})
    assert unknown.status_code==known.status_code==200
    assert unknown.json()==known.json()=={'ok':True}
    assert calls==[['delivery@example.com']]
