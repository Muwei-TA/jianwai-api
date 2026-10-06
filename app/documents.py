import json
from urllib.parse import urlsplit
from fastapi import APIRouter,Request,Query
from sqlalchemy import select,update
from .common import *
from .models import Draft,Asset
router=APIRouter(prefix='/drafts')
FIELDS=('title','summary','body','club_id','scope','tags','feedback_intent','cover_asset_id')

def url(value):
    if not isinstance(value,str) or len(value)>2048 or any(ord(c)<33 for c in value):invalid('链接必须为 http 或 https')
    try:
        parts=urlsplit(value)
        if parts.scheme not in {'http','https'} or not parts.hostname or parts.username or parts.password:invalid('链接必须为 http 或 https')
        _=parts.port
    except ValueError:invalid('链接无效')

def rich_body(body):
    try:
        if len(json.dumps(body,ensure_ascii=False).encode())>150000:invalid('正文过大')
    except (TypeError,ValueError,RecursionError):invalid('正文格式无效')
    refs=[];texts=[];nodes=0
    blocks={'paragraph','heading','blockquote','bulletList','orderedList','horizontalRule','figure','gallery','linkCard'}
    children={'doc':blocks,'paragraph':{'text','hardBreak'},'heading':{'text','hardBreak'},'blockquote':blocks,'bulletList':{'listItem'},'orderedList':{'listItem'},'listItem':blocks}
    def asset_item(attrs):
        exact(attrs,('assetId','caption','alt'),('assetId',))
        asset=text(attrs['assetId'],32,32)
        if any(c not in '0123456789abcdef' for c in asset):invalid('图片标识无效')
        refs.append(asset)
        for k in ('caption','alt'):
            if k in attrs:text(attrs[k],0,500)
    def walk(n,depth,parent=None):
        nonlocal nodes
        nodes+=1
        if nodes>5000 or depth>20:invalid('正文结构过于复杂')
        exact(n,('type','attrs','content','text','marks'),('type',))
        kind=n['type']
        if not isinstance(kind,str) or kind not in children.keys()|{'text','hardBreak','horizontalRule','figure','gallery','linkCard'}:invalid('正文节点不支持')
        if parent and kind not in children.get(parent,set()):invalid('正文层级无效')
        if parent is None and kind!='doc':invalid('正文必须为 doc')
        attrs=n.get('attrs',{})
        if not isinstance(attrs,dict):invalid()
        if kind=='heading':
            exact(attrs,('level',),('level',))
            if type(attrs['level']) is not int or attrs['level'] not in (2,3):invalid()
        elif kind=='orderedList':
            exact(attrs,('start','type'))
            if 'start' in attrs and (type(attrs['start']) is not int or not 1<=attrs['start']<=10000):invalid()
            if attrs.get('type') not in (None,'1','a','A','i','I'):invalid()
        elif kind=='figure':
            exact(attrs,('assetId','caption','alt','layout','spoiler'),('assetId',))
            asset_item({k:v for k,v in attrs.items() if k in ('assetId','caption','alt')})
            if attrs.get('layout','normal') not in ('normal','wide') or type(attrs.get('spoiler',False)) is not bool:invalid()
        elif kind=='gallery':
            exact(attrs,('items','caption','layout'),('items',))
            if not isinstance(attrs['items'],list) or not 1<=len(attrs['items'])<=9:invalid()
            for item in attrs['items']:asset_item(item)
            text(attrs.get('caption',''),0,500)
            if attrs.get('layout','normal') not in ('normal','wide'):invalid()
        elif kind=='linkCard':
            exact(attrs,('url','title','description'),('url',));url(attrs['url']);text(attrs.get('title',''),0,160);text(attrs.get('description',''),0,500)
        elif attrs:invalid('正文属性不支持')
        if kind=='text':
            if 'content' in n or 'attrs' in n:invalid()
            if not isinstance(n.get('text'),str) or not n['text']:invalid()
            texts.append(n['text'])
        elif 'text' in n or ('marks' in n and kind!='hardBreak'):invalid()
        marks=n.get('marks',[])
        if not isinstance(marks,list) or len(marks)>8:invalid()
        for mark in marks:
            exact(mark,('type','attrs'),('type',))
            if mark['type'] not in ('bold','italic','underline','strike','code','link','spoiler'):invalid('正文标记不支持')
            ma=mark.get('attrs',{})
            if mark['type']=='link':
                exact(ma,('href','target','rel','class','title'),('href',));url(ma['href'])
                if ma.get('title') is not None:text(ma['title'],0,160)
                if ma.get('target') not in (None,'_blank','_self') or ma.get('class') is not None:invalid()
                if ma.get('rel') not in (None,'noopener noreferrer','noopener noreferrer nofollow'):invalid()
            elif ma:invalid()
        content=n.get('content',[])
        if not isinstance(content,list) or (kind not in children and content):invalid()
        if kind in ('bulletList','orderedList','listItem') and not content:invalid()
        for child in content:walk(child,depth+1,kind)
    walk(body,0)
    if sum(len(t) for t in texts)>20000:invalid('正文最多20000字')
    if len(refs)>9:invalid('正文最多9张图片')
    return refs,''.join(texts)

def validate_document(data,db,u,draft_id,publishing=False):
    exact(data,FIELDS,FIELDS)
    title=text(data['title'],2 if publishing else 0,80);text(data['summary'],0,160);text(data['feedback_intent'],0,160)
    if data['scope'] not in ('club','members','public'):invalid('可见范围无效')
    if not isinstance(data['tags'],list) or len(data['tags'])>5:invalid('标签最多5个')
    for tag in data['tags']:text(tag,1,20)
    cid=data['club_id']
    if cid is not None:
        if not isinstance(cid,str):invalid()
        c=db.get(Club,cid)
        if not c:invalid('社团不存在')
        if publishing and (not c.active or not membership(db,cid,u.id)):invalid('请选择你已加入的社团')
    elif publishing:invalid('发布前请选择社团')
    refs,plain=rich_body(data['body'])
    cover=data['cover_asset_id']
    if cover is not None:
        if not isinstance(cover,str):invalid()
        refs.append(cover)
    for aid in refs:
        a=db.get(Asset,aid)
        if not a or a.user_id!=u.id or a.draft_id!=draft_id:invalid('图片不属于当前草稿')
    if publishing and not plain.strip() and not refs:invalid('发布正文不能为空')
    return refs

def own_draft(db,did,u,locked=False):
    d=db.scalar(select(Draft).where(Draft.id==did).with_for_update()) if locked else db.get(Draft,did)
    if not d or not u or d.user_id!=u.id:missing()
    return d

def draft_data(d):return {**d.document,'id':d.id,'revision':d.revision,'updated_at':iso(d.updated_at)}
@router.post('',status_code=201)
def create(data:dict,request:Request,db=DB):
    u=user(request,db,True);exact(data,('club_id',))
    cid=data.get('club_id')
    if cid is not None and not isinstance(cid,str):invalid()
    if cid and not membership(db,cid,u.id):invalid('请选择你已加入的社团')
    d=Draft(user_id=u.id,document=dict(title='',summary='',body={'type':'doc','content':[{'type':'paragraph'}]},club_id=cid,scope='club',tags=[],feedback_intent='',cover_asset_id=None));db.add(d);db.flush();return draft_data(d)
@router.get('')
def listing(request:Request,limit:int=Query(20,ge=1,le=50),offset:int=Query(0,ge=0),db=DB):
    u=user(request,db,True)
    return paginate([draft_data(d) for d in db.scalars(select(Draft).where(Draft.user_id==u.id).order_by(Draft.updated_at.desc()))],limit,offset)
@router.get('/{did}')
def get(did:str,request:Request,db=DB):return draft_data(own_draft(db,did,user(request,db)))
@router.put('/{did}')
def save(did:str,data:dict,request:Request,db=DB):
    u=user(request,db,True);d=own_draft(db,did,u)
    exact(data,(*FIELDS,'revision'),(*FIELDS,'revision'))
    rev=data['revision']
    if type(rev) is not int or rev<1:invalid()
    doc={k:data[k] for k in FIELDS};validate_document(doc,db,u,did)
    changed=db.execute(update(Draft).where(Draft.id==did,Draft.user_id==u.id,Draft.revision==rev).values(document=doc,revision=rev+1,updated_at=now()).execution_options(synchronize_session='fetch'))
    if changed.rowcount!=1:error(409,'STALE_DRAFT','草稿已在其他位置更新，请保留输入并重新载入')
    db.refresh(d);return draft_data(d)
@router.delete('/{did}')
def delete(did:str,request:Request,db=DB):
    d=own_draft(db,did,user(request,db,True),True)
    # Retain immutable post assets; ON DELETE SET NULL removes only draft access.
    db.delete(d);db.flush();return {'ok':True}
