# Sympy_Tools — Spécification v0.4 : processus, événements et symétries

*Validée avec l'utilisateur le 17/11/2026 (cas 36 à 45 ; niveau de vérification validé sur `v0.4_evenements.pdf`). Implémentée dans la v0.4.0.*

## Idée
On vérifie les symétries **là où on voit encore les événements**. Si les 12 événements du processus sont invariants par une permutation, toutes les équations de moments le sont aussi : à tous les ordres, avant comme après fermeture.

## 1. Le modèle
Deux nouvelles sections, que latex-preview ignore. Les noms anglais `[events]` et `[symmetries]` sont aussi acceptés.

```ini
[evenements]
# nom = taux | saut      (12 lignes explicites, morts globales)
naissance_A1 = rmaxA*NA1 | NA1+1
mort_A1 = (s*(x1 - thA)**2 + (NA1 + NA2)/KA)*NA1 | NA1-1
migration_A1_B1 = m*NA1 | NA1-1, NB1+1
…

[symetries]
phenotypes = A1<->A2, B1<->B2, x1<->x2
niches = A1<->B1, A2<->B2, rmaxA<->rmaxB, KA<->KB, thA<->thB
```

- Dans une symétrie, tout ce qui n'est pas listé ne change pas. Les r_A1… sont déduits de leurs formules.
- Les combinaisons de symétries (« niches + phenotypes ») sont ajoutées automatiquement.
- **Contrôles au chargement** :
  - les taux se lisent comme des expressions, avec des variables NA1… et des paramètres ;
  - les sauts sont de la forme NA1±k ;
  - un taux doit s'annuler quand la population qui diminue vaut 0 ;
  - les échanges d'une symétrie portent sur des noms connus, et l'image de chaque r_ est un r_.
- Une symétrie qui ne respecte pas les événements est acceptée, mais marquée ✗ et signalée.

## 2. Events…
La fenêtre affiche la table compilée : événement, taux, ↦, image, taux de l'image, ✓ ou ✗. Les K_A sont en rouge et les K_B en bleu. Boutons Save PDF… et Copy LaTeX.

## 3. Generate et Take moments
- **Generate d/dt** écrit l'équation d'un moment événement par événement, `E(w·Δf, événement)`, et la place dans l'entrée (mode Equation). En LaTeX, chaque terme est un ⟨…⟩ avec le nom de l'événement en dessous, dans l'ordre des événements du modèle.
- **Take moments** applique la linéarité de l'espérance. Les produits de N deviennent des moments, et le résultat reste regroupé par événement : rmaxA·(…), s(x−θ)²·(…), m·(…), (…)/K.

## 4. Symmetry
Une liste des symétries et un bouton **Apply**. L'opération s'enchaîne comme les autres, sur les deux côtés d'une équation. Les étiquettes d'événements suivent la symétrie. Une remarque signale une équation invariante, et un avertissement une symétrie non valide.

## Cas VALIDÉ
| # | Cas | Attendu |
|---|---|---|
| 36 | modèle par défaut | 12 événements, 3 symétries valides ; latex-preview lit le modèle |
| 37 | Events… | 36 ✓ |
| 38 | symétrie niches sans `KA<->KB` | ✗ sur les 4 morts ; avertissement sur Apply |
| 39 | `mort_A1 = s*(x1 - thA)**2 | NA1-1` | erreur « the rate does not vanish when NA1 = 0 » |
| 40 | Generate `M_A1_A1` | 4 termes E(…, événement), dans l'ordre naissance, mort, migrations en LaTeX |
| 41 | puis Take moments | `m*(-2*M_A1_A1 + n_A1) + m*(2*M_A1_B1 + n_B1) + rmaxA*(2*M_A1_A1 + n_A1) + s*(-2*M_A1_A1 + n_A1)*(-thA + x1)**2 + (M_A1_A1 + M_A1_A2 - 2*T_A1_A1_A1 - 2*T_A1_A1_A2)/KA` |
| 42 | Generate, puis Take moments, puis Isserlis, pour les 14 moments | identique à moment_closure niveau 2, pour les 14 |
| 43 | Generate `M_A1_A1`, puis Symmetry phenotypes | identique à Generate `M_A2_A2` |
| 44 | `dM_A1_B1/dt`, puis Symmetry niches | invariant (remarque) |
| 45 | `dn_A1/dt`, puis niches + phenotypes | `dn_B2_dt`, égal à moment_closure |
