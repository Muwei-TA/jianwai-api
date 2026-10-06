import threading,time,secrets
from collections import defaultdict,deque
from fastapi import FastAPI,Request,Depends
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from .config import Settings
from .db import configure_db
from .common import APIError,csrf
from .auth import passwords
from . import auth,clubs,invites,documents,media,posts

def create_app(settings=None):
    settings=settings or Settings()
    app=FastAPI(title='间外社区 API',version='0.1.0')
    app.state.settings=settings
    app.state.engine,app.state.session_factory=configure_db(settings)
    app.state.dummy_password_hash=passwords.hash(secrets.token_urlsafe(32))
    rates=defaultdict(deque);lock=threading.Lock()
    @app.exception_handler(APIError)
    async def api_error(request,exc):return JSONResponse(status_code=exc.status,content={'error':{'code':exc.code,'message':exc.message}})
    @app.exception_handler(RequestValidationError)
    async def validation_error(request,exc):return JSONResponse(status_code=422,content={'error':{'code':'VALIDATION_ERROR','message':'输入格式无效'}})
    @app.exception_handler(HTTPException)
    async def http_error(request,exc):
        code='NOT_FOUND' if exc.status_code==404 else 'VALIDATION_ERROR'
        message='内容不存在或无权访问' if exc.status_code==404 else '请求无效'
        return JSONResponse(status_code=exc.status_code,content={'error':{'code':code,'message':message}})
    @app.middleware('http')
    async def guards(request,call_next):
        path=request.url.path
        if request.method not in {'GET','HEAD','OPTIONS'}:
            # Single-instance memory limits. Client IP is direct peer; no untrusted proxy header.
            sensitive={'/api/v1/auth/register','/api/v1/auth/login','/api/v1/auth/resend-verification','/api/v1/auth/verify-email','/api/v1/invites/preview','/api/v1/invites/redeem'}
            group=path if path in sensitive else 'comments' if path.startswith('/api/v1/posts/') and path.endswith('/comments') else 'write'
            budget=10 if path in sensitive else 30 if group=='comments' else 120
            key=(request.client.host if request.client else 'unknown',group)
            current=time.monotonic()
            with lock:
                if key not in rates and len(rates)>=10000:
                    for stale in list(rates):
                        if not rates[stale] or rates[stale][-1]<current-60:rates.pop(stale,None)
                    if len(rates)>=10000:return JSONResponse(status_code=429,content={'error':{'code':'RATE_LIMITED','message':'操作过于频繁，请稍后再试'}})
                history=rates[key]
                while history and history[0]<current-60:history.popleft()
                if len(history)>=budget:return JSONResponse(status_code=429,content={'error':{'code':'RATE_LIMITED','message':'操作过于频繁，请稍后再试'}},headers={'Retry-After':'60'})
                history.append(current)
                if len(rates)>10000:
                    for stale in list(rates):
                        if rates[stale] and rates[stale][-1]<current-60:rates.pop(stale,None)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Cache-Control']='private, no-store'
        return response
    for router in (auth.router,clubs.router,invites.router,documents.router,media.router,posts.router):app.include_router(router,prefix='/api/v1',dependencies=[Depends(csrf)])
    @app.get('/api/v1/health')
    def health():return {'status':'ok'}
    return app
app=create_app()
