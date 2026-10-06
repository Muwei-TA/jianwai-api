from io import BytesIO
import secrets,warnings
from fastapi import APIRouter,Request,UploadFile,File
from fastapi.responses import Response
from PIL import Image,UnidentifiedImageError
from sqlalchemy import select
from .common import *
from .models import Asset,Draft,Post,PostAsset
from .documents import own_draft
from .policy import can_read
router=APIRouter()
MAX_BYTES=10*1024*1024;MAX_PIXELS=25_000_000
@router.post('/drafts/{did}/media',status_code=201)
def upload(did:str,request:Request,file:UploadFile=File(...),db=DB):
    u=user(request,db,True);own_draft(db,did,u,True)
    formats={'image/jpeg':('JPEG','jpg'),'image/png':('PNG','png'),'image/webp':('WEBP','webp')}
    if file.content_type not in formats:invalid('仅接受 JPEG、PNG、WebP 图片')
    content=file.file.read(MAX_BYTES+1)
    if len(content)>MAX_BYTES:invalid('图片最多10 MiB')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                fmt,ext=formats[file.content_type]
                if image.format!=fmt or image.width*image.height>MAX_PIXELS or getattr(image,'n_frames',1)!=1:invalid('图片格式或像素数量无效')
                image.load();width,height=image.size
                clean=Image.new('RGBA' if image.mode=='RGBA' and fmt!='JPEG' else 'RGB',image.size)
                clean.paste(image.convert(clean.mode));out=BytesIO();clean.save(out,format=fmt)
    except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError,Image.DecompressionBombWarning):invalid('图片无法解码')
    settings=request.app.state.settings;settings.media_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
    filename=secrets.token_hex(32)+'.'+ext
    target=settings.media_dir/filename;target.write_bytes(out.getvalue());target.chmod(0o600)
    a=Asset(user_id=u.id,draft_id=did,mime_type=file.content_type,width=width,height=height,filename=filename);db.add(a);db.flush()
    return dict(id=a.id,url='/api/v1/media/'+a.id,mime_type=a.mime_type,width=width,height=height)
@router.get('/media/{aid}')
def get(aid:str,request:Request,db=DB):
    a=db.get(Asset,aid);u=user(request,db)
    if not a:missing()
    d=db.get(Draft,a.draft_id) if a.draft_id else None
    allowed=bool(u and d and d.user_id==u.id)
    if not allowed:
        for p in db.scalars(select(Post).join(PostAsset,PostAsset.post_id==Post.id).where(PostAsset.asset_id==a.id)):
            if can_read(db,p,u):allowed=True;break
    if not allowed:missing()
    path=request.app.state.settings.media_dir/a.filename
    if not path.is_file():missing()
    # Read before transaction completes to keep ACL decisions and bytes consistent.
    return Response(path.read_bytes(),media_type=a.mime_type,headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})
