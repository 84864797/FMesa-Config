"""与GUI共用生成器的命令行入口，不连接硬件。"""
import argparse
import json
from pathlib import Path
from config_core import defaults,validate,export


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('sample');p.add_argument('output',type=Path)
    p=sub.add_parser('validate');p.add_argument('project',type=Path)
    p=sub.add_parser('export');p.add_argument('project',type=Path);p.add_argument('directory',type=Path)
    a=parser.parse_args()
    if a.command=='sample':
        if a.output.exists():raise FileExistsError(a.output)
        a.output.write_text(json.dumps(defaults(),ensure_ascii=False,indent=2),encoding='utf-8');return
    c=json.loads(a.project.read_text(encoding='utf-8-sig'));errors,warnings=validate(c)
    print(json.dumps(dict(errors=errors,warnings=warnings),ensure_ascii=False,indent=2))
    if errors:raise SystemExit(1)
    if a.command=='export':print(export(c,a.directory))


if __name__=='__main__':main()
