# Sources & références — pipeline RAG / chunking de ctx

> Inventaire de ce qui est **réellement implémenté** dans ctx, avec une référence-ancre
> par technique. Voir la note finale : une bibliographie *exhaustive et causale* est
> volontairement hors de portée (folklore d'ingénierie + churn des preprints).

---

## 1. Pipeline RAG

Implémenté dans `src/ctx/store.py` (`search_chunks`), `src/ctx/rerank.py`,
`src/ctx/embedder.py`, `src/ctx/db.py`.

| # | Technique | Ce que fait ctx | Fichier | Ancre |
|---|-----------|-----------------|---------|-------|
| 1 | Embeddings denses | OpenAI `text-embedding-3-large` (3072-d) ; fallback local `fastembed` | `embedder.py` | doc fournisseur |
| 2 | Index vectoriel ANN | `sqlite-vec` (table `vec0`, distance cosine, `MATCH … k=`) | `db.py`, `store.py` | lib `sqlite-vec` |
| 3 | Recherche lexicale BM25 | SQLite **FTS5** (`chunks_fts MATCH … ORDER BY rank`) — capte termes exacts (codes, noms de fonctions, ids) que l'embedding floute | `store.py` | folklore (FTS5/BM25) |
| 4 | Fusion hybride — RRF | **Reciprocal Rank Fusion**, k=60, combine les rangs vecteur + BM25 | `store.py` | Cormack, Clarke & Büttcher 2009 |
| 5 | Filtrage métadonnées | post-fusion : `kind` / `source` / `tags` | `store.py` | — |
| 6 | Small-to-big | récupère le chunk précis, expansion possible à la section entière via `section_text(doc_id, heading_path)` | `store.py` | LlamaIndex / LangChain (folklore) |
| 7 | Rerank LLM listwise | top-20 candidats → réordonnés par `gpt-5.4-mini`, sortie JSON `{order:[…]}`, BYOK, best-effort (jamais bloquant) | `rerank.py` | RankGPT (listwise LLM rerank) |
| 8 | Ranking status-aware | marqueurs ★ canonical / ◯ plan / ✗ stale / ⚠ duplicate injectés dans le prompt du reranker | `rerank.py` | **spécifique ctx** |

**Réglages empiriques** (pas dérivés d'un théorème) : `k0 = 60` (RRF, le « standard »),
pool = `max(limit*6, 30)`, top-20 au reranker, `RERANK_TIMEOUT_SEC = 8`.

---

## 2. Stratégie de chunking

Implémenté dans `src/ctx/chunking.py`.

| # | Technique | Ce que fait ctx | Ancre |
|---|-----------|-----------------|-------|
| 9 | Chunking **structure-aware** (markdown) | split sur les headings (pas de fenêtre fixe) ; breadcrumb de heading conservé par chunk | [2603.24556](https://arxiv.org/abs/2603.24556), [2606.00881](https://arxiv.org/abs/2606.00881) |
| 10 | **Prefix-fusion** du breadcrumb | on embed `"titre > h1 > h2\n\nbody"` (contextual chunk headers) — gain principal | [2510.24402](https://arxiv.org/abs/2510.24402) ; cousin : Anthropic *Contextual Retrieval* |
| 11 | Re-split borné en tokens | sections > 450 tokens recoupées par fenêtres de paragraphes (estim. 4 char/token) | réglage empirique |
| 12 | Parsing robuste | strip du frontmatter ; fence-aware (ne coupe pas dans un bloc de code) | — |

**Constantes** : `DEFAULT_MAX_TOKENS = 450`, estimation `len(text)//4` tokens.

### Citations arXiv vérifiées (présentes dans le docstring de `chunking.py`)

- **[2603.24556](https://arxiv.org/abs/2603.24556)** — *Evaluating Chunking Strategies For Retrieval-Augmented Generation in Oil and Gas Enterprise Documents* (Taiwo & Yusoff, 2026-03). Conclut : structure-aware > sliding/semantic en top-K, à coût nettement inférieur (moins de fragmentation).
- **[2606.00881](https://arxiv.org/abs/2606.00881)** — *Chunking Methods on RAG — Effectiveness Evaluation Against Computational Cost and Limitations* (Śmigielski et al., Wrocław, 2026). Les gains du semantic chunking ne sont pas proportionnels au surcoût.
- **[2510.24402](https://arxiv.org/abs/2510.24402)** — *Metadata-Driven RAG for Financial Question Answering* (2025-10). Gain principal = embarquer les métadonnées directement dans le texte embeddé (« contextual chunks »).

---

## 3. Contexte recherche — « quand récupérer » & l'inconnu inconnu

Littérature de fond sur le problème : un agent ne lit que ce qu'il sait chercher.

### Active / adaptive RAG (déclenchement par incertitude)
- **[2305.06983](https://arxiv.org/abs/2305.06983)** — *Active Retrieval Augmented Generation* (FLARE) : récupère quand un token à faible confiance apparaît.
- **Self-RAG** — « reflection tokens » émis par le modèle pour déclencher la récupération.
- **[2406.19215](https://arxiv.org/pdf/2406.19215)** — *SeaKR: Self-aware Knowledge Retrieval* : déclenche selon l'incertitude de l'état interne.
- **[2406.12534](https://arxiv.org/html/2406.12534v2)** — *Unified Active Retrieval for RAG*.

### Limite (= notre unknown-unknown)
- **[2509.01476](https://arxiv.org/html/2509.01476v2)** — *Do Retrieval-Augmented LMs Know When They Don't Know?* : self-awareness partielle, abstention imparfaite.
- **[2509.02401](https://arxiv.org/html/2509.02401v1)** — *Towards Agents That Know When They Don't Know* : l'incertitude comme signal de contrôle, et ses limites.
- **[2604.27283](https://arxiv.org/html/2604.27283)** — *Learning When to Remember: Risk-Sensitive Bandits for Abstention-Aware Memory Retrieval in Coding Agents* : l'injection inconditionnelle a un coût de faux positifs → pénaliser l'injection à tort plus fort que l'oubli.

**Conséquence pour ctx** : quand l'agent est *confiant et faux*, aucun signal d'incertitude
ne se déclenche → la récupération auto-déclenchée échoue précisément sur l'inconnu inconnu.
D'où le design : injection **externe et inconditionnelle** d'une **carte légère** (titres + tags,
pas le contenu — cf. coût des faux positifs ci-dessus). Endpoint : `/api/map`.

---

## 4. Note honnête — pourquoi une biblio exhaustive est « quasi impossible »

1. **Folklore d'ingénierie** : RRF, hybride vecteur+BM25, small-to-big, rerank listwise
   n'ont pas une source académique unique — patterns de libs/blogs (LlamaIndex, LangChain,
   Elastic, Anthropic). Les « citer » proprement est arbitraire.
2. **On cite des évaluations, pas des inventeurs** : les papiers chunking ci-dessus *valident*
   la technique sur un domaine ; ils ne l'ont pas inventée. La « vraie source » de
   structure-aware chunking n'existe pas en un seul papier.
3. **Choix multi-déterminés** : 450 tokens, k=60, top-20 sont des réglages empiriques,
   pas dérivés d'un théorème → non « sourçables ».

→ Pratique tenable : **lister l'implémenté + 1 ancre par technique + marquer le reste
« folklore »**. C'est ce que fait ce document.
