import argparse
import json

from purchase_analysis.config import RunConfig
from purchase_analysis.pipeline import PipelineRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Purchase analysis pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_all = subparsers.add_parser("run-all", help="Fetch data and build marts")
    run_all.add_argument("--date-from", default="01.01.2024")
    run_all.add_argument("--date-to", default="31.12.2025")
    run_all.add_argument("--max-pages", type=int, default=20)
    run_all.add_argument("--request-timeout", type=int, default=30)
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
        )
        result = PipelineRunner(config=config).run_all()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
