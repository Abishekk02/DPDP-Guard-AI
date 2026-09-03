from pathlib import Path
from app.services.rag import search_documents

QUERY = "What obligations does a Data Fiduciary have regarding personal data?"


def main():
    index_path = Path("vectorstore/index.faiss")
    chunks_path = Path("vectorstore/chunks.json")

    if not index_path.exists() or not chunks_path.exists():
        print("Vectorstore not found.")
        print("Run first: python -m app.services.document_ingestion")
        return

    print(f"Query: {QUERY}\n")
    results = search_documents(QUERY, top_k=5)

    for i, result in enumerate(results, start=1):
        print(f"--- Result {i} ---")
        print(f"Source : {result['source']}")
        print(f"Page   : {result['page']}")
        print(f"Score  : {result['score']}")
        print(f"Text   : {result['text'][:300]}...")
        print()


if __name__ == "__main__":
    main()
