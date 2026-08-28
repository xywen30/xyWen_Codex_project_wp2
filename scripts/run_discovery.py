from __future__ import annotations

import argparse,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from app.config import settings
from app.database import Database
from app.services.discovery_service import DiscoveryService


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--source",choices=["REAL"],default="REAL"); args=parser.parse_args()
    settings.ensure(); db=Database(settings.database_path); db.initialize()
    statuses={r["source"]:r["status"] for r in db.source_statuses()}
    result=DiscoveryService(ROOT,db).run(settings.keywords(),statuses); print(result); return result


if __name__=="__main__": main()
