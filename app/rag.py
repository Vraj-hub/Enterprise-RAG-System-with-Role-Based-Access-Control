import uuid

ALL_ROLES = ["Admin", "Manager", "Employee"]

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"

_client = None
_collection = None
_model = None


def get_collection():
    global _client, _collection
    if _collection is None:
        import chromadb
        _client = chromadb.PersistentClient(path="./chroma_db")
        _collection = _client.get_or_create_collection("documents")
    return _collection


def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def split_text(text, size=800, overlap=100):
    chunks = []
    start = 0
    while start < len(text):
        chunk = text[start:start + size].strip()
        if chunk:
            chunks.append(chunk)
        start += size - overlap
    return chunks


def add_document(doc_id, title, pages, allowed_roles):
    ids, texts, metas = [], [], []
    n = 0
    for page_no, text in pages:
        for chunk in split_text(text):
            ids.append(f"doc{doc_id}_{uuid.uuid4().hex[:8]}_chunk{n}")
            texts.append(chunk)
            meta = {
                "doc_id": doc_id,
                "source": title,
                "page_no": page_no,
                "allowed_roles": ",".join(allowed_roles),
            }
            for r in ALL_ROLES:
                meta[f"access_{r}"] = r in allowed_roles
            metas.append(meta)
            n += 1
    if not ids:
        return 0
    embeddings = get_model().encode(texts).tolist()
    get_collection().add(ids=ids, documents=texts, embeddings=embeddings, metadatas=metas)
    return n


def search(question, role, k=3):
    embedding = get_model().encode([question]).tolist()
    result = get_collection().query(
        query_embeddings=embedding,
        n_results=k,
        where={f"access_{role}": {"$eq": True}},
    )
    docs = result["documents"][0]
    metas = result["metadatas"][0]
    return list(zip(docs, metas))

def ask_llm(question, chunks):
    import requests
    context = "\n\n".join(c[0] for c in chunks)
    prompt = (
        "You are an enterprise assistant. Answer the question using ONLY the "
        "context below. If the answer is not in the context, say exactly: "
        "'I could not find this information in the documents available to you.'\n\n"
        f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"
    )
    r = requests.post(
        OLLAMA_URL,
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
        timeout=300,
    )
    r.raise_for_status()
    return r.json()["response"].strip()

def ask_llm(question, chunks):
    import requests
    context = "\n\n".join(c[0] for c in chunks)
    prompt = (
        "You are an enterprise assistant. Answer the question using ONLY the "
        "context below. If the answer is not in the context, say exactly: "
        "'I could not find this information in the documents available to you.'\n\n"
        f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"
    )
    r = requests.post(
        OLLAMA_URL,
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
        timeout=300,
    )
    r.raise_for_status()
    return r.json()["response"].strip()