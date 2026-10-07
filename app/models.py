import secrets
from datetime import datetime,timezone
from sqlalchemy import String,Text,Boolean,Integer,DateTime,ForeignKey,JSON,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from .db import Base

def uid(): return secrets.token_hex(16)
def now(): return datetime.now(timezone.utc)
class User(Base):
    __tablename__='users'
    id:Mapped[str]=mapped_column(String(32),primary_key=True,default=uid)
    email:Mapped[str]=mapped_column(String(254),unique=True)
    display_name:Mapped[str]=mapped_column(String(80))
    password_hash:Mapped[str]=mapped_column(Text)
    email_verified:Mapped[bool]=mapped_column(Boolean,default=False)
    is_member:Mapped[bool]=mapped_column(Boolean,default=False)
class Session(Base):
    __tablename__='sessions'
    id:Mapped[str]=mapped_column(String(64),primary_key=True)
    user_id:Mapped[str|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    csrf_token:Mapped[str]=mapped_column(String(80))
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class Verification(Base):
    __tablename__='verifications'
    id:Mapped[str]=mapped_column(String(64),primary_key=True)
    user_id:Mapped[str]=mapped_column(ForeignKey('users.id'))
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    used:Mapped[bool]=mapped_column(Boolean,default=False)
class PasswordReset(Base):
    __tablename__='password_resets'
    id:Mapped[str]=mapped_column(String(64),primary_key=True)
    user_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    used:Mapped[bool]=mapped_column(Boolean,default=False)
class Club(Base):
    __tablename__='clubs'
    id:Mapped[str]=mapped_column(String(32),primary_key=True,default=uid)
    slug:Mapped[str]=mapped_column(String(80),unique=True)
    name:Mapped[str]=mapped_column(String(80))
    description:Mapped[str]=mapped_column(Text,default='')
    accent:Mapped[str]=mapped_column(String(20),default='#c66b3d')
    active:Mapped[bool]=mapped_column(Boolean,default=True)
class Membership(Base):
    __tablename__='memberships'
    club_id:Mapped[str]=mapped_column(ForeignKey('clubs.id'),primary_key=True)
    user_id:Mapped[str]=mapped_column(ForeignKey('users.id'),primary_key=True)
    joined_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    role:Mapped[str]=mapped_column(String(10),default='member')
    can_invite:Mapped[bool]=mapped_column(Boolean,default=False)
class Invitation(Base):
    __tablename__='invitations'
    id:Mapped[str]=mapped_column(String(32),primary_key=True,default=uid)
    code_hash:Mapped[str]=mapped_column(String(64),unique=True)
    club_id:Mapped[str]=mapped_column(ForeignKey('clubs.id'),index=True)
    creator_id:Mapped[str]=mapped_column(ForeignKey('users.id'))
    bound_email:Mapped[str|None]=mapped_column(String(254),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    revoked:Mapped[bool]=mapped_column(Boolean,default=False)
    used_by:Mapped[str|None]=mapped_column(ForeignKey('users.id'),nullable=True)
class Draft(Base):
    __tablename__='drafts'
    id:Mapped[str]=mapped_column(String(32),primary_key=True,default=uid)
    user_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    revision:Mapped[int]=mapped_column(Integer,default=1)
    document:Mapped[dict]=mapped_column(JSON)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Asset(Base):
    __tablename__='assets'
    id:Mapped[str]=mapped_column(String(32),primary_key=True,default=uid)
    user_id:Mapped[str]=mapped_column(ForeignKey('users.id'))
    draft_id:Mapped[str|None]=mapped_column(ForeignKey('drafts.id',ondelete='SET NULL'),nullable=True,index=True)
    mime_type:Mapped[str]=mapped_column(String(40))
    width:Mapped[int]=mapped_column(Integer)
    height:Mapped[int]=mapped_column(Integer)
    filename:Mapped[str]=mapped_column(String(80))
class Post(Base):
    __tablename__='posts'
    __table_args__=(UniqueConstraint('draft_id','revision',name='uq_post_draft_revision'),)
    id:Mapped[str]=mapped_column(String(32),primary_key=True,default=uid)
    draft_id:Mapped[str]=mapped_column(String(32))
    revision:Mapped[int]=mapped_column(Integer)
    author_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    club_id:Mapped[str]=mapped_column(ForeignKey('clubs.id'),index=True)
    document:Mapped[dict]=mapped_column(JSON)
    status:Mapped[str]=mapped_column(String(30))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    published_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    review_note:Mapped[str|None]=mapped_column(Text,nullable=True)
class PostAsset(Base):
    __tablename__='post_assets'
    post_id:Mapped[str]=mapped_column(ForeignKey('posts.id'),primary_key=True)
    asset_id:Mapped[str]=mapped_column(ForeignKey('assets.id'),primary_key=True)
class Review(Base):
    __tablename__='reviews'
    id:Mapped[str]=mapped_column(String(32),primary_key=True,default=uid)
    post_id:Mapped[str]=mapped_column(ForeignKey('posts.id'),unique=True)
    reviewer_id:Mapped[str]=mapped_column(ForeignKey('users.id'))
    decision:Mapped[str]=mapped_column(String(30))
    note:Mapped[str]=mapped_column(Text,default='')
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Comment(Base):
    __tablename__='comments'
    id:Mapped[str]=mapped_column(String(32),primary_key=True,default=uid)
    post_id:Mapped[str]=mapped_column(ForeignKey('posts.id'),index=True)
    user_id:Mapped[str]=mapped_column(ForeignKey('users.id'))
    body:Mapped[str]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
