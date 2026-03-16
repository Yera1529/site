import asyncio
from services.rag import RAGService
from services.ai import AIService

async def test_rag():
    rag = RAGService()
    ai = AIService()
    
    print("Testing BM25 extraction and RRF...")
    query = "Не обеспечили безопасность труда, статья 22 Трудового кодекса"
    
    # 1. Поиск законов
    laws = rag.search_relevant_laws(query=query, top_k=3)
    print("\n--- Retrieved Laws ---")
    for law in laws:
        print(f"[{law.get('score', 0):.4f}] {law.get('law_title', '')} (ст. {law.get('article_number', 'N/A')}): {law.get('text', '')[:100]}...")
        
    print("\nTesting Prompt Generation...")
    template = "<p>Test Template</p>"
    facts = "На заводе ТОО 'Рога и Копыта' упал кран. Выявлено нарушение статьи 22 Трудового кодекса РК."
    instructions = ""
    
    # 2. Промпт
    sys_prompt, user_prompt = ai.build_generation_prompt(
        template_text=template,
        facts=facts,
        kb_context="",
        custom_instructions=instructions,
        additional_instructions="",
        retrieved_laws=laws
    )
    
    print("\n--- User Prompt Part ---")
    print(user_prompt[:500] + "\n...\n" + user_prompt[-500:])

if __name__ == "__main__":
    import os
    from config import Settings
    os.environ["STORAGE_DIR"] = "/tmp/legalassist_storage"
    
    asyncio.run(test_rag())
