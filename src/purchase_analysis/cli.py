import argparse
import json

from purchase_analysis.config import CURATED_DIR, OUTPUT_DIR, RunConfig
from purchase_analysis.pipeline import PipelineRunner
from purchase_analysis.postgres_loader import default_dsn, sync_postgres


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Purchase analysis pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_all = subparsers.add_parser("run-all", help="Fetch data and build marts")
    defaults = RunConfig()
    run_all.add_argument("--date-from", default=defaults.date_from)
    run_all.add_argument("--date-to", default=defaults.date_to)
    run_all.add_argument("--max-pages", type=int, default=defaults.max_pages)
    run_all.add_argument("--request-timeout", type=int, default=defaults.request_timeout)
    run_all.add_argument("--max-sberb2b-details", type=int, default=defaults.max_sberb2b_details)
    run_all.add_argument("--download-documents-limit", type=int, default=defaults.download_documents_limit)
    run_all.add_argument("--max-document-size-bytes", type=int, default=defaults.max_document_size_bytes)
    run_all.add_argument("--max-sberb2b-api-probes", type=int, default=defaults.max_sberb2b_api_probes)

    sync_pg = subparsers.add_parser(
        "sync-postgres",
        help="Apply PostgreSQL schema/views/marts and load the current curated CSV snapshot",
    )
    sync_pg.add_argument("--dsn", default=default_dsn())
    sync_pg.add_argument("--admin-dsn")
    sync_pg.add_argument("--create-database", action="store_true")
    sync_pg.add_argument("--curated-dir", default=str(CURATED_DIR))
    sync_pg.add_argument("--source-sprints-dir", default=str(OUTPUT_DIR / "source_sprints"))
    sync_pg.add_argument("--skip-enrichment", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "run-all":
        config = RunConfig(
            date_from=args.date_from,
            date_to=args.date_to,
            max_pages=args.max_pages,
            request_timeout=args.request_timeout,
            max_sberb2b_details=args.max_sberb2b_details,
            download_documents_limit=args.download_documents_limit,
            max_document_size_bytes=args.max_document_size_bytes,
            max_sberb2b_api_probes=args.max_sberb2b_api_probes,
        )
        result = PipelineRunner(config=config).run_all()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "sync-postgres":
        if not args.dsn:
            parser.error(
                "sync-postgres requires --dsn or the PURCHASE_ANALYSIS_PG_DSN / DATABASE_URL environment variable."
            )
        result = sync_postgres(
            dsn=args.dsn,
            admin_dsn=args.admin_dsn,
            create_database=args.create_database,
            curated_dir=args.curated_dir,
            source_sprints_dir=args.source_sprints_dir,
            include_enrichment=not args.skip_enrichment,
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
