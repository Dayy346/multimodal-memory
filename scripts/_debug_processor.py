from transformers import AutoProcessor

p = AutoProcessor.from_pretrained(
    "jinaai/jina-embeddings-v5-omni-small",
    trust_remote_code=True,
)
print(type(p), p)
