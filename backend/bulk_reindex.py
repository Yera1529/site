"""
Bulk reindex all legislation from PostgreSQL → ChromaDB with E5-768dim embeddings.
Run inside Docker: python /app/bulk_reindex.py
"""
import asyncio
import sys
sys.path.insert(0, '/app')

async def main():
    from database import engine
    from models.legislation import LegislationDoc
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
    from services.rag import RAGService

    rag = RAGService()
    print(f"RAG service initialized.")

    async with AsyncSession(engine) as session:
        result = await session.execute(select(LegislationDoc))
        laws = result.scalars().all()
        print(f"Found {len(laws)} legislation documents in PostgreSQL")

        success = 0
        errors = 0
        for i, law in enumerate(laws, 1):
            try:
                rag.index_legislation(
                    doc_id=str(law.id),
                    text=law.content or law.title,
                    law_title=law.title or "",
                    category=law.category or "иное",
                )
                success += 1
                if i % 3 == 0:
                    print(f"  [{i}/{len(laws)}] OK: {law.title[:60]}")
            except Exception as e:
                errors += 1
                print(f"  ERROR [{i}] {law.title[:50]}: {e}")

        print(f"\nReindex complete: {success} success, {errors} errors")
        try:
            rag._rebuild_bm25()
            print("BM25 index rebuilt")
        except Exception as e:
            print(f"BM25 rebuild error: {e}")

asyncio.run(main())
