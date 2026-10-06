"""Explicit operator bootstrap; no HTTP privilege elevation or default credentials."""
import argparse,getpass,os
from sqlalchemy import select
from .config import Settings
from .db import configure_db
from .models import User,Club,Membership
from .auth import passwords,password
from .common import email,text

def main():
    parser=argparse.ArgumentParser(description='间外运营工具')
    commands=parser.add_subparsers(dest='command',required=True)
    bootstrap=commands.add_parser('bootstrap',help='显式创建邮箱已验证的团主与社团')
    for key in ('email','display-name','club-slug','club-name'):bootstrap.add_argument('--'+key,required=True)
    bootstrap.add_argument('--club-description',default='')
    args=parser.parse_args()
    settings=Settings();engine,factory=configure_db(settings)
    raw=os.getenv('BOOTSTRAP_PASSWORD') or getpass.getpass('运营账号密码（至少10字符）：')
    addr=email(args.email);name=text(args.display_name,2,30);pwd=password(raw)
    slug=text(args.club_slug,2,80)
    import re
    if not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*',slug):parser.error('club-slug 仅允许小写英数字与中划线')
    with factory.begin() as db:
        if db.scalar(select(User).where(User.email==addr)):parser.error('邮箱已存在；bootstrap不会自动提升现有账户权限')
        if db.scalar(select(Club).where(Club.slug==slug)):parser.error('社团slug已存在')
        u=User(email=addr,display_name=name,password_hash=passwords.hash(pwd),email_verified=True,is_member=True)
        c=Club(slug=slug,name=text(args.club_name,2,80),description=text(args.club_description,0,2000))
        db.add_all([u,c]);db.flush();db.add(Membership(club_id=c.id,user_id=u.id,role='owner',can_invite=True))
        user_id,club_id=u.id,c.id
    engine.dispose()
    print('创建完成：user_id='+user_id+' club_id='+club_id)
if __name__=='__main__':main()
