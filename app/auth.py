import json,secrets
import httpx
from datetime import timedelta
from fastapi import APIRouter,Request,Response
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from sqlalchemy import select,update
from .common import *
from .models import Verification
router=APIRouter(prefix='/auth'); passwords=PasswordHasher()

def password(value,minimum=10):
    if not isinstance(value,str) or not minimum<=len(value)<=128:invalid('密码长度无效')
    return value

def user_data(u):return {k:getattr(u,k) for k in ('id','email','display_name','email_verified','is_member')}
def rotate(request,response,db,u=None):
    old=current_session(request,db)
    if old:db.delete(old)
    token=secrets.token_urlsafe(32)
    s=Session(id=digest(token),user_id=u.id if u else None,csrf_token=secrets.token_urlsafe(32),expires_at=now()+timedelta(days=30))
    db.add(s);db.flush()
    response.set_cookie('jw_session',token,httponly=True,secure=request.app.state.settings.cookie_secure,samesite='lax',max_age=30*86400,path='/')
    return {'user':user_data(u) if u else None,'csrf_token':s.csrf_token}

def send_verification(request,db,u):
    # Invalidate preceding verification links before issuing a new one.
    db.execute(update(Verification).where(Verification.user_id==u.id,Verification.used==False).values(used=True).execution_options(synchronize_session="fetch"))
    token=secrets.token_urlsafe(32)
    db.add(Verification(id=digest(token),user_id=u.id,expires_at=now()+timedelta(hours=24)))
    settings=request.app.state.settings
    url=settings.public_web_url.rstrip('/')+'/verify?token='+token
    if settings.resend_api_key:
        try:
            result=httpx.post('https://api.resend.com/emails',headers={'Authorization':'Bearer '+settings.resend_api_key},json={'from':settings.resend_from,'to':[u.email],'subject':'验证你的间外邮箱','text':'请在24小时内验证邮箱：'+url},timeout=15)
            result.raise_for_status()
            payload=result.json()
            if not isinstance(payload,dict) or not payload.get('id'):raise ValueError('missing email id')
        except (httpx.HTTPError,ValueError):error(503,'MAIL_UNAVAILABLE','邮件暂时无法发送，请稍后重试')
    else:
        settings.outbox_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
        path=settings.outbox_dir/(secrets.token_hex(16)+'.json')
        path.write_text(json.dumps({'to':u.email,'url':url,'token':token},ensure_ascii=False));path.chmod(0o600)

@router.get('/session')
def session(request:Request,response:Response,db=DB):
    s=current_session(request,db);u=user(request,db)
    if not s:return rotate(request,response,db)
    return {'user':user_data(u) if u else None,'csrf_token':s.csrf_token}
@router.post('/register',status_code=201)
def register(data:dict,request:Request,response:Response,db=DB):
    exact(data,('email','password','display_name'),('email','password','display_name'))
    addr=email(data['email']);pwd=password(data['password'],10);name=text(data['display_name'],2,30)
    if db.scalar(select(User).where(User.email==addr)):error(409,'REGISTRATION_UNAVAILABLE','暂时无法创建账号，请尝试登录或稍后重试')
    u=User(email=addr,display_name=name,password_hash=passwords.hash(pwd));db.add(u);db.flush();send_verification(request,db,u)
    return rotate(request,response,db,u)
@router.post('/login')
def login(data:dict,request:Request,response:Response,db=DB):
    exact(data,('email','password'),('email','password'))
    addr=email(data['email']);pwd=password(data['password'],1)
    u=db.scalar(select(User).where(User.email==addr))
    try:
        # Equal-cost dummy verification reduces account-enumeration timing differences.
        passwords.verify(u.password_hash if u else request.app.state.dummy_password_hash,pwd)
    except VerificationError:error(401,'AUTH_REQUIRED','邮箱或密码不正确')
    if not u:error(401,'AUTH_REQUIRED','邮箱或密码不正确')
    return rotate(request,response,db,u)
@router.post('/logout')
def logout(request:Request,response:Response,db=DB):
    rotate(request,response,db);return {'ok':True}
@router.post('/verify-email')
def verify(data:dict,request:Request,db=DB):
    exact(data,('token',),('token',));token=text(data['token'],1,200)
    v=db.get(Verification,digest(token))
    if not v or v.used or utc(v.expires_at)<=now():invalid('验证链接已失效')
    result=db.execute(update(Verification).where(Verification.id==v.id,Verification.used==False,Verification.expires_at>now()).values(used=True).execution_options(synchronize_session="fetch"))
    if result.rowcount!=1:invalid('验证链接已失效')
    db.get(User,v.user_id).email_verified=True
    return {'ok':True}
@router.post('/resend-verification')
def resend(request:Request,db=DB):
    u=user(request,db,True)
    if not u.email_verified:send_verification(request,db,u)
    return {'ok':True}
