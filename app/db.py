from sqlalchemy import create_engine,event
from sqlalchemy.orm import DeclarativeBase,sessionmaker
class Base(DeclarativeBase): pass

def configure_db(settings):
    if settings.database_url.startswith('sqlite:///'):
        from pathlib import Path
        path=settings.database_url.removeprefix('sqlite:///')
        if path!=':memory:': Path(path).parent.mkdir(parents=True,exist_ok=True)
    engine=create_engine(settings.database_url,connect_args={'check_same_thread':False,'timeout':30} if settings.database_url.startswith('sqlite') else {},pool_pre_ping=True)
    if engine.dialect.name=='sqlite':
        @event.listens_for(engine,'connect')
        def configure(conn,_):
            conn.execute('PRAGMA foreign_keys=ON')
            conn.execute('PRAGMA busy_timeout=30000')
    return engine,sessionmaker(engine,expire_on_commit=False)

def get_db(request):
    with request.app.state.session_factory() as db:
        try:
            # SQLite does not support row locks: acquire its write transaction before reads.
            if db.bind.dialect.name=='sqlite': db.connection().exec_driver_sql('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback(); raise
