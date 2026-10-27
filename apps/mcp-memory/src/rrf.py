"""
Reciprocal Rank Fusion (RRF) — Multi-channel rank fusion.
Portado e adaptado do Tencent Hy-Memory (Cormack et al., 2009).

Fórmula:
    score(d) = Σ_c [ w_c / (k + rank_c(d)) ]

Propriedades fundamentais:
- Elimina a incomparabilidade matemática entre distâncias vetoriais e scores de palavras-chave.
- Cada canal (vetorial, léxico, temporal) ranqueia independentemente seus candidatos.
- Documentos que aparecem no topo de múltiplos canais são impulsionados organicamente.
"""

from typing import Any, Dict, List, Optional

RRF_K = 60

def rrf_fuse(
    channels: Dict[str, List[Dict[str, Any]]],
    weights: Optional[Dict[str, float]] = None,
    k: int = RRF_K,
    id_key: str = 'id'
) -> List[Dict[str, Any]]:
    """
    Funde múltiplos canais ranqueados via RRF.

    Args:
        channels: Dicionário onde cada chave é o nome do canal (ex: 'vec', 'kw', 'recency')
                  e o valor é uma lista de dicionários já ordenados pelo critério do canal.
        weights: Pesos por canal (default: 1.0 para cada).
        k: Constante de suavização RRF (default: 60).
        id_key: Chave de identificação única do item (default: 'id').

    Returns:
        Lista ordenada decrescente por rrf_score.
    """
    weights = weights or {}
    acc: Dict[Any, Dict[str, Any]] = {}

    for channel_name, items in channels.items():
        w = float(weights.get(channel_name, 1.0))
        if w <= 0 or not items:
            continue
            
        for rank, item in enumerate(items, start=1):
            item_id = item.get(id_key)
            if item_id is None:
                continue
                
            contrib = w / (k + rank)
            if item_id not in acc:
                acc[item_id] = {
                    'item': item,
                    'rrf_score': 0.0,
                    'channel_ranks': {},
                    'channels_hit': []
                }
            
            acc[item_id]['rrf_score'] += contrib
            acc[item_id]['channel_ranks'][channel_name] = rank
            acc[item_id]['channels_hit'].append(channel_name)

    results = list(acc.values())
    results.sort(key=lambda x: x['rrf_score'], reverse=True)
    return results
