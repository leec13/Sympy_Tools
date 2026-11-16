# Sympy_Tools — Spécification v0.2

*Validée avec l'utilisateur le 16/11/2026 (cas 16 à 26). Implémentée dans la v0.2.0.*

## Ajouts

| Ajout | Détail |
|---|---|
| **Isserlis (order 3)** | Chaque `T_…` présent est remplacé par ⟨abc⟩ ≈ ⟨ab⟩⟨c⟩ + ⟨ac⟩⟨b⟩ + ⟨bc⟩⟨a⟩ − 2⟨a⟩⟨b⟩⟨c⟩, c'est-à-dire la fermeture de niveau 2 de `moment_closure.py` (cumulants d'ordre 3 nuls). Code affiché : `rules = {T_…: …}` puis `result = expr.xreplace(rules)`. Le résultat n'est pas développé. Les moments d'ordre ≥ 4 ne sont pas touchés (remarque). Bouton grisé sans T. |
| **Substitute definitions** | r_A1 → `rmaxA - s*(x1 - thA)**2` (section `[definitions]` du modèle). Une définition peut en utiliser une autre ; une boucle est une erreur. Code : `expr.xreplace(rules)`. Bouton grisé sans r_. |
| **Recognize definitions** | Sens inverse, formule → r_A1. La règle est donnée ci-dessous. Bouton grisé si aucun symbole des formules (rmaxA, s…) n'est présent. |
| **Identité visuelle** | Mode clair, avec un liseré de couleur en haut, un fond légèrement teinté et le cadre du code SymPy teinté, pour distinguer la fenêtre de latex-preview. Un thème sombre a été essayé puis abandonné (trop sombre). L'aperçu LaTeX reste une feuille blanche avec le texte noir, et l'image copiée aussi. |

## Règle de « Recognize definitions »

1. L'expression est regroupée par produits de moments, comme « Collect by all moments ».
2. Chaque coefficient c est écrit, **si c'est possible exactement**, sous la forme c = α·r_A1 + β·r_A2 + γ·r_B1 + δ·r_B2 + c₀, où c₀ et les coefficients α… ne contiennent plus aucun symbole des formules (rmaxA, rmaxB, s, x1, x2, thA, thB).
3. Une telle écriture est **unique** : chaque r_ contient un terme qui lui est propre, par exemple s·x1·θA pour r_A1. Il n'y a donc pas d'ambiguïté.
4. Sinon, le coefficient est laissé tel quel, et la remarque « Kept as it is » le signale. C'est le cas du coefficient naissance + mort de ⟨N_A¹⟩, rmaxA + s(x₁−θ_A)².
5. Vérification interne : en remettant les formules à la place des r_, on retrouve exactement l'entrée.

## Cas VALIDÉ

Les cas 22 à 25 ont été validés sur le PDF `v0.2_cas_22_25.pdf` (avant / après, compilé).

| # | Entrée | Opération | Attendu |
|---|---|---|---|
| 16 | `T_A1_A1_A1` | Isserlis | `3*M_A1_A1*n_A1 - 2*n_A1**3` |
| 17 | `T_A1_A1_A2` | Isserlis | `M_A1_A1*n_A2 + 2*M_A1_A2*n_A1 - 2*n_A1**2*n_A2` |
| 18 | `T_A1_A2_B1` | Isserlis | `M_A1_A2*n_B1 + M_A1_B1*n_A2 + M_A2_B1*n_A1 - 2*n_A1*n_A2*n_B1` |
| 19 | équation exacte de d⟨(N_A¹)²⟩/dt (avec T) | Isserlis, puis Compare avec `dM_A1_A1/dt` de moment_closure | **Equal** |
| 20 | `n_A1*(r_A1 - (n_A1 + n_A2)/KA) - m*(n_A1 - n_B1)` | Substitute | `-m*(n_A1 - n_B1) + n_A1*(rmaxA - s*(-thA + x1)**2 - (n_A1 + n_A2)/KA)` |
| 21 | expression sans T, sans r_, ou sans rmaxA… | — | le bouton correspondant est grisé |
| 22 | `dn_A1/dt` de moment_closure | Recognize | `m*n_B1 + n_A1*(-m + r_A1) - M_A1_A1/KA - M_A1_A2/KA` |
| 23 | `dM_A1_A1/dt` de moment_closure | Recognize | `M_A1_A1*(-2*m + 2*r_A1 + 1/KA) + …`, avec `n_A1*(m + rmaxA + s*(-thA + x1)**2)` gardé et signalé |
| 24 | `dM_A1_B1/dt` | Recognize | `M_A1_B1*(-2*m + r_A1 + r_B1) + …` |
| 25 | `2*rmaxA - s*(x1 - thA)**2 - s*(x2 - thA)**2` | Recognize | `r_A1 + r_A2` |
| 26 | les 14 équations de moment_closure | Recognize, puis Substitute, puis Compare avec l'entrée | **Equal** |
