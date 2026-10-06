import secrets
from datetime import timedelta
from fastapi import APIRouter,Request,Query
from sqlalchemy import select,update,func
from .common import *
from .models import Invitation
router=APIRouter()

def invitation_data(i):
    status='used' if i.used_by else 'revoked' if i.revoked else 'expired' if utc(i.expires_at)<=now() else 'active'
    return dict(id=i.id,club_id=i.club_id,expires_at=iso(i.expires_at),created_at=iso(i.created_at),bound_email=i.bound_email,status=status)
def allowed(db,cid,uid):
    m=membership(db,cid,uid)
    return bool(m and (m.role=='owner' or m.can_invite))
def require_permission(db,cid,u):
    if not allowed(db,cid,u.id):error(403,'INVITE_PERMISSION_REQUIRED','你没有邀请权限')
@router.post('/clubs/{cid}/invites',status_code=201)
def create(cid:str,data:dict,request:Request,db=DB):
    u=user(request,db,True,True);lock_club(db,cid);require_permission(db,cid,u)
    exact(data,('bound_email',));bound=email(data['bound_email']) if data.get('bound_email') else None
    count=db.scalar(select(func.count()).select_from(Invitation).where(Invitation.club_id==cid,Invitation.creator_id==u.id,Invitation.revoked==False,Invitation.used_by==None,Invitation.expires_at>now()))
    if count>=20:error(409,'INVITE_UNAVAILABLE','最多保留20个有效邀请码')
    code=secrets.token_urlsafe(32);i=Invitation(code_hash=digest(code),club_id=cid,creator_id=u.id,bound_email=bound,expires_at=now()+timedelta(days=7));db.add(i);db.flush()
    return {**invitation_data(i),'code':code}
@router.get('/clubs/{cid}/invites')
def listing(cid:str,request:Request,limit:int=Query(20,ge=1,le=50),offset:int=Query(0,ge=0),db=DB):
    u=user(request,db,True);require_permission(db,cid,u)
    query=select(Invitation).where(Invitation.club_id==cid).order_by(Invitation.created_at.desc())
    if membership(db,cid,u.id).role!='owner':query=query.where(Invitation.creator_id==u.id)
    return paginate([invitation_data(i) for i in db.scalars(query)],limit,offset)
@router.delete('/clubs/{cid}/invites/{iid}')
def delete(cid:str,iid:str,request:Request,db=DB):
    u=user(request,db,True);lock_club(db,cid);i=db.get(Invitation,iid);m=membership(db,cid,u.id)
    if not i or i.club_id!=cid or not m or (i.creator_id!=u.id and m.role!='owner'):missing()
    if i.used_by:error(409,'INVITE_UNAVAILABLE','邀请码已使用')
    i.revoked=True;return {'ok':True}
def lookup(data,db):
    exact(data,('code',),('code',));code=text(data['code'],1,200)
    i=db.scalar(select(Invitation).where(Invitation.code_hash==digest(code)))
    if not i:error(409,'INVITE_UNAVAILABLE','邀请码不可用')
    return i
def active(i,c,db):
    if not c.active or i.revoked or i.used_by or utc(i.expires_at)<=now() or not allowed(db,c.id,i.creator_id):error(409,'INVITE_UNAVAILABLE','邀请码不可用')
@router.post('/invites/preview')
def preview(data:dict,db=DB):
    i=lookup(data,db);c=db.get(Club,i.club_id);active(i,c,db)
    return dict(club={'id':c.id,'name':c.name,'description':c.description},expires_at=iso(i.expires_at),requires_email=bool(i.bound_email),status='active')
@router.post('/invites/redeem')
def redeem(data:dict,request:Request,db=DB):
    u=user(request,db,True,True);i=lookup(data,db);c=lock_club(db,i.club_id)
    # Refresh after acquiring the common club lock: all membership/invite mutations share it.
    db.refresh(i)
    m=membership(db,c.id,u.id)
    if i.used_by==u.id:
        if m:return {'club':club_data(db,c,u),'already_member':True}
        error(409,'ALREADY_REDEEMED','已兑换的邀请码不能再次加入')
    active(i,c,db)
    if i.bound_email and i.bound_email!=u.email:error(409,'INVITE_UNAVAILABLE','邀请码不可用')
    if m:return {'club':club_data(db,c,u),'already_member':True}
    result=db.execute(update(Invitation).where(Invitation.id==i.id,Invitation.used_by==None,Invitation.revoked==False,Invitation.expires_at>now()).values(used_by=u.id).execution_options(synchronize_session="fetch"))
    if result.rowcount!=1:error(409,'INVITE_UNAVAILABLE','邀请码不可用')
    db.add(Membership(club_id=c.id,user_id=u.id,role='member',can_invite=False));u.is_member=True;db.flush()
    return {'club':club_data(db,c,u),'already_member':False}
