# Sympy_Tools — Spécification v0.1

*Rédigée et validée avec l'utilisateur le 16/11/2026. Implémentée dans la v0.1.0.*

## 1. Objectif

Une petite application de bureau (macOS) pour **manipuler avec SymPy des expressions de dynamique de populations**, en particulier des équations de moments. On colle une expression ou une équation en texte « python-like » (par exemple la sortie de latex-preview), on applique une opération, et on récupère le résultat en texte Python (pour VS Code ou un notebook) ou en LaTeX (pour Overleaf ou Keynote).

C'est la suite de **latex-preview** (v0.7.3), dont on réutilise le cœur : le modèle `.ini`, la traduction LaTeX → Python et la compilation TeX Live.

**Inclus dans la v0.1** : entrée Expression ou Equation, lecture vérifiée, Simplify / Factor / Expand / Collect by / Compare, affichage du code SymPy, sorties Python et LaTeX, copie, modèle modifiable.

**Hors v0.1** (prévu ensuite) : fermeture des moments (cumulants nuls, Isserlis), symétries (phénotypes 1↔2, niches A↔B), génération des équations à partir du processus (`moment_closure.py` généralisé), entrée `M(NA1, NA1)`, scripts `solve_ivp` / Gillespie.

## 2. Conventions décidées

| Sujet | Décision |
|---|---|
| Variables de base | `NA1, NA2, NB1, NB2`, c'est-à-dire « N » suivi du code (règle `variable = N{code}` du modèle) |
| Moments en texte | `n_A1`, `M_A1_A2`, `T_A1_A1_A2`, `Q_…` : préfixe selon l'ordre, puis les codes dans l'ordre A1, A2, B1, B2 (tableau des 34 moments) |
| Dérivées en texte | `dM_A1_A1_dt` (règle `derivee = d{nom}_dt` du modèle) |
| Paramètres | les noms du modèle : `m, s, x1, x2, thA, thB, rmaxA, rmaxB, KA, KB, r_A1…` |
| Moments dans le code | objet SymPy qui range ses arguments tout seul, `M(NA1, NA1)` (interne, prévu pour la fermeture et les symétries) ; remplacements avec `xreplace` et non `subs(simultaneous=True)` |
| Interface | entièrement en anglais |
| README, commentaires | en anglais quand c'est possible sans tout réécrire ; les messages de TeX venant de latex-preview restent en français |

## 3. Modèle

- Même fichier `.ini` que latex-preview, avec le même modèle par défaut (2 niches × 2 phénotypes).
- Boutons **Edit model…** (fenêtre séparée, comme dans latex-preview), **Save model as…** et **Load model…**. Le modèle courant est conservé d'une session à l'autre.
- Sections et clés : on lit les noms français **et** anglais (`[parametres]` / `[parameters]`, `separateur` / `separator`, `derivee` / `derivative`…). On écrit en français tant que latex-preview ne lit que le français.
- **Hypothèses sur les symboles (validé)** : section facultative `[hypotheses]` (ou `[assumptions]`), que latex-preview ignore sans erreur. Par défaut, comme dans `moment_closure.py` : `rmaxA rmaxB s KA KB m` positifs, `x1 x2 thA thB` réels. Ces hypothèses changent ce que Simplify peut faire : `sqrt(x**2)` ne devient `Abs(x)` que si x est réel. Les symboles sont tous créés à un seul endroit, à partir du modèle, pour qu'un même nom donne toujours le même symbole.

## 4. Entrées

- **Expression** : un seul champ, par exemple `2*M_A1_A1** + M_A1_A1`.
- **Equation** : deux champs, `lhs` et `rhs`.
- Un texte contenant un `=` collé dans le champ Expression (par exemple `dM_A1_A1_dt = …`) est découpé : on passe en mode Equation, avec une remarque.
- **Lecture vérifiée** : on lit avec `parse_expr`, puis on contrôle tout ce qui a été lu.
  - Seuls sont connus les noms du modèle, les noms de moments ou de dérivées bien formés, et une liste blanche de fonctions (`exp, log, sqrt, sin, cos, Abs`…). On n'utilise ni `eval` libre ni `sympify` sans contrôle.
  - `^` est accepté comme `**`, avec une remarque.
  - Un nom de moment invalide est une **erreur** (voir les cas 1 et 2) ; s'il y a plusieurs erreurs de noms, elles sont listées ensemble.
  - Un moment écrit dans le désordre est **remis dans l'ordre**, avec une remarque.
  - Un symbole hors modèle est **accepté**, avec une remarque.
  - Un exposant qui n'est pas un nombre donne un **avertissement**.
  - La lecture est toujours affichée.
- **Liste des symboles lus**, qui sert aussi de vérification : elle est rangée par catégorie (Moments order 1 / 2 / 3…, Derivatives, Parameters, Not in model) et marque les noms corrigés. C'est elle qui remplit le menu Collect by.

## 5. Opérations

Sur une équation, chaque opération s'applique **à chaque côté séparément**. Compare est l'exception : il porte sur les deux côtés ensemble.

| Bouton | Code SymPy affiché |
|---|---|
| Simplify | `result = sp.simplify(expr)` |
| Factor | `result = sp.factor(expr)` |
| Expand | `result = sp.expand(expr)` |
| Collect by ▾ `v` | `result = sp.collect(sp.expand(expr), v)` |
| Collect by ▾ *all moments* | `result = sp.collect(sp.expand(expr), [n_A1*M_A1_B1, …, n_A1, M_A1_A1, …])` : produits de moments présents d'abord (ajout pendant le développement : une équation fermée garde ainsi un seul coefficient par produit de moments) |
| Compare | `equal = sp.cancel(lhs - rhs) == 0` |

- **Collect by** développe d'abord, donc une forme factorisée est perdue. C'est normal et la remarque est affichée.
- **Compare** donne trois verdicts :
  1. **Equal (proved)** : quand l'expression ne contient que des fractions rationnelles, `cancel(lhs − rhs) == 0` est une preuve. Avec `exp`, `sqrt`… on essaie ensuite `simplify(lhs − rhs) == 0`.
  2. **Different** : on affiche `lhs − rhs` regroupé par moment. On dit « prouvé » si `cancel` donne une fraction rationnelle non nulle, ou si l'on trouve un contre-exemple en des valeurs rationnelles.
  3. **Undetermined** : SymPy ne conclut pas. On fait un test numérique en quelques points, en indiquant clairement que ce n'est pas une preuve.
- **Use result as input** : le résultat remplace l'entrée, pour enchaîner les opérations.
- **Code SymPy** : une ou deux lignes, celles qui sont réellement exécutées, à but pédagogique. Elles utilisent des symboles ordinaires et peuvent donc être recopiées dans un notebook.

## 6. Sorties et copie

- Le **résultat en texte Python** est toujours visible : noms canoniques, `**` pour les puissances.
- **Show LaTeX : ☐ code ☐ rendered**.
  - Les noms LaTeX viennent du modèle (`\langle (N_{A}^{x_1})^{2} \rangle`).
  - Le rendu passe par TeX Live (compilateur de latex-preview, coupure des lignes longues par breqn).
- **Copy** propose quatre formats :
  - **Python** ;
  - **LaTeX** simple, qui marche dans l'éditeur d'équations de Keynote (sans `dmath` ni `breqn`), à vérifier sur un vrai exemple ;
  - **LaTeX for Overleaf** (`dmath*`, comme ⇧⌘L dans latex-preview) ;
  - **Image** (pour Keynote).

## 7. Esquisse de la fenêtre

```
┌ Sympy_Tools ─────────────────────────────────────────────────────────────┐
│ Model: 2 niches × 2 phenotypes   [Edit model…] [Load model…] [Save as…] │
│ ○ Expression   ● Equation                                                │
│ lhs  [ dM_A1_A1_dt                                                   ]  │
│ rhs  [ 2*M_A1_A1*rmaxA + n_A1*rmaxA - 2*M_A1_A1*m + ...              ]  │
│ Reading: ⚠ M_A2_A1 → M_A1_A2    ⓘ delta not in model     [Symbols ▾]    │
│                                                                          │
│ [Simplify] [Factor] [Expand] [Collect by ▾ M_A1_A1 ] [Compare]           │
│                                                                          │
│ SymPy code                                                               │
│   result = sp.collect(sp.expand(rhs), M_A1_A1)                           │
│                                                                          │
│ Result                                   [Copy ▾] [↑ Use as input]       │
│   M_A1_A1*(-2*m + 2*rmaxA + 1/KA) + ...                                  │
│ Show LaTeX: ☐ code   ☐ rendered                                          │
│   ┌ preview ─────────────────────────────────────────────┐               │
│   └──────────────────────────────────────────────────────┘               │
└──────────────────────────────────────────────────────────────────────────┘
```

## 8. Architecture

```
sympy_tools/
  core/                 # sans interface graphique, testable, utilisable dans un notebook
    model.py            # chargement du .ini (clés FR/EN), symboles et hypothèses, registre des moments
    reading.py          # texte → expression : parse_expr + contrôles, liste des symboles, remarques
    operations.py       # Simplify/Factor/Expand/Collect/Compare → résultat + ligne de code SymPy
    output.py           # texte Python, LaTeX (noms du modèle), LaTeX Keynote / Overleaf
  ui/                   # PySide6 : fenêtre principale, éditeur de modèle, aperçu
tests/                  # un test par cas « VALIDÉ »
```

- **Dépendance** : `latex_preview.core` (modèle, compilation, export, breqn), installé dans le même environnement conda avec `pip install -e ../latex-preview`. Il n'est pas recopié, pour qu'une correction profite aux deux outils.
- **Environnement** : conda, comme latex-preview (Python 3.12, PySide6, SymPy, PyMuPDF, pytest).
- **Calculs** dans un processus séparé et interruptible, comme dans latex-preview : un `simplify` peut être long.

## 9. Cas VALIDÉ (deviennent les tests)

Résultats vérifiés avec SymPy 1.14.

| # | Entrée | Opération | Attendu |
|---|---|---|---|
| 1 | `2*M_A1_A1** + M_A1_A1` | lecture | ⚠ « non-numeric exponent », lu `2*M_A1_A1**M_A1_A1` (`a** + b` = a^(+b) en Python) |
| 1b | `2*M_A1_A1** + M_A1_MA1` | lecture | ✗ « unknown code MA1 (codes: A1, A2, B1, B2) » |
| 2 | `M_A1_A1_A2` | lecture | ✗ « 3 indices → T_A1_A1_A2 » |
| 3 | `M_A2_A1` | lecture | lu `M_A1_A2`, ⓘ « reordered » |
| 4 | `delta*n_A1` | lecture | accepté, ⓘ « delta: not in model » |
| 5 | `n_A1^2` | lecture | lu `n_A1**2`, ⓘ « ^ read as ** » |
| 6 | `dM_A1_A1_dt = 2*M_A1_A1*rmaxA` dans le champ Expression | lecture | passage en mode Equation, `dM_A1_A1_dt` rangé dans Derivatives |
| 7 | `(n_A1 + n_A2)**2` | Expand | `n_A1**2 + 2*n_A1*n_A2 + n_A2**2` |
| 8 | `M_A1_A1*m - M_A1_A1*rmaxA` | Factor | `M_A1_A1*(m - rmaxA)` |
| 9 | `M_A1_A1*m + 2*M_A1_A1*rmaxA + n_A1*m` | Collect by M_A1_A1 | `M_A1_A1*(m + 2*rmaxA) + m*n_A1` |
| 10 | `m*(n_A1 + n_B1 + 2*M_A1_B1 - 2*M_A1_A1) + rmaxA*(n_A1 + 2*M_A1_A1) + (M_A1_A1 + M_A1_A2)/KA` | Collect by all moments | `M_A1_A1*(-2*m + 2*rmaxA + 1/KA) + 2*M_A1_B1*m + m*n_B1 + n_A1*(m + rmaxA) + M_A1_A2/KA` |
| 11 | lhs `(M_A1_A1 + M_A1_A2)/KA`, rhs `M_A1_A1/KA + M_A1_A2/KA` | Compare | **Equal (proved)** |
| 12 | lhs `M_A1_A1 + M_A1_A2/KA`, rhs `(M_A1_A1 + M_A1_A2)/KA` | Compare | **Different**, lhs − rhs = `M_A1_A1*(KA - 1)/KA` (l'erreur du script 2) |
| 13 | lhs `exp(x1)*exp(s)`, rhs `exp(x1 + s)` | Compare | **Equal (proved)**, par `simplify` |
| 14 | équation de l'exemple 10 = elle-même factorisée | Simplify | appliqué à chaque côté ; Compare donne Equal |
| 15 | un résultat quelconque | Use as input | le résultat devient l'entrée, et la liste des symboles est mise à jour |

À noter : Factor et Simplify mettent tout sur un dénominateur commun dès qu'il y a `1/KA` (exemple 10 : `(KA*(…) + M_A1_A1 + M_A1_A2)/KA`). C'est le comportement de SymPy, et on l'affiche tel quel.

## 10. Points ouverts

- Vérifier la copie LaTeX dans Keynote sur un vrai exemple.
