import argparse
import json

from purchase_analysis.config import RunConfig
from purchase_analysis.pipeline import PipelineRunner


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


if __name__ == "__main__":
    main()
