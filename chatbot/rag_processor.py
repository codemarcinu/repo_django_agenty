# chatbot/rag_processor.py
import logging
import ollama
import chromadb
from pathlib import Path

from django.conf import settings
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .models import Document

logger = logging.getLogger(__name__)

# Configuration
CHROMA_PATH = settings.BASE_DIR / "chroma_db"
EMBEDDING_MODEL = 'mxbai-embed-large' # Recommended model for embeddings
COLLECTION_NAME = "rag_documents"

class RagProcessor:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        self.ollama_client = ollama.Client()
        self.collection = self.client.get_or_create_collection(name=COLLECTION_NAME)
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

    def process_document(self, document_id: int):
        """Loads, splits, embeds, and stores a document in the vector DB."""
        try:
            doc = Document.objects.get(pk=document_id)
            doc.status = 'processing'
            doc.save()

            file_path = Path(doc.file.path)
            if not file_path.exists():
                raise FileNotFoundError(f"Document file not found at {file_path}")

            # 1. Load Document
            if file_path.suffix.lower() == '.pdf':
                loader = PyPDFLoader(str(file_path))
            elif file_path.suffix.lower() == '.txt':
                loader = TextLoader(str(file_path))
            else:
                raise ValueError(f"Unsupported file type: {file_path.suffix}")
            
            docs_from_file = loader.load()

            # 2. Split into chunks
            chunks = self.text_splitter.split_documents(docs_from_file)
            logger.info(f"Split {file_path.name} into {len(chunks)} chunks.")

            # 3. Embed and Store
            for i, chunk in enumerate(chunks):
                embedding = self.ollama_client.embeddings(
                    model=EMBEDDING_MODEL,
                    prompt=chunk.page_content
                )['embedding']
                
                self.collection.add(
                    ids=[f"{document_id}_{i}"],
                    embeddings=[embedding],
                    documents=[chunk.page_content],
                    metadatas=[{"source": file_path.name, "document_id": document_id}]
                )

            doc.status = 'ready'
            doc.save()
            logger.info(f"Successfully processed and stored document: {doc.title}")

        except Exception as e:
            logger.error(f"Error processing document {document_id}: {e}", exc_info=True)
            if 'doc' in locals():
                doc.status = 'error'
                doc.save()

    def retrieve_context(self, query: str, n_results: int = 3) -> list[str]:
        """Retrieves relevant context for a given query from the vector DB."""
        try:
            embedding = self.ollama_client.embeddings(
                model=EMBEDDING_MODEL,
                prompt=query
            )['embedding']

            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=n_results
            )
            
            return results.get('documents', [[]])[0]
        except Exception as e:
            logger.error(f"Error retrieving context for query '{query}': {e}")
            return []

# Global instance
rag_processor = RagProcessor()
