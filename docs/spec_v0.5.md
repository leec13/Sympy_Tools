# Sympy_Tools — Spécification v0.5 : ω et r dans le modèle

*Validée avec l'utilisateur le 17/11/2026 (cas 46 à 53, Substitute complet en une fois). PDF : `v0.5_chaine.pdf` (cas 46 à 51) et `v0.5_recognize_omega.pdf` (cas 52). Implémentée dans la v0.5.0.*

## Idée
- ω_ik = s(x_k − θ_i)² est le **taux de mort par sélection**, un paramètre de l'événement *mort*.
- r_ik = rmax_i − ω_ik est le **taux de croissance net** : il apparaît quand naissance et mort se combinent.
- Les deux noms sont gardés, avec une seule source de vérité : le modèle.

## Changements
1. **Modèle par défaut** :
   - paramètres `omega_A1…` (LaTeX `\omega_A^{1}`, comme dans latex-preview) ;
   - définitions `omega_A1 = s*(x1 - thA)**2` et `r_A1 = rmaxA - omega_A1` ;
   - morts `mort_A1 = (omega_A1 + (NA1 + NA2)/KA)*NA1 | NA1-1`.
   - Les symétries échangent les ω, puisqu'elles sont déduites des définitions.
   - Un ancien modèle par défaut enregistré (v0.1 à v0.4) est remplacé au démarrage.
2. **Compare** remplace toujours les définitions avant de comparer : « Equal (proved, after substituting definitions) ».
3. **Recognize** : on remplace d'abord toutes les définitions, puis on cherche **l'écriture exacte la plus courte**. rmax peut rester avec son propre coefficient, mais il n'est jamais ajouté ni modifié. Sinon, le coefficient est laissé tel quel. Sans les ω, la règle redonne exactement les cas 22 à 25.
4. **Substitute** remplace complètement, en une seule fois, jusqu'aux paramètres de base (décision du 17/11/2026).

## Cas VALIDÉ
| # | Cas | Attendu |
|---|---|---|
| 46 | modèle par défaut | ω et r (r à partir de ω), morts avec ω, symétries valides, latex-preview lit le modèle |
| 47 | Generate `M_A1_A1` | mort A1 = ⟨N(1 − 2N)(ω_A¹ + (N_A¹+N_A²)/K_A)⟩ |
| 48 | Take moments | `m*(-2*M_A1_A1 + n_A1) + m*(2*M_A1_B1 + n_B1) + omega_A1*(-2*M_A1_A1 + n_A1) + rmaxA*(2*M_A1_A1 + n_A1) + (M_A1_A1 + M_A1_A2 - 2*T_A1_A1_A1 - 2*T_A1_A1_A2)/KA` |
| 49 | Isserlis, puis Compare avec moment_closure | Equal (proved, after substituting definitions) |
| 50 | Recognize sur 48 | −2m + 2r_A1 + 1/K_A devant ⟨(N_A¹)²⟩ ; m + ω_A1 + rmaxA devant ⟨N_A¹⟩ |
| 51 | Symmetry phenotypes sur 47 | ω_A² |
| 52 | Recognize sur les sorties de moment_closure | 22, 24, 25 inchangés ; 23 : m + rmaxA + ω_A1 |
| 53 | Substitute `r_A1*n_A1` | `n_A1*(rmaxA - s*(-thA + x1)**2)` |
