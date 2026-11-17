# Sympy_Tools — Spécification v0.3 : enchaîner les opérations

*Validée avec l'utilisateur le 17/11/2026 (cas 27 à 35, pas de bouton Undo). Implémentée dans la v0.3.0.*

## Problème constaté
Les boutons agissaient toujours sur l'entrée. Après **Isserlis**, un **Collect by all moments** repartait donc de l'entrée et faisait réapparaître les `T_…`, sauf si l'on pensait à cliquer sur « ↑ Use as input ».

## Règle
- Chaque opération s'applique **au résultat affiché** s'il y en a un, sinon à l'entrée.
- **L'entrée n'est jamais modifiée** par une opération : elle reste la source.
- Le **titre** montre la chaîne : *Result — Isserlis (order 3) → Collect by all moments*.
- **SymPy code** montre toutes les étapes, chacune avec son nom en commentaire. La première étape part de `expr` (ou `lhs`, `rhs`), les suivantes de `result`. Le cadre grandit jusqu'à 7 lignes, puis défile jusqu'à la dernière.
- La **liste Collect by** et les boutons Isserlis / Substitute / Recognize se basent sur le **résultat courant**.
- **↺ Back to input** efface la chaîne. Modifier l'entrée, changer de mode ou de modèle a le même effet.
- **↑ Use as input** recopie le résultat courant dans les champs d'entrée et efface la chaîne.
- **Compare** vérifie l'équation courante **sans la remplacer**. L'opération suivante repart de l'équation, pas de lhs − rhs.
- La copie et l'aperçu LaTeX portent toujours sur le résultat affiché.
- Pas de bouton Undo (décision du 17/11/2026).

## Cas VALIDÉ

| # | Ce que tu fais | Ce que le programme affiche |
|---|---|---|
| 27 | Expression `m*n_A1 + T_A1_A1_A2/KA`, **Isserlis**, puis **Collect by all moments** | `m*n_A1 + M_A1_A1*n_A2/KA + 2*M_A1_A2*n_A1/KA - 2*n_A1**2*n_A2/KA` (sans T) ; titre *Isserlis (order 3) → Collect by all moments* ; code en 3 lignes |
| 28 | (suite) le champ d'entrée | inchangé, avec les T |
| 29 | (suite) la liste Collect by | les symboles du résultat (n_A2, M_A1_A2…), sans T ; Isserlis est grisé |
| 30 | **↺ Back to input** | retour à l'entrée lue ; T_A1_A1_A2 revient dans la liste ; Isserlis est réactivé |
| 31 | modifier l'entrée après une chaîne | même effet que 30 |
| 32 | lhs = l'équation exacte avec T, rhs = `dM_A1_A1/dt` de moment_closure : **Compare**, puis **Isserlis** et **Compare** | Different, puis **Equal (proved)** |
| 33 | (suite) **Simplify** | s'applique à l'équation fermée ; titre *Isserlis (order 3) → Simplify* |
| 34 | **↑ Use as input** après une chaîne | le résultat va dans les champs, la chaîne est effacée |
| 35 | changer de mode après une chaîne | la chaîne est effacée |
