"""Interactive inspection of persisted vectors without reingestion."""
import argparse
import json
import sys
from .embeddings import MyEmbedder
from .prepare import ROOT
from .run import MODEL
from .store import QdrantStore


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('question')
    parser.add_argument('--strategy', choices=['A', 'B', 'C'], default='C')
    parser.add_argument('--chapter', type=int, choices=range(1, 13))
    args = parser.parse_args()
    if args.chapter and args.strategy != 'C':
        parser.error('--chapter is supported by strategy C only')
    embedder = MyEmbedder(MODEL)
    store = QdrantStore(ROOT / 'starter/.qdrant', embedder.dimensions)
    try:
        hits = store.search(args.strategy, embedder.embed_query(args.question),
                            filters={'chapter': args.chapter} if args.chapter else None)
        print(json.dumps(hits, ensure_ascii=False, indent=2))
    finally:
        store.close()


if __name__ == '__main__':
    main()
