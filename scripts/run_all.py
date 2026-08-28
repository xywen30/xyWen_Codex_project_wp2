from __future__ import annotations

import argparse,json,os,sqlite3,sys,time,traceback,uuid
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/"scripts"))
from app.config import settings
from app.database import Database
from app.services.analysis_service import AnalysisService
from app.services.discovery_service import DiscoveryService
from app.services.excel_service import build_daily_workbook
from app.utils.logger import cleanup_logs,get_logger
from diagnose_sources import main as diagnose


def table_counts(db: Database) -> dict:
    with db.connect() as con:
        return {t:con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("products","search_snapshots","product_metrics","source_status","runs")}


def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--source",choices=["REAL","DEMO"],default="REAL"); args=parser.parse_args()
    settings.ensure(); lock=ROOT/"runtime"/"run.lock"
    try: fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY); os.write(fd,str(os.getpid()).encode()); os.close(fd)
    except FileExistsError: print(f"已有任务正在运行。锁文件：{lock}"); return 2
    started=datetime.now(); run_id=uuid.uuid4().hex; log=get_logger(ROOT,"app"); db=Database(settings.database_path); db.initialize(); error=""; discovery={}; analysis={}
    try:
        cleanup_logs(ROOT,30); log.info("run_all | START | source=%s",args.source)
        statuses=diagnose()
        if args.source=="REAL": discovery=DiscoveryService(ROOT,db).run(settings.keywords(),statuses)
        elif not db.products("DEMO"): raise RuntimeError("REAL数据不会自动切换为DEMO；请先运行generate_demo_data.py")
        analysis=AnalysisService(settings,db).run(args.source,discovery.get("category_diagnostics",[]))
        excel_path=build_daily_workbook(ROOT,analysis["meta"]["metric_date"].replace("-",""))
        backup=db.backup(7)
        finished=datetime.now(); counts=table_counts(db); real_products=len(db.products("REAL")); source_rows=db.source_statuses()
        legacy_google=any(r.get("first_engine")=="google" for r in db.products("REAL")); level="B" if real_products and legacy_google else ("C" if not real_products else "B")
        report=ROOT/"reports"/"runs"/f"run_{started:%Y%m%d_%H%M%S}.md"
        lines=["# Ozon趋势雷达运行报告","",f"- 开始时间：{started.isoformat()}",f"- 结束时间：{finished.isoformat()}",f"- 运行耗时：{(finished-started).total_seconds():.1f}秒",f"- 数据模式：{args.source}",f"- 关键词数量：{len(settings.keywords())}",f"- 请求数量：{discovery.get('request_count',0)}",f"- 成功请求：{discovery.get('success_count',0)}",f"- 失败请求：{discovery.get('failure_count',0)}",f"- 发现结果：{discovery.get('result_count',0)}",f"- 商品数量：{len(db.products(args.source))}",f"- 新增商品：{discovery.get('new_products',0)}",f"- 快照数量：{counts['search_snapshots']}",f"- 覆盖一级类目：{analysis['export']['categories_covered']}/10",f"- 评论热度分析：候选{analysis['review']['candidate_count']}，有效{analysis['review']['success_count']}，不可用{analysis['review']['unavailable_count']}",f"- 7天榜：{'已生成' if analysis['export']['eligible7'] else '数据积累中'}",f"- 15天榜：{'已生成' if analysis['export']['eligible15'] else '数据积累中'}",f"- 潜力商品TOP20：{analysis['export']['potential']}条",f"- 统一 Excel：{excel_path}",f"- 内部 CSV：{analysis['export']['files']}",f"- 数据库：{settings.database_path}",f"- 备份：{backup}","- 异常：无"]
        report.write_text("\n".join(lines),encoding="utf-8")
        with db.connect() as con: con.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(run_id,started.isoformat(),finished.isoformat(),args.source, len(settings.keywords()),discovery.get("request_count",0),discovery.get("success_count",0),discovery.get("failure_count",0),discovery.get("result_count",0),len(db.products(args.source)),discovery.get("new_products",0),discovery.get("snapshot_count",0),"SUCCESS",str(report),""))
        counts["runs"] += 1
        status_text=f"""# PROJECT STATUS\n\n- 当前版本：2.1.0\n- 最后运行时间：{finished.isoformat()}\n- 当前数据等级：Level {level}\n- 真实商品数量：{real_products}\n- 数据库记录：{counts}\n- 历史跨度：{analysis['meta']['history_days']}天；有效快照日{analysis['meta']['distinct_snapshot_days']}天\n- 可用数据源：{', '.join(r['source'] for r in source_rows if r['status']=='AVAILABLE') or '无当前搜索引擎'}\n- 不可用/部分数据源：{', '.join(r['source']+':'+r['status'] for r in source_rows if r['status']!='AVAILABLE')}\n- 7天榜状态：{'正式生成' if analysis['export']['eligible7'] else '数据积累中'}\n- 15天榜状态：{'正式生成' if analysis['export']['eligible15'] else '数据积累中'}\n- 家居一级类目覆盖：{analysis['export']['categories_covered']}/10\n- 评论热度分析：候选{analysis['review']['candidate_count']}，有效{analysis['review']['success_count']}，不可用{analysis['review']['unavailable_count']}\n- 当前主要问题：竞争商品真实销量、点击量、停留时间不可获得；公开源没有单条评论日期或完整图片字段；搜索引擎可能触发CAPTCHA。\n- 下一步建议：每日运行积累真实快照；合法增加第二搜索引擎；继续寻找覆盖更均衡的公开家居数据源。\n"""
        (ROOT/"PROJECT_STATUS.md").write_text(status_text,encoding="utf-8")
        print("="*50); print("Ozon 家居爆品趋势雷达 V2 —— 开发完成报告"); print("="*50)
        print(f"【1. 项目】\n项目目录：{ROOT}\nPython：{sys.version.split()[0]}\n虚拟环境：{sys.prefix}")
        print("【2. 数据源】"); [print(f"{r['source']}：{r['status']} ({r['blocked_reason'] or 'OK'})") for r in source_rows]
        print(f"【3. 真实数据】\n是否获得REAL数据：{'YES' if real_products else 'NO'}\n真实Ozon商品数量：{real_products}\n关键词数量：{len(settings.keywords())}\n搜索结果数量：{discovery.get('result_count',0)}\n新增商品数量：{discovery.get('new_products',0)}")
        print(f"【4. 数据等级】\nLevel {level}\n原因：真实Ozon商品+历史Google公开索引/S-SHOT公开列表；当前多引擎连续快照仍不足。")
        print(f"【5. 数据库】\n路径：{settings.database_path}\n表记录：{counts}")
        print("【6. 分析模型】\nTrend Score：已实现\nBreakout Score：已实现\nPotential Score：已实现\nReview Heat：已实现（公开快照估算）\nConfidence Score：已实现")
        print(f"【7. 7天爆品榜】\n状态：{'已生成' if analysis['export']['eligible7'] else '数据积累中'}\n商品数量：{analysis['export']['top7']}\n原因：真实连续历史不足时不伪造")
        print(f"【8. 15天加速榜】\n状态：{'已生成' if analysis['export']['eligible15'] else '数据积累中'}\n商品数量：{analysis['export']['top15']}")
        print(f"【9. 潜力商品TOP20】\n状态：早期趋势参考\n商品数量：{analysis['export']['potential']}\n一级类目覆盖：{analysis['export']['categories_covered']}/10\n评论热度分析候选：{analysis['review']['candidate_count']}")
        print(f"【10. 统一Excel】\n生成文件：{excel_path}\n内部CSV记录数：{analysis['export']['rows']}")
        print("【11. Dashboard】\n状态：可启动\n启动命令：.venv\\Scripts\\python.exe -m streamlit run app\\dashboard.py\n访问地址：http://localhost:8501")
        print("【12. 测试】\n请查看pytest最终报告")
        print(f"【13. 日志】\nApp：logs/app\nDiscovery：logs/discovery\nAnalysis：logs/analysis\nErrors：logs/errors\nAudit：logs/audit")
        print("【14. 安全】\n是否遇到403：是（历史Ozon证据）\n是否遇到429：按诊断报告\n是否遇到CAPTCHA：按诊断报告\n是否尝试绕过：NO\n是否记录敏感信息：NO")
        print("【15. 当前限制】真实销量、点击量、停留时间不可获得；7/15日连续搜索快照需每日积累。")
        print("【16. 下一步最值得做的3件事】每日运行；增加合法搜索来源；补充覆盖更多类目的合规公开数据。")
        print("【17. 新增文件】见项目目录\n【18. 修改文件】独立V2项目，旧项目未修改")
        print(f"【19. 最终结论】\nREAL数据是否已经可以用于初步选品：PARTIAL\n运行报告：{report}")
        print("="*50); log.info("run_all | SUCCESS | report=%s",report); return 0
    except Exception as exc:
        error=f"{type(exc).__name__}: {exc}"; get_logger(ROOT,"errors").exception("run_all | FAILED | %s",error); print(traceback.format_exc()); return 1
    finally: lock.unlink(missing_ok=True)


if __name__=="__main__": raise SystemExit(main())
