# Refonte ctx — Périmètre v1

**Date :** 2026-06-10 · **Statut :** validé sur le fond, **build post-dogfood** · issu d'une session grill-me.

---

## 1. Identité

ctx passe de *« router token-efficient sur des .md in-tree »* à **un outil de centralisation de doc où ctx *est* la doc**.

Le router n'est plus le produit — c'est une **capacité** de l'outil de centralisation.

## 2. Étoile polaire

> **Ne jamais dépenser de tokens d'agent inutilement.**

Tout choix de design se juge à une question : *est-ce que ça fait passer des octets par le LLM pour rien ?* Si oui → mauvais.

## 3. Le modèle — deux verbes, un front, une échappatoire

| Surface | Pour qui | Rôle |
|---|---|---|
| `/read` | agents | renvoie du **contenu** (pas un `path:line`), et seulement le **bon doc / la bonne section** — jamais une liste de candidats à trier |
| `/write` | agents | l'agent émet le contenu **une fois** ; ctx stocke. SSOT par construction (instance unique partagée) |
| **frontend** | humains | browse / lecture / recherche via l'UI web — aucun fichier local requis |
| `.ctxignore` | — | la **seule** raison de garder un vrai fichier sur disque : un **consommateur file-native** (build de doc, outil du repo qui lit les .md, humain qui veut son éditeur). Tout le reste vit **uniquement dans ctx** |

**Propriété clé :** tous les agents d'un dev **et** le 2ᵉ dev voient la même doc, parce que toute lecture/écriture passe par un point unique. Pas de sync, pas de copies qui dérivent — le point de passage *est* la SSOT.

## 4. Les gaspillages tués

| Gaspillage aujourd'hui | Tué par |
|---|---|
| Lire 3 `.md` pour deviner le canonique | `/read` en sert **1**, le bon |
| Lire un fichier entier pour 2 paragraphes | `/read` sert **la section** |
| Re-dériver ce qu'un autre agent a déjà trouvé | `/read` le **record existant** (mémoire partagée) |
| Régénérer un report introuvable | il est dans ctx → **trouvable**, pas refait |
| Contenu qui transite par le LLM pour atterrir sur disque | **supprimé** — pas de matérialisation |

## 5. Non-goals (ne pas ressusciter)

- ❌ Matérialiser les docs sur le disque local
- ❌ Daemon de sync local / cache read-through fichier
- ❌ Faire écrire le fichier par l'agent (gaspille des tokens)
- ❌ Split de stockage living/record → la distinction se réduit à un **flag de lifecycle** (les records ne périment pas par l'âge / ne sont pas dédupliqués), pas à deux emplacements

## 6. Backlog plomberie (interne à ctx, invisible du contrat)

- **Substrat** : Pôle A = fichiers + table sqlite de versions, derrière une interface `Store` pluggable → switch Supabase (Pôle B) en drop-in. Même pattern que l'embedder pluggable v0.8.
- **Recherche** : sqlite-vec reste l'index unifié.
- **Adressage** : ID opaque stable pour les docs centraux (= aussi le handle de référence pour relay).
- **Accès** : plat partagé, auth léger, `workspace_id` gardé dormant.
- **Concurrence** : sérialisation des écritures côté serveur ; sémantique par type à trancher (record = append ; mémoire = last-write-wins ; doc partagé = vrai conflit).
- **Extraction de section** au `/read` (servir le minimum).
- **Relay** : dégraissage → transport pur ; vault + mémoire migrent vers ctx (rupture de contrat `search_vault` / `get_memory` → phase de compat).

## 7. Séquencement (⚠️ la vraie décision live)

Le freeze actuel **dogfoode le router**. Ne **pas** démarrer cette refonte avant la fin du dogfood — sinon on jette la seule preuve terrain en cours. Ordre : **identité figée maintenant (gratuit) → refonte juste après le dogfood**.

## 8. Premier pas concret (jour J)

Le **contrat des deux endpoints**, parce que tout se branche dessus :

```
/read(query | doc_id, [section]) -> { id, content (min utile), freshness }
/write(content, [doc_id], [kind]) -> { id }       # kind = flag lifecycle
```

Tout le reste (substrat, concurrence, relay) se construit derrière ce contrat.

## 9. État d'implémentation (v0.9 → v0.10)

Construit sur la branche `docs/refonte-v1`, **sans merge ni deploy** (dogfood router intact sur `master`).

**Livré dans ce repo :**
- ✅ `ctx_write` / `ctx_read` — contenu, pas pointeurs (v0.9)
- ✅ Store pluggable `SqliteStore` (Pôle A), docs adressés par ID opaque → switch Supabase = drop-in (v0.9)
- ✅ docs ctx sous `source_id='ctx'` virtuel, jamais purgés par l'indexeur (v0.9)
- ✅ `kind='record'` exempté de péremption-âge + dédup (v0.9)
- ✅ Extraction de **section** au `ctx_read` (servir le minimum) (v0.10)
- ✅ **Sérialisation des écritures** (lock côté serveur) (v0.10)
- ✅ **Hook d'enforcement** `deploy/hooks/ctx-md-guard.sh` + `.ctxignore.example` (deny .md direct → `ctx_write`, dégradation gracieuse si ctx down) (v0.10)
- ✅ **Frontend reader** `/doc/{ext_id}` — markdown rendu (renderer maison anti-XSS), TOC, métadonnées, copy-id ; design ui-ux-pro-max sur les tokens existants (v0.10)

**Hors de ce repo (ne PAS construire ici) :**
- ⏸️ **Supabase (Pôle B)** — infra post-dogfood ; le `Store` est déjà l'interface de swap, rien à faire côté ctx tant que le besoin n'est pas là.
- ⏸️ **Dégraissage de relay + migration `search_vault`/`get_memory`** — c'est le repo **`agent-relay`**, un autre système. À mener là-bas, pas dans ctx.

**Reste ouvert (décisions, pas du code) :** sémantique de concurrence par type (record=append / mémoire=last-write-wins / doc partagé=conflit) ; couplage harnais du hook (repo-level vs user-level).
