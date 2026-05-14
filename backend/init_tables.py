"""Standalone script to create all database tables and copy FAISS index."""
import asyncio
import shutil
import os

# 1. Create database tables
from database import engine, Base
import models  # noqa: F401 — triggers model registration on Base

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[init] All database tables created/verified.")

# 2. Copy pre-built FAISS index to storage volume if not present
def copy_faiss_index():
    """Copy FAISS index files from git source to the storage volume."""
    storage_dir = os.environ.get("STORAGE_DIR", "/app/storage")
    target_dir = os.path.join(storage_dir, "faiss_laws")
    target_index = os.path.join(target_dir, "laws.index")
    
    # Source: these files come from git, available at /app/storage/faiss_laws/
    # But since /app/storage is overridden by a named volume, check /app/ root too
    source_candidates = [
        "/app/storage/faiss_laws",  # Direct path (if volume not overriding)
        "/app/faiss_laws_source",   # Alternative mount point
    ]
    
    # Also check if files exist in the backend source directory
    src_dir = "/app"
    for root, dirs, files in os.walk(src_dir):
        if "laws.index" in files and "laws_records.pkl" in files:
            source_candidates.insert(0, root)
            break
    
    if os.path.exists(target_index):
        size = os.path.getsize(target_index)
        print(f"[init] FAISS index already exists ({size} bytes), skipping copy.")
        return
    
    os.makedirs(target_dir, exist_ok=True)
    
    for src in source_candidates:
        src_index = os.path.join(src, "laws.index")
        src_records = os.path.join(src, "laws_records.pkl")
        if os.path.exists(src_index) and os.path.exists(src_records):
            shutil.copy2(src_index, target_dir)
            shutil.copy2(src_records, target_dir)
            print(f"[init] FAISS index copied from {src} to {target_dir}")
            return
    
    print("[init] FAISS index source not found — will be built on first use.")

if __name__ == "__main__":
    copy_faiss_index()
    asyncio.run(create_tables())
    print("[init] Initialization complete!")
