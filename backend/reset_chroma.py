"""
Script to reset ChromaDB collections when embedding model changes (dimension mismatch fix).
Run inside Docker container: python reset_chroma.py
"""
import os
import sys
import pickle
import chromadb
from chromadb.config import Settings as ChromaSettings

STORAGE_DIR = os.environ.get("STORAGE_DIR", "./storage")
CHROMA_PATH = f"{STORAGE_DIR}/chroma_db"
BM25_PATH = f"{STORAGE_DIR}/legislation_bm25.pkl"

COLLECTIONS = ["legislation", "knowledge_base"]

def main():
    print(f"Connecting to ChromaDB at: {CHROMA_PATH}")
    client = chromadb.PersistentClient(
        path=CHROMA_PATH,
        settings=ChromaSettings(anonymized_telemetry=False),
    )

    existing = [c.name for c in client.list_collections()]
    print(f"Existing collections: {existing}")

    for name in COLLECTIONS:
        # Try both names with and without prefix
        variants = [name, f"{name}_v2"]
        for col_name in existing:
            if name in col_name.lower():
                try:
                    client.delete_collection(col_name)
                    print(f"✓ Deleted collection: {col_name}")
                except Exception as e:
                    print(f"✗ Failed to delete {col_name}: {e}")

    # Also reset BM25 index
    if os.path.exists(BM25_PATH):
        os.remove(BM25_PATH)
        print(f"✓ Deleted BM25 index: {BM25_PATH}")

    # Verify
    remaining = [c.name for c in client.list_collections()]
    print(f"\nRemaining collections after reset: {remaining}")
    print("\n✅ ChromaDB reset complete. Restart the backend to rebuild with E5 (768-dim) embeddings.")
    print("   Then re-upload legislation files via the admin panel.")

if __name__ == "__main__":
    main()
