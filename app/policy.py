from sqlalchemy import select
from .common import membership,missing
from .models import Club,Post,Membership

def can_read(db,p,u):
    c=db.get(Club,p.club_id)
    if not c or not c.active:return False
    m=membership(db,p.club_id,u.id if u else None)
    scope=p.document['scope']
    if scope=='club' and not m:return False
    if scope=='members' and not (u and u.is_member):return False
    if p.status=='published':return True
    return bool(u and (u.id==p.author_id or m and m.role=='owner'))

def readable(db,p,u):
    if not p or not can_read(db,p,u):missing()
    return p

def published_query(db,u):
    # ACL precedes filtering, text search, pagination and counting, at the SQL layer.
    query=select(Post).join(Club,Club.id==Post.club_id).where(Club.active==True,Post.status=='published')
    from sqlalchemy import or_
    scope=Post.document['scope'].as_string()
    clauses=[scope=='public']
    if u:
        if u.is_member:clauses.append(scope=='members')
        clubs=select(Membership.club_id).where(Membership.user_id==u.id)
        clauses.append((scope=='club') & Post.club_id.in_(clubs))
    return query.where(or_(*clauses))
