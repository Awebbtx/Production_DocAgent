from __future__ import annotations

import argparse
import asyncio
import json

from it_doc_builder.config import get_settings
from it_doc_builder.models import DocumentBuildRequest
from it_doc_builder.services.pipeline import DocumentPipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Build IT reports from raw notes.")
    parser.add_argument("input", help="Path to a JSON file matching the DocumentBuildRequest schema.")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as handle:
        request_data = json.load(handle)

    request = DocumentBuildRequest.model_validate(request_data)
    result = asyncio.run(DocumentPipeline(get_settings()).build_document(request))
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()