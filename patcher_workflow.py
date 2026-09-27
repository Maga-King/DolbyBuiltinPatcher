"""Dolby patcher defaults: patch in place, keep automatic PC-side history."""
import os
from pathlib import Path
from core import Build, apply_session, save_json


def history_root():
    base=Path(os.environ.get('LOCALAPPDATA') or Path.home()/'.local/share')
    path=base/'DolbyBuiltinPatcher/history'
    path.mkdir(parents=True,exist_ok=True)
    return path


def patch_local(rom,log=lambda s:None,build_only=False,output=None):
    output=Path(output) if output else history_root()/'local'
    log('自动备份/记录目录：'+str(output))
    session=Build(rom,output,log).run()
    if not build_only:apply_session(session,log=log)
    save_json(output/'最新构建.json',dict(session=str(session),applied=not build_only))
    return session
