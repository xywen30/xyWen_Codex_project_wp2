from __future__ import annotations

import argparse,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from app.config import settings
from app.database import Database
from app.services.analysis_service import AnalysisService


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--source",choices=["REAL","DEMO"],default="REAL"); args=parser.parse_args()
    settings.ensure(); db=Database(settings.database_path); db.initialize(); result=AnalysisService(settings,db).run(args.source); print(result); return result


if __name__=="__main__": main()
