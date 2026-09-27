import argparse
import json
import sys
import traceback
from pathlib import Path
from core import Build, inspect_rom, apply_session, save_json
from patcher_workflow import history_root, patch_local

def main():
    parser=argparse.ArgumentParser(description='ColorOS 17 Dolby native patcher')
    parser.add_argument('--rom');parser.add_argument('--output')
    actions=parser.add_mutually_exclusive_group()
    actions.add_argument('--apply',action='store_true',help='原位修改（默认行为）')
    actions.add_argument('--build-only',action='store_true',help='仅生成补丁，不写回 ROM')
    parser.add_argument('--adb',metavar='SERIAL');parser.add_argument('--remote-rom')
    parser.add_argument('--adb-live',action='store_true',help='只读当前系统分区，仅允许检查/生成模块')
    parser.add_argument('--module',metavar='SAVE_ZIP',help='生成 KSU 模块；不修改 ROM 或安装')
    parser.add_argument('--resume-adb',metavar='SESSION')
    parser.add_argument('--inspect',action='store_true')
    parser.add_argument('--restore',metavar='SESSION')
    parser.add_argument('--gui-smoke',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.adb_live and (not args.adb or args.rom or args.remote_rom or args.apply or args.restore or args.resume_adb or not (args.module or args.inspect)):
        parser.error('--adb-live 仅支持 --adb SERIAL 配合 --module SAVE_ZIP 或 --inspect')
    if args.module and (args.apply or args.restore or args.resume_adb or args.build_only or args.inspect):
        parser.error('--module 不可与修改/回退/构建/检查操作混用')
    if len(sys.argv)==1 or args.gui_smoke:
        from gui import App
        app=App()
        if args.gui_smoke:app.after(1500,app.destroy)
        app.mainloop();return 0
    def log(s):
        if sys.stdout:print(s,flush=True)
    try:
        if args.module:
            from ksu_module import generate_module
            if args.adb and not args.adb_live and (not args.remote_rom or args.rom):parser.error('ADB 模块生成需 --remote-rom，不可混用 --rom')
            if args.remote_rom and not args.adb:parser.error('--remote-rom 需要 --adb')
            session=generate_module(args.module,root=args.remote_rom if args.adb else args.rom,serial=args.adb,
                                    live=args.adb_live,log=log,output=args.output)
            log(str(session));return 0
        if args.adb_live:
            from ksu_module import inspect_live
            log(str(inspect_live(args.adb,log)));return 0
        if args.resume_adb:
            from adb_mode import monitor_remote
            monitor_remote(args.resume_adb,log=log);return 0
        if args.restore:
            if (Path(args.restore)/'adb-session.json').is_file():
                from adb_mode import apply_remote
                apply_remote(args.restore,restore=True,log=log)
            else:apply_session(args.restore,restore=True,log=log)
            return 0
        if args.adb or args.remote_rom:
            if not (args.adb and args.remote_rom) or args.rom:parser.error('ADB 模式需同时指定 --adb SERIAL 和 --remote-rom PATH，不可与 --rom 混用')
            from adb_mode import run_adb
            session=run_adb(args.adb,args.remote_rom,log,inspect_only=args.inspect,build_only=args.build_only,output=args.output)
            log(str(session));return 0
        if not args.rom:parser.error('--rom is required')
        if args.inspect:
            _,info=inspect_rom(args.rom);log(json.dumps(info,ensure_ascii=False,indent=2));return 0
        session=patch_local(args.rom,log,build_only=args.build_only,output=args.output)
        log(str(session));return 0
    except Exception as e:
        log(traceback.format_exc())
        save_json((Path(args.output) if args.output else history_root())/'最近失败.json',{'error':str(e),'traceback':traceback.format_exc()})
        return 1

if __name__=='__main__':
    raise SystemExit(main())
