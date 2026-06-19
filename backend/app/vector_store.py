import faiss
import numpy as np
import logging
import google.generativeai as genai
from backend.app.config import GEMINI_API_KEY, EMBEDDING_MODEL
from backend.app.parsers import configure_gemini

logger = logging.getLogger(__name__)

class RAGEngine:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or GEMINI_API_KEY
        self.dimension = None
        self.index = None
        self.chunks = []

    def _get_embedding(self, text: str, is_query: bool = False) -> list:
        """Helper to fetch embedding from Gemini."""
        configure_gemini(self.api_key)
        task_type = "retrieval_query" if is_query else "retrieval_document"
        
        response = genai.embed_content(
            model=EMBEDDING_MODEL,
            content=text,
            task_type=task_type
        )
        return response['embedding']

    def chunk_text(self, text: str, max_chunk_size: int = 500) -> list:
        """Splits text into readable chunks based on paragraphs or line lengths."""
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = ""
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
                
            # If a single paragraph is larger than max_chunk_size, split it into smaller pieces
            if len(para) > max_chunk_size:
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                # Split this paragraph into sub-chunks
                sub_chunks = [para[i:i+max_chunk_size] for i in range(0, len(para), max_chunk_size)]
                # Add all except the last one to chunks directly
                chunks.extend(sub_chunks[:-1])
                # The last sub-chunk becomes the current_chunk for subsequent folding
                current_chunk = sub_chunks[-1]
            elif len(current_chunk) + len(para) < max_chunk_size:
                current_chunk += "\n\n" + para if current_chunk else para
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = para
                
        if current_chunk:
            chunks.append(current_chunk)
            
        return chunks

    def add_documents(self, resume_text: str, jd_text: str):
        """Chunks and embeds the candidate's resume and job description, loading them into FAISS."""
        resume_chunks = [f"Resume Section:\n{c}" for c in self.chunk_text(resume_text)]
        jd_chunks = [f"Job Description Section:\n{c}" for c in self.chunk_text(jd_text)]
        
        all_chunks = resume_chunks + jd_chunks
        if not all_chunks:
            return

        embeddings = []
        valid_chunks = []
        
        for chunk in all_chunks:
            try:
                emb = self._get_embedding(chunk)
                if self.dimension is None:
                    self.dimension = len(emb)
                    self.index = faiss.IndexFlatIP(self.dimension)
                embeddings.append(emb)
                valid_chunks.append(chunk)
            except Exception as e:
                logger.error(f"Failed to generate embedding for chunk: {e}")
                # Skip failed chunk embeddings
                continue
                
        if embeddings and self.index is not None:
            vectors = np.array(embeddings, dtype=np.float32)
            # Normalize vectors for Cosine Similarity (Inner Product index)
            faiss.normalize_L2(vectors)
            self.index.add(vectors)
            self.chunks.extend(valid_chunks)
            logger.info(f"Loaded {len(valid_chunks)} chunks into FAISS vector index.")

    def retrieve(self, query: str, k: int = 3) -> str:
        """Retrieves top K chunks related to the query. Falls back to keyword search on error."""
        if not self.chunks or self.index is None:
            return self._keyword_fallback_retrieve(query, k)
            
        try:
            query_emb = self._get_embedding(query, is_query=True)
            query_vector = np.array([query_emb], dtype=np.float32)
            faiss.normalize_L2(query_vector)
            
            distances, indices = self.index.search(query_vector, min(k, len(self.chunks)))
            
            retrieved_chunks = []
            for idx in indices[0]:
                if idx != -1 and idx < len(self.chunks):
                    retrieved_chunks.append(self.chunks[idx])
                    
            return "\n\n---\n\n".join(retrieved_chunks)
            
        except Exception as e:
            logger.warning(f"RAG embedding search failed, falling back to keyword search: {e}")
            return self._keyword_fallback_retrieve(query, k)

    def _keyword_fallback_retrieve(self, query: str, k: int = 3) -> str:
        """Simple substring score fallback retrieve."""
        query_words = set(query.lower().split())
        scored_chunks = []
        
        for chunk in self.chunks:
            chunk_lower = chunk.lower()
            score = sum(1 for word in query_words if word in chunk_lower)
            scored_chunks.append((score, chunk))
            
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        top_k = [chunk for score, chunk in scored_chunks[:k] if score > 0]
        
        if not top_k:
            # If no match, return first few chunks
            top_k = self.chunks[:k]
            
        return "\n\n---\n\n".join(top_k)
