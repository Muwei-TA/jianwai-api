import copy
from fastapi import APIRouter,Request,Query
from sqlalchemy import select,update,func
from .common import *
from .models import Draft,Post,PostAsset,Review,Comment
from .documents import own_draft,validate_document,FIELDS
from .policy import readable,can_read,published_query
router=APIRouter()

def post_data(db,p,u):
    author=db.get(User,p.author_id);club=db.get(Club,p.club_id)
    result={**p.document,'id':p.id,'author':{'id':author.id,'display_name':author.display_name},'club':{'id':club.id,'name':club.name,'slug':club.slug},'status':p.status,'created_at':iso(p.created_at),'published_at':iso(p.published_at),'comment_count':db.scalar(select(func.count()).select_from(Comment).where(Comment.post_id==p.id))}
    m=membership(db,club.id,u.id if u else None)
    if u and (u.id==p.author_id or m and m.role=='owner'):result['review_note']=p.review_note
    return result
@router.post('/drafts/{did}/publish',status_code=201)
def publish(did:str,data:dict,request:Request,db=DB):
    u=user(request,db,True,True);exact(data,('revision',),('revision',))
    rev=data['revision']
    if type(rev) is not int or rev<1:invalid()
    d=own_draft(db,did,u,True)
    cid=d.document.get('club_id')
    if not cid:invalid('发布前请选择社团')
    lock_club(db,cid)
    if not membership(db,cid,u.id):error(403,'CLUB_MEMBERSHIP_REQUIRED','请先加入社团')
    # Serialize publish with save/delete, and repeated publication using the same draft.
    db.refresh(d)
    existing=db.scalar(select(Post).where(Post.draft_id==did,Post.revision==rev))
    if existing:return post_data(db,readable(db,existing,u),u)
    if d.revision!=rev:error(409,'STALE_DRAFT','请先保存当前版本后发布')
    refs=validate_document(d.document,db,u,did,True)
    status='pending' if d.document['scope']=='public' else 'published'
    p=Post(draft_id=did,revision=rev,author_id=u.id,club_id=cid,document=copy.deepcopy(d.document),status=status,published_at=now() if status=='published' else None)
    db.add(p);db.flush()
    for aid in set(refs):db.add(PostAsset(post_id=p.id,asset_id=aid))
    db.flush();return post_data(db,p,u)
@router.get('/posts')
def listing(request:Request,club_id:str|None=None,scope:str|None=None,q:str|None=None,limit:int=Query(20,ge=1,le=50),offset:int=Query(0,ge=0),db=DB):
    u=user(request,db);query=published_query(db,u).order_by(Post.created_at.desc())
    if club_id:query=query.where(Post.club_id==club_id)
    if scope:
        if scope not in ('club','members','public'):invalid()
        query=query.where(Post.document['scope'].as_string()==scope)
    if q and len(q)>100:invalid()
    items=[]
    for p in db.scalars(query):
        if not q or q.casefold() in (p.document['title']+' '+p.document['summary']+' '+str(p.document['body'])).casefold():items.append(post_data(db,p,u))
    return paginate(items,limit,offset)
@router.get('/me/posts')
def own(request:Request,limit:int=Query(20,ge=1,le=50),offset:int=Query(0,ge=0),db=DB):
    u=user(request,db,True)
    return paginate([post_data(db,p,u) for p in db.scalars(select(Post).where(Post.author_id==u.id).order_by(Post.created_at.desc())) if can_read(db,p,u)],limit,offset)
@router.get('/reviews')
def reviews(request:Request,limit:int=Query(20,ge=1,le=50),offset:int=Query(0,ge=0),db=DB):
    u=user(request,db,True)
    clubs=select(Membership.club_id).where(Membership.user_id==u.id,Membership.role=='owner')
    return paginate([post_data(db,p,u) for p in db.scalars(select(Post).where(Post.club_id.in_(clubs),Post.status=='pending').order_by(Post.created_at)) if can_read(db,p,u)],limit,offset)
@router.get('/posts/{pid}')
def get(pid:str,request:Request,db=DB):
    u=user(request,db);return post_data(db,readable(db,db.get(Post,pid),u),u)
@router.post('/posts/{pid}/review')
def review(pid:str,data:dict,request:Request,db=DB):
    u=user(request,db,True,True);p=db.get(Post,pid)
    if not p:missing()
    lock_club(db,p.club_id);m=membership(db,p.club_id,u.id)
    if not m or m.role!='owner':missing()
    exact(data,('decision','note'),('decision',))
    if data['decision'] not in ('approve','request_changes'):invalid()
    note=text(data.get('note',''),0,2000)
    if data['decision']=='request_changes' and not note:invalid('请填写退回原因')
    status='published' if data['decision']=='approve' else 'changes_requested'
    result=db.execute(update(Post).where(Post.id==pid,Post.status=='pending').values(status=status,review_note=note,published_at=now() if status=='published' else None).execution_options(synchronize_session='fetch'))
    if result.rowcount!=1:error(409,'INVALID_STATE','稿件已被处理或撤回')
    db.add(Review(post_id=pid,reviewer_id=u.id,decision=data['decision'],note=note));db.flush();db.refresh(p)
    return post_data(db,p,u)
@router.post('/posts/{pid}/withdraw')
def withdraw(pid:str,request:Request,db=DB):
    u=user(request,db,True);p=db.get(Post,pid)
    if not p or p.author_id!=u.id:missing()
    # Club row also synchronizes with approval; withdrawal can never be approved back to life.
    db.scalar(select(Club).where(Club.id==p.club_id).with_for_update())
    db.execute(update(Post).where(Post.id==pid).values(status='withdrawn').execution_options(synchronize_session='fetch'))
    return {'id':pid,'status':'withdrawn'}

def comment_data(db,c):
    u=db.get(User,c.user_id)
    return dict(id=c.id,body=c.body,author={'id':u.id,'display_name':u.display_name},created_at=iso(c.created_at))
@router.get('/posts/{pid}/comments')
def comments(pid:str,request:Request,limit:int=Query(20,ge=1,le=50),offset:int=Query(0,ge=0),db=DB):
    readable(db,db.get(Post,pid),user(request,db))
    return paginate([comment_data(db,c) for c in db.scalars(select(Comment).where(Comment.post_id==pid).order_by(Comment.created_at))],limit,offset)
@router.post('/posts/{pid}/comments',status_code=201)
def comment(pid:str,data:dict,request:Request,db=DB):
    u=user(request,db);p=readable(db,db.get(Post,pid),u)
    if not u:error(401,'AUTH_REQUIRED','请先登录')
    if not u.email_verified:error(403,'EMAIL_UNVERIFIED','请先验证邮箱')
    if p.document['scope'] in ('public','members') and not u.is_member:error(403,'MEMBERSHIP_REQUIRED','仅社区成员可以回应')
    if p.status!='published':error(409,'INVALID_STATE','仅已发布内容可以回应')
    exact(data,('body',),('body',));body=text(data['body'],1,2000)
    c=Comment(post_id=pid,user_id=u.id,body=body);db.add(c);db.flush();return comment_data(db,c)
