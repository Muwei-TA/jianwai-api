from fastapi import APIRouter,Request,Query
from sqlalchemy import select,update
from .common import *
from .models import Invitation
router=APIRouter(prefix='/clubs')
@router.get('')
def clubs(request:Request,limit:int=Query(20,ge=1,le=50),offset:int=Query(0,ge=0),db=DB):
    u=user(request,db)
    return paginate([club_data(db,c,u) for c in db.scalars(select(Club).where(Club.active==True).order_by(Club.name))],limit,offset)
@router.get('/{cid}')
def club(cid:str,request:Request,db=DB):
    c=db.get(Club,cid)
    if not c or not c.active:missing()
    return club_data(db,c,user(request,db))

def revoke(db,cid,uid):db.execute(update(Invitation).where(Invitation.club_id==cid,Invitation.creator_id==uid,Invitation.used_by==None).values(revoked=True))
@router.delete('/{cid}/membership')
def leave(cid:str,request:Request,db=DB):
    u=user(request,db,True);lock_club(db,cid);m=membership(db,cid,u.id)
    if not m:missing()
    if m.role=='owner':error(409,'INVALID_STATE','团主须转移社团后退出')
    revoke(db,cid,u.id);db.delete(m);return {'ok':True}
@router.patch('/{cid}/members/{uid}/invite-permission')
def permission(cid:str,uid:str,data:dict,request:Request,db=DB):
    u=user(request,db,True);lock_club(db,cid);m=membership(db,cid,u.id)
    if not m or m.role!='owner':missing()
    exact(data,('can_invite',),('can_invite',))
    if type(data['can_invite']) is not bool:invalid()
    target=membership(db,cid,uid)
    if not target:missing()
    if target.role=='owner' and not data['can_invite']:error(409,'INVALID_STATE','团主始终具有邀请权限')
    target.can_invite=data['can_invite']
    if not target.can_invite:revoke(db,cid,uid)
    return {'ok':True}

@router.get('/{cid}/members')
def members(cid:str,request:Request,limit:int=Query(20,ge=1,le=50),offset:int=Query(0,ge=0),db=DB):
    u=user(request,db,True);m=membership(db,cid,u.id)
    if not m or m.role!='owner':missing()
    items=[]
    for row in db.scalars(select(Membership).where(Membership.club_id==cid).order_by(Membership.joined_at)):
        member=db.get(User,row.user_id)
        items.append(dict(user_id=row.user_id,display_name=member.display_name,role=row.role,can_invite=row.can_invite or row.role=='owner',joined_at=iso(row.joined_at)))
    return paginate(items,limit,offset)
