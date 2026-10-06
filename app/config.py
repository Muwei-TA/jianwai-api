"""Validated runtime configuration; production never silently uses outbox mail."""
import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path('.env'),override=False)

@dataclass
class Settings:
    app_env: str = field(default_factory=lambda:os.getenv('APP_ENV','development'))
    database_url: str = field(default_factory=lambda:os.getenv('DATABASE_URL','sqlite:///./var/jianwai.db'))
    allowed_origins: list[str] = field(default_factory=lambda:os.getenv('ALLOWED_ORIGINS','http://localhost:5173,http://127.0.0.1:5173').split(','))
    cookie_secure: bool = field(default_factory=lambda:os.getenv('COOKIE_SECURE','false').lower()=='true')
    media_dir: Path = field(default_factory=lambda:Path(os.getenv('MEDIA_DIR','var/media')))
    outbox_dir: Path = field(default_factory=lambda:Path(os.getenv('OUTBOX_DIR','var/outbox')))
    public_web_url: str = field(default_factory=lambda:os.getenv('PUBLIC_WEB_URL','http://localhost:5173'))
    smtp_host: str = field(default_factory=lambda:os.getenv('SMTP_HOST',''))
    smtp_port: int = field(default_factory=lambda:int(os.getenv('SMTP_PORT','587')))
    smtp_username: str = field(default_factory=lambda:os.getenv('SMTP_USERNAME',''))
    smtp_password: str = field(default_factory=lambda:os.getenv('SMTP_PASSWORD',''))
    smtp_from: str = field(default_factory=lambda:os.getenv('SMTP_FROM',''))
    smtp_starttls: bool = field(default_factory=lambda:os.getenv('SMTP_STARTTLS','true').lower()=='true')
    def __post_init__(self):
        self.media_dir=Path(self.media_dir); self.outbox_dir=Path(self.outbox_dir)
        self.allowed_origins=[x.strip().rstrip('/') for x in self.allowed_origins if x.strip()]
        if self.app_env not in {'development','test','production'}: raise ValueError('APP_ENV 无效')
        if self.app_env=='production':
            if not self.database_url.startswith(('postgresql://','postgresql+psycopg://')): raise ValueError('生产必须配置 PostgreSQL DATABASE_URL')
            if not self.smtp_host or not self.smtp_from: raise ValueError('生产必须配置 SMTP_HOST 和 SMTP_FROM')
            if not self.cookie_secure: raise ValueError('生产必须 COOKIE_SECURE=true')
            if not self.allowed_origins or any(not x.startswith('https://') for x in self.allowed_origins): raise ValueError('生产 ALLOWED_ORIGINS 必须显式 HTTPS')
            if not self.public_web_url.startswith('https://'): raise ValueError('生产 PUBLIC_WEB_URL 必须 HTTPS')
