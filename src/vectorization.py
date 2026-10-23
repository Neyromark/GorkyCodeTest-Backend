from sentence_transformers import SentenceTransformer
from sentence_transformers.util import normalize_embeddings
import numpy as np

_model = SentenceTransformer(
    'sentence-transformers/paraphrase-multilingual-mpnet-base-v2',
    device='cpu'
)

def vector(raw_text : str):
    '''
    Возвращает нормированный вектор одного предложения np.ndarray(1, 768)
    '''
    if not isinstance(raw_text, str) or not raw_text.strip():
        return np.zeros(768)

    return _model.encode(raw_text, normalize_embeddings=True)