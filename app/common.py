import re
from datetime import timezone
from fastapi import Request,Depends
from sqlalchemy import select,func
from .db import get_db as _get_db
from .models import User,Session,Membership,Club,now
import hashlib,hmac

def get_db(request:Request): yield from _get_db(request)
DB=Depends(get_db,scope="function")
class APIError(Exception):
    def __init__(self,status,code,message): self.status=status;self.code=code;self.message=message

def error(status,code,message): raise APIError(status,code,message)
def missing(): error(404,'NOT_FOUND','内容不存在或无权访问')
def invalid(message='输入格式无效'): error(422,'VALIDATION_ERROR',message)
def digest(token): return hashlib.sha256(token.encode()).hexdigest()
def utc(dt): return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
def iso(dt): return utc(dt).isoformat() if dt else None

def email(value):
    if not isinstance(value,str): invalid('邮箱格式无效')
    value=value.strip().lower()
    if len(value)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value): invalid('邮箱格式无效')
    return value

def exact(data,keys,required=()):
    if not isinstance(data,dict) or set(data)-set(keys) or set(required)-set(data): invalid()

def text(value,minimum=0,maximum=2000):
    if not isinstance(value,str) or (len(value.strip())<minimum or len(value)>maximum): invalid()
    return value.strip()

def current_session(request,db):
    token=request.cookies.get('jw_session','')
    row=db.get(Session,digest(token)) if token else None
    return row if row and utc(row.expires_at)>now() else None

def user(request,db,required=False,verified=False):
    session=current_session(request,db)
    u=db.get(User,session.user_id) if session and session.user_id else None
    if required and not u:error(401,'AUTH_REQUIRED','请先登录')
    if verified and u and not u.email_verified:error(403,'EMAIL_UNVERIFIED','请先验证邮箱')
    return u

def csrf(request:Request,db=DB):
    if request.method in {'GET','HEAD','OPTIONS'}:return
    s=current_session(request,db)
    if request.headers.get('origin') not in request.app.state.settings.allowed_origins or not s or not hmac.compare_digest(request.headers.get('x-csrf-token',''),s.csrf_token):error(403,'CSRF_FAILED','安全校验失败，请刷新页面')

def membership(db,cid,uid):return db.get(Membership,(cid,uid)) if uid else None

def lock_club(db,cid):
    club=db.scalar(select(Club).where(Club.id==cid).with_for_update())
    if not club or not club.active:missing()
    return club

def club_data(db,c,u):
    m=membership(db,c.id,u.id if u else None)
    return dict(id=c.id,slug=c.slug,name=c.name,description=c.description,accent=c.accent,member_count=db.scalar(select(func.count()).select_from(Membership).where(Membership.club_id==c.id)),my_role=m.role if m else None,can_invite=bool(m and (m.role=='owner' or m.can_invite)))

def paginate(items,limit,offset):return {'items':items[offset:offset+limit],'total':len(items)}
