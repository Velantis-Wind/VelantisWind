# -*- coding: utf-8 -*-
"""Translations of the help texts of the arguments of the subordinate objects (``subordinates.py``, #64) and of the
controls that edit them: Spanish source to en, fr and de.

Registered as whole strings only. The quotations of PyWake («…») stay in its English in every language.
"""

_ROWS = (
    # (es, en, fr, de)
    ("PyWake (engineering_models.py:926-929): «if float: maximum accepted change in WS_eff_ilk [m/s]; if None: return "
     "after first iteration». Como mucho max(número de turbinas, 20) iteraciones. PyWake no da rango.",
     "PyWake (engineering_models.py:926-929): «if float: maximum accepted change in WS_eff_ilk [m/s]; if None: return "
     "after first iteration». At most max(number of turbines, 20) iterations. PyWake gives no range.",
     "PyWake (engineering_models.py:926-929) : « if float : maximum accepted change in WS_eff_ilk [m/s] ; if None : return after first iteration ». Au plus max(nombre de turbines, 20) itérations. PyWake ne donne pas de plage.",
     "PyWake (engineering_models.py:926-929): «if float: maximum accepted change in WS_eff_ilk [m/s]; if None: return after first iteration». Höchstens max(Anzahl der Windturbinen, 20) Iterationen. PyWake gibt keinen Bereich an."),
    ("PyWake no la documenta (engineering_models.py:515-535); corta si el cambio máximo es menor que ella. PyWake no da "
     "rango.",
     "PyWake does not document it (engineering_models.py:515-535); it stops when the largest change is below it. "
     "PyWake gives no range.",
     "PyWake ne la documente pas (engineering_models.py:515-535) ; il s’arrête quand le changement maximal lui est "
     "inférieur. PyWake ne donne pas de plage.",
     "PyWake dokumentiert sie nicht (engineering_models.py:515-535); es bricht ab, wenn die größte Änderung darunter "
     "liegt. PyWake gibt keinen Bereich an."),
    ("PyWake no lo documenta; se compara con un contador entero (engineering_models.py:589) y el bucle tiene como mucho "
     "tantas pasadas como turbinas (línea 559); ≤ 0 hace una pasada. PyWake no da rango.",
     "PyWake does not document it; it is compared with an integer counter (engineering_models.py:589) and the loop has "
     "at most as many passes as turbines (line 559); ≤ 0 makes one pass. PyWake gives no range.",
     "PyWake ne le documente pas ; il est comparé à un compteur entier (engineering_models.py:589) et la boucle a au plus autant de passes que d’éoliennes (ligne 559) ; ≤ 0 fait une passe. PyWake ne donne pas de plage.",
     "PyWake dokumentiert ihn nicht; er wird mit einem ganzzahligen Zähler verglichen (engineering_models.py:589), und die Schleife hat höchstens so viele Durchläufe wie Windturbinen (Zeile 559); ≤ 0 macht einen Durchlauf. PyWake gibt keinen Bereich an."),
    ("PyWake (rotor_avg_model.py:127-133): «Circular Gauss Integration … n : {4, 7, 9, 21} Number of points».",
     "PyWake (rotor_avg_model.py:127-133): «Circular Gauss Integration … n : {4, 7, 9, 21} Number of points».",
     "PyWake (rotor_avg_model.py:127-133) : «Circular Gauss Integration … n : {4, 7, 9, 21} Number of points».",
     "PyWake (rotor_avg_model.py:127-133): «Circular Gauss Integration … n : {4, 7, 9, 21} Number of points»."),
    ("PyWake no lo documenta: malla de n × n puntos, con los que caen dentro del rotor (rotor_avg_model.py:83-88); de −2 "
     "a 0 no hay nodos, y con −3 o menos no se construye. PyWake no da rango.",
     "PyWake does not document it: a grid of n × n points, those that fall inside the rotor (rotor_avg_model.py:83-88); "
     "from −2 to 0 there are no nodes, and with −3 or less it is not built. PyWake gives no range.",
     "PyWake ne le documente pas : grille de n × n points, ceux qui tombent dans le rotor (rotor_avg_model.py:83-88) ; "
     "de −2 à 0 il n’y a pas de nœuds, et avec −3 ou moins il n’est pas construit. PyWake ne donne pas de plage.",
     "PyWake dokumentiert ihn nicht: ein Gitter von n × n Punkten, die innerhalb des Rotors liegen "
     "(rotor_avg_model.py:83-88); von −2 bis 0 gibt es keine Knoten, und mit −3 oder weniger wird es nicht gebaut. "
     "PyWake gibt keinen Bereich an."),
    ("PyWake (ground_models.py:24-30): «Superposition model used to sum wakes from the above and below-ground turbine. "
     "If None, default, the superposition model used for the deficit model is applied».",
     "PyWake (ground_models.py:24-30): «Superposition model used to sum wakes from the above and below-ground turbine. "
     "If None, default, the superposition model used for the deficit model is applied».",
     "PyWake (ground_models.py:24-30) : «Superposition model used to sum wakes from the above and below-ground turbine. "
     "If None, default, the superposition model used for the deficit model is applied».",
     "PyWake (ground_models.py:24-30): «Superposition model used to sum wakes from the above and below-ground turbine. "
     "If None, default, the superposition model used for the deficit model is applied»."),
    ("PyWake (ground_models.py:64-75): «Considers the ground and a mirror aloft as a mirror by default … mirror_heigth : "
     "int or float, optional». PyWake no da rango.",
     "PyWake (ground_models.py:64-75): «Considers the ground and a mirror aloft as a mirror by default … mirror_heigth : "
     "int or float, optional». PyWake gives no range.",
     "PyWake (ground_models.py:64-75) : «Considers the ground and a mirror aloft as a mirror by default … mirror_heigth : "
     "int or float, optional». PyWake ne donne pas de plage.",
     "PyWake (ground_models.py:64-75): «Considers the ground and a mirror aloft as a mirror by default … mirror_heigth : "
     "int or float, optional». PyWake gibt keinen Bereich an."),
    ("PyWake (ground_models.py:64-76): «the user can set how many mirrors should be enforced (n_mirrors = 2 + n_reps). "
     "Be aware that the number of turbines grows quickly n_turbines = 2^(n_mirrors)». PyWake no da rango: un negativo "
     "no añade repeticiones, como 0 (ground_models.py:89-94); el control llega a −2147483647, el mínimo de su campo.",
     "PyWake (ground_models.py:64-76): «the user can set how many mirrors should be enforced (n_mirrors = 2 + n_reps). "
     "Be aware that the number of turbines grows quickly n_turbines = 2^(n_mirrors)». PyWake gives no range: a "
     "negative adds no repetitions, as 0 (ground_models.py:89-94); the control reaches −2147483647, the minimum of its "
     "field.",
     "PyWake (ground_models.py:64-76) : « the user can set how many mirrors should be enforced (n_mirrors = 2 + n_reps). Be aware that the number of turbines grows quickly n_turbines = 2^(n_mirrors) ». PyWake ne donne pas de plage : un négatif n’ajoute pas de répétitions, comme 0 (ground_models.py:89-94) ; le contrôle va jusqu’à −2147483647, le minimum de son champ.",
     "PyWake (ground_models.py:64-76): «the user can set how many mirrors should be enforced (n_mirrors = 2 + n_reps). "
     "Be aware that the number of turbines grows quickly n_turbines = 2^(n_mirrors)». PyWake gibt keinen Bereich an: "
     "ein negativer Wert fügt keine Wiederholungen hinzu, wie 0 (ground_models.py:89-94); das Feld reicht bis "
     "−2147483647, sein Minimum."),
    ("PyWake (ground_models.py:77-81): el mismo texto que en Mirror.",
     "PyWake (ground_models.py:77-81): the same text as in Mirror.",
     "PyWake (ground_models.py:77-81) : le même texte que dans Mirror.",
     "PyWake (ground_models.py:77-81): derselbe Text wie bei Mirror."),
    ("PyWake (superposition_models.py:83): «minimum deficit (as fraction of free-stream) to invoke weighted "
     "summation»; Zong y Porté-Agel, J. Fluid Mech. (2020) 889 A8. PyWake no da rango.",
     "PyWake (superposition_models.py:83): «minimum deficit (as fraction of free-stream) to invoke weighted "
     "summation»; Zong and Porté-Agel, J. Fluid Mech. (2020) 889 A8. PyWake gives no range.",
     "PyWake (superposition_models.py:83) : « minimum deficit (as fraction of free-stream) to invoke weighted summation » ; Zong et Porté-Agel, J. Fluid Mech. (2020) 889 A8. PyWake ne donne pas de plage.",
     "PyWake (superposition_models.py:83): «minimum deficit (as fraction of free-stream) to invoke weighted "
     "summation»; Zong und Porté-Agel, J. Fluid Mech. (2020) 889 A8. PyWake gibt keinen Bereich an."),
    ("PyWake (superposition_models.py:85): «convergence limit for computing global convection velocity». PyWake no da "
     "rango.",
     "PyWake (superposition_models.py:85): «convergence limit for computing global convection velocity». PyWake gives "
     "no range.",
     "PyWake (superposition_models.py:85) : « convergence limit for computing global convection velocity ». PyWake ne donne pas de plage.",
     "PyWake (superposition_models.py:85): «convergence limit for computing global convection velocity». PyWake gibt "
     "keinen Bereich an."),
    ("PyWake (superposition_models.py:87): «maximum number of iterations used in computing weights». PyWake no da "
     "rango.",
     "PyWake (superposition_models.py:87): «maximum number of iterations used in computing weights». PyWake gives no "
     "range.",
     "PyWake (superposition_models.py:87) : «maximum number of iterations used in computing weights». PyWake ne donne "
     "pas de plage.",
     "PyWake (superposition_models.py:87): «maximum number of iterations used in computing weights». PyWake gibt "
     "keinen Bereich an."),
    ("PyWake (superposition_models.py:89): «Limit weights to this value. A limit of 1.0 means not exceeding linear "
     "superposition». PyWake no da rango.",
     "PyWake (superposition_models.py:89): «Limit weights to this value. A limit of 1.0 means not exceeding linear "
     "superposition». PyWake gives no range.",
     "PyWake (superposition_models.py:89) : «Limit weights to this value. A limit of 1.0 means not exceeding linear "
     "superposition». PyWake ne donne pas de plage.",
     "PyWake (superposition_models.py:89): «Limit weights to this value. A limit of 1.0 means not exceeding linear "
     "superposition». PyWake gibt keinen Bereich an."),
    ("PyWake (superposition_models.py:216-217): «somewhat empirical factor to scale results to fit LES predictions … "
     "alpha in 8.3 (1 in eq 6.4 and 2 in eq 4.9)»; Bastankhah et al., J. Fluid Mech. (2021) 911 A53. PyWake no da "
     "rango.",
     "PyWake (superposition_models.py:216-217): «somewhat empirical factor to scale results to fit LES predictions … "
     "alpha in 8.3 (1 in eq 6.4 and 2 in eq 4.9)»; Bastankhah et al., J. Fluid Mech. (2021) 911 A53. PyWake gives no "
     "range.",
     "PyWake (superposition_models.py:216-217) : «somewhat empirical factor to scale results to fit LES predictions … "
     "alpha in 8.3 (1 in eq 6.4 and 2 in eq 4.9)» ; Bastankhah et al., J. Fluid Mech. (2021) 911 A53. PyWake ne donne "
     "pas de plage.",
     "PyWake (superposition_models.py:216-217): «somewhat empirical factor to scale results to fit LES predictions … "
     "alpha in 8.3 (1 in eq 6.4 and 2 in eq 4.9)»; Bastankhah et al., J. Fluid Mech. (2021) 911 A53. PyWake gibt "
     "keinen Bereich an."),
    ("PyWake (stf.py:72-73): «the maximal added TI is calculated as TI_add = 1/(1.5 + 0.8*d/sqrt(Ct))», según la IEC "
     "61400-1 de 2017. PyWake no da rango.",
     "PyWake (stf.py:72-73): «the maximal added TI is calculated as TI_add = 1/(1.5 + 0.8*d/sqrt(Ct))», after IEC "
     "61400-1 of 2017. PyWake gives no range.",
     "PyWake (stf.py:72-73) : « the maximal added TI is calculated as TI_add = 1/(1.5 + 0.8*d/sqrt(Ct)) », selon la CEI 61400-1 de 2017. PyWake ne donne pas de plage.",
     "PyWake (stf.py:72-73): «the maximal added TI is calculated as TI_add = 1/(1.5 + 0.8*d/sqrt(Ct))», nach IEC "
     "61400-1 von 2017. PyWake gibt keinen Bereich an."),
    ("Cómo se suma la turbulencia añadida a la ambiente (turbulence_model.py:47). PyWake no lo documenta.",
     "How the added turbulence is summed with the ambient one (turbulence_model.py:47). PyWake does not document it.",
     "Comment la turbulence ajoutée est sommée à la turbulence ambiante (turbulence_model.py:47). PyWake ne le documente "
     "pas.",
     "Wie die zusätzliche Turbulenz mit der Umgebungsturbulenz summiert wird (turbulence_model.py:47). PyWake "
     "dokumentiert es nicht."),
    ("PyWake (stf.py:12-17, 43-51): FrandsenWeight, el peso de la tesis de Frandsen (Eq. 3.16); IECWeight, el sector de "
     "21,6° de la IEC 61400-1 (anexos D de 2005 y E de 2017).",
     "PyWake (stf.py:12-17, 43-51): FrandsenWeight, the weight of Frandsen’s thesis (Eq. 3.16); IECWeight, the 21.6° "
     "sector of IEC 61400-1 (annexes D of 2005 and E of 2017).",
     "PyWake (stf.py:12-17, 43-51) : FrandsenWeight, le poids de la thèse de Frandsen (éq. 3.16) ; IECWeight, le secteur "
     "de 21,6° de la CEI 61400-1 (annexes D de 2005 et E de 2017).",
     "PyWake (stf.py:12-17, 43-51): FrandsenWeight, das Gewicht aus Frandsens Dissertation (Gl. 3.16); IECWeight, der "
     "21,6°-Sektor der IEC 61400-1 (Anhänge D von 2005 und E von 2017)."),
    ("Como en STF2017TurbulenceModel.", "As in STF2017TurbulenceModel.", "Comme dans STF2017TurbulenceModel.",
     "Wie bei STF2017TurbulenceModel."),
    ("Relación entre el Ct y la inducción axial: ct2a_madsen (Madsen et al., Wind Energ. Sci. 5, 2020) o ct2a_mom1d "
     "(momento 1-D, Ct = 4a(1 − a), con Ct menor que 1) (deficit_models/utils.py:6-18).",
     "Relation between Ct and the axial induction: ct2a_madsen (Madsen et al., Wind Energ. Sci. 5, 2020) or ct2a_mom1d "
     "(1-D momentum, Ct = 4a(1 − a), with Ct below 1) (deficit_models/utils.py:6-18).",
     "Relation entre le Ct et l’induction axiale : ct2a_madsen (Madsen et al., Wind Energ. Sci. 5, 2020) ou ct2a_mom1d "
     "(quantité de mouvement 1-D, Ct = 4a(1 − a), avec Ct inférieur à 1) (deficit_models/utils.py:6-18).",
     "Beziehung zwischen Ct und axialer Induktion: ct2a_madsen (Madsen et al., Wind Energ. Sci. 5, 2020) oder "
     "ct2a_mom1d (1-D-Impuls, Ct = 4a(1 − a), mit Ct unter 1) (deficit_models/utils.py:6-18)."),
    ("PyWake (crespo.py:42-44): «added turbulence (Eq. 21)», c[0]·a^c[1]·TI^c[2]·(dw/D)^c[3]; Crespo y Hernández, J. "
     "Wind Eng. Ind. Aerodyn. 61 (1996) 71-85. PyWake no da rango.",
     "PyWake (crespo.py:42-44): «added turbulence (Eq. 21)», c[0]·a^c[1]·TI^c[2]·(dw/D)^c[3]; Crespo and Hernández, J. "
     "Wind Eng. Ind. Aerodyn. 61 (1996) 71-85. PyWake gives no range.",
     "PyWake (crespo.py:42-44) : « added turbulence (Eq. 21) », c[0]·a^c[1]·TI^c[2]·(dw/D)^c[3] ; Crespo et Hernández, J. Wind Eng. Ind. Aerodyn. 61 (1996) 71-85. PyWake ne donne pas de plage.",
     "PyWake (crespo.py:42-44): «added turbulence (Eq. 21)», c[0]·a^c[1]·TI^c[2]·(dw/D)^c[3]; Crespo und Hernández, J. "
     "Wind Eng. Ind. Aerodyn. 61 (1996) 71-85. PyWake gibt keinen Bereich an."),
    ("PyWake no lo documenta: distancia, en diámetros, hasta la que se aplica el peso (stf.py:56). PyWake no da rango.",
     "PyWake does not document it: the distance, in diameters, up to which the weight applies (stf.py:56). PyWake gives "
     "no range.",
     "PyWake ne le documente pas : la distance, en diamètres, jusqu’à laquelle le poids s’applique (stf.py:56). PyWake "
     "ne donne pas de plage.",
     "PyWake dokumentiert ihn nicht: der Abstand in Durchmessern, bis zu dem das Gewicht gilt (stf.py:56). PyWake gibt "
     "keinen Bereich an."),
    ("Relación entre el Ct y la inducción axial (deficit_models/utils.py:6-18).",
     "Relation between Ct and the axial induction (deficit_models/utils.py:6-18).",
     "Relation entre le Ct et l’induction axiale (deficit_models/utils.py:6-18).",
     "Beziehung zwischen Ct und axialer Induktion (deficit_models/utils.py:6-18)."),
    ("PyWake: «limiter for singularities»; anula el bloqueo a menos de limiter·R del plano del rotor, aguas arriba y "
     "aguas abajo (la distancia va en valor absoluto, selfsimilarity.py:52, 84) y, con exclude_wake, delimita la zona "
     "de la estela (deficit_model.py:115). PyWake no da rango.",
     "PyWake: «limiter for singularities»; it cancels the blockage closer than limiter·R to the rotor plane, upstream "
     "and downstream (the distance is taken in absolute value, selfsimilarity.py:52, 84) and, with exclude_wake, it "
     "bounds the wake region (deficit_model.py:115). PyWake gives no range.",
     "PyWake : « limiter for singularities » ; il annule le blocage à moins de limiter·R du plan du rotor, en amont et en aval (la distance est prise en valeur absolue, selfsimilarity.py:52, 84) et, avec exclude_wake, il délimite la zone du sillage (deficit_model.py:115). PyWake ne donne pas de plage.",
     "PyWake: «limiter for singularities»; es hebt die Blockade näher als limiter·R an der Rotorebene auf, stromauf- "
     "und stromabwärts (der Abstand wird als Betrag genommen, selfsimilarity.py:52, 84), und mit exclude_wake begrenzt "
     "es den Nachlaufbereich (deficit_model.py:115). PyWake gibt keinen Bereich an."),
    ("PyWake: «if used in a wind farm simulation, set deficit in wake region to zero, as here the wake model is "
     "active» (VortexCylinder excluye por el radio del rotor, vortexcylinder.py:85-90).",
     "PyWake: «if used in a wind farm simulation, set deficit in wake region to zero, as here the wake model is "
     "active» (VortexCylinder excludes by the radius of the rotor, vortexcylinder.py:85-90).",
     "PyWake : «if used in a wind farm simulation, set deficit in wake region to zero, as here the wake model is "
     "active» (VortexCylinder exclut selon le rayon du rotor, vortexcylinder.py:85-90).",
     "PyWake: «if used in a wind farm simulation, set deficit in wake region to zero, as here the wake model is "
     "active» (VortexCylinder schließt nach dem Rotorradius aus, vortexcylinder.py:85-90)."),
    ("PyWake (deficit_model.py:92-93): «if true, downstream deficit from this model is set to zero».",
     "PyWake (deficit_model.py:92-93): «if true, downstream deficit from this model is set to zero».",
     "PyWake (deficit_model.py:92-93) : «if true, downstream deficit from this model is set to zero».",
     "PyWake (deficit_model.py:92-93): «if true, downstream deficit from this model is set to zero»."),
    ("PyWake: «limiter to avoid singularities»; regulariza el borde del cilindro (|ρ − 1| < limiter, "
     "vortexcylinder.py:47) y el plano del rotor (línea 56), también lejos del rotor, y delimita la zona excluida "
     "(línea 88). PyWake no da rango.",
     "PyWake: «limiter to avoid singularities»; it regularises the edge of the cylinder (|ρ − 1| < limiter, "
     "vortexcylinder.py:47) and the rotor plane (line 56), also far from the rotor, and bounds the excluded region "
     "(line 88). PyWake gives no range.",
     "PyWake : « limiter to avoid singularities » ; il régularise le bord du cylindre (|ρ − 1| < limiter, vortexcylinder.py:47) et le plan du rotor (ligne 56), aussi loin du rotor, et délimite la zone exclue (ligne 88). PyWake ne donne pas de plage.",
     "PyWake: «limiter to avoid singularities»; es regularisiert den Rand des Zylinders (|ρ − 1| < limiter, "
     "vortexcylinder.py:47) und die Rotorebene (Zeile 56), auch fern vom Rotor, und begrenzt den ausgeschlossenen "
     "Bereich (Zeile 88). PyWake gibt keinen Bereich an."),
    ("PyWake: «limiter to avoid singularities»; actúa con r/R < limiter (vortexdipole.py:53, 57) y, con exclude_wake, "
     "delimita la zona de la estela (deficit_model.py:115). PyWake no da rango.",
     "PyWake: «limiter to avoid singularities»; it acts with r/R < limiter (vortexdipole.py:53, 57) and, with "
     "exclude_wake, it bounds the wake region (deficit_model.py:115). PyWake gives no range.",
     "PyWake : « limiter to avoid singularities » ; il agit avec r/R < limiter (vortexdipole.py:53, 57) et, avec exclude_wake, il délimite la zone du sillage (deficit_model.py:115). PyWake ne donne pas de plage.",
     "PyWake: «limiter to avoid singularities»; es wirkt bei r/R < limiter (vortexdipole.py:53, 57), und mit "
     "exclude_wake begrenzt es den Nachlaufbereich (deficit_model.py:115). PyWake gibt keinen Bereich an."),
    ("PyWake: «limiter to avoid singularities»; anula el bloqueo con 2r/D < limiter (rankinehalfbody.py:70) y, con "
     "exclude_wake, delimita la zona de la estela (deficit_model.py:115). PyWake no da rango.",
     "PyWake: «limiter to avoid singularities»; it cancels the blockage with 2r/D < limiter (rankinehalfbody.py:70) "
     "and, with exclude_wake, it bounds the wake region (deficit_model.py:115). PyWake gives no range.",
     "PyWake : « limiter to avoid singularities » ; il annule le blocage avec 2r/D < limiter (rankinehalfbody.py:70) et, avec exclude_wake, il délimite la zone du sillage (deficit_model.py:115). PyWake ne donne pas de plage.",
     "PyWake: «limiter to avoid singularities»; es hebt die Blockade bei 2r/D < limiter auf (rankinehalfbody.py:70), "
     "und mit exclude_wake begrenzt es den Nachlaufbereich (deficit_model.py:115). PyWake gibt keinen Bereich an."),
    ("PyWake: «limiter to avoid singularities»; solo se usa con exclude_wake, para delimitar la zona de la estela "
     "(deficit_model.py:115). PyWake no da rango.",
     "PyWake: «limiter to avoid singularities»; it is used only with exclude_wake, to bound the wake region "
     "(deficit_model.py:115). PyWake gives no range.",
     "PyWake : « limiter to avoid singularities » ; il ne sert qu’avec exclude_wake, pour délimiter la zone du sillage (deficit_model.py:115). PyWake ne donne pas de plage.",
     "PyWake: «limiter to avoid singularities»; es wird nur mit exclude_wake verwendet, um den Nachlaufbereich zu "
     "begrenzen (deficit_model.py:115). PyWake gibt keinen Bereich an."),
    ("PyWake (hybridinduction.py:15-20): «Location at which to switch from near-rotor to far-field can be altered "
     "though by setting switch_radius»; campo lejano si r > R·switch_radius o aguas abajo. PyWake no da rango.",
     "PyWake (hybridinduction.py:15-20): «Location at which to switch from near-rotor to far-field can be altered "
     "though by setting switch_radius»; far field if r > R·switch_radius or downstream. PyWake gives no range.",
     "PyWake (hybridinduction.py:15-20) : «Location at which to switch from near-rotor to far-field can be altered "
     "though by setting switch_radius» ; champ lointain si r > R·switch_radius ou en aval. PyWake ne donne pas de "
     "plage.",
     "PyWake (hybridinduction.py:15-20): «Location at which to switch from near-rotor to far-field can be altered "
     "though by setting switch_radius»; Fernfeld, wenn r > R·switch_radius oder stromabwärts. PyWake gibt keinen "
     "Bereich an."),
    ("PyWake (selfsimilarity.py:21, 64-65): el Ct efectivo es gamma·Ct, Eq. (8) de Troldborg y Meyer Forsting (2016). "
     "PyWake no da rango.",
     "PyWake (selfsimilarity.py:21, 64-65): the effective Ct is gamma·Ct, Eq. (8) of Troldborg and Meyer Forsting "
     "(2016). PyWake gives no range.",
     "PyWake (selfsimilarity.py:21, 64-65) : le Ct effectif est gamma·Ct, éq. (8) de Troldborg et Meyer Forsting "
     "(2016). PyWake ne donne pas de plage.",
     "PyWake (selfsimilarity.py:21, 64-65): das effektive Ct ist gamma·Ct, Gl. (8) von Troldborg und Meyer Forsting "
     "(2016). PyWake gibt keinen Bereich an."),
    ("PyWake (selfsimilarity.py:36-38): r12 = √(ss_lambda·(ss_eta + x²)), Eq. (13) de [1]. PyWake no da rango.",
     "PyWake (selfsimilarity.py:36-38): r12 = √(ss_lambda·(ss_eta + x²)), Eq. (13) of [1]. PyWake gives no range.",
     "PyWake (selfsimilarity.py:36-38) : r12 = √(ss_lambda·(ss_eta + x²)), éq. (13) de [1]. PyWake ne donne pas de "
     "plage.",
     "PyWake (selfsimilarity.py:36-38): r12 = √(ss_lambda·(ss_eta + x²)), Gl. (13) von [1]. PyWake gibt keinen "
     "Bereich an."),
    ("PyWake (selfsimilarity.py:43-45, 132): forma radial, Eq. (6) de [1].",
     "PyWake (selfsimilarity.py:43-45, 132): radial shape, Eq. (6) of [1].",
     "PyWake (selfsimilarity.py:43-45, 132) : forme radiale, éq. (6) de [1].",
     "PyWake (selfsimilarity.py:43-45, 132): radiale Form, Gl. (6) von [1]."),
    ("PyWake (selfsimilarity.py:135, 147-151): «coefficients for the half width approximation», Eq. (13) de Meyer "
     "Forsting et al. (2023). PyWake no da rango.",
     "PyWake (selfsimilarity.py:135, 147-151): «coefficients for the half width approximation», Eq. (13) of Meyer "
     "Forsting et al. (2023). PyWake gives no range.",
     "PyWake (selfsimilarity.py:135, 147-151) : « coefficients for the half width approximation », éq. (13) de Meyer Forsting et al. (2023). PyWake ne donne pas de plage.",
     "PyWake (selfsimilarity.py:135, 147-151): «coefficients for the half width approximation», Gl. (13) von Meyer "
     "Forsting et al. (2023). PyWake gibt keinen Bereich an."),
    ("PyWake (selfsimilarity.py:137, 162-166): γ(Ct) en x/R = −1, Eq. (16) de [2]. PyWake no da rango.",
     "PyWake (selfsimilarity.py:137, 162-166): γ(Ct) at x/R = −1, Eq. (16) of [2]. PyWake gives no range.",
     "PyWake (selfsimilarity.py:137, 162-166) : γ(Ct) en x/R = −1, éq. (16) de [2]. PyWake ne donne pas de plage.",
     "PyWake (selfsimilarity.py:137, 162-166): γ(Ct) bei x/R = −1, Gl. (16) von [2]. PyWake gibt keinen Bereich an."),
    ("PyWake (selfsimilarity.py:155-158): γ(Ct) en x/R = −6, Eq. (17) de [2], fgp[0]·sin((Ct − fgp[1])/fgp[3]) + "
     "fgp[2]. PyWake no da rango.",
     "PyWake (selfsimilarity.py:155-158): γ(Ct) at x/R = −6, Eq. (17) of [2], fgp[0]·sin((Ct − fgp[1])/fgp[3]) + "
     "fgp[2]. PyWake gives no range.",
     "PyWake (selfsimilarity.py:155-158) : γ(Ct) en x/R = −6, éq. (17) de [2], fgp[0]·sin((Ct − fgp[1])/fgp[3]) + "
     "fgp[2]. PyWake ne donne pas de plage.",
     "PyWake (selfsimilarity.py:155-158): γ(Ct) bei x/R = −6, Gl. (17) von [2], fgp[0]·sin((Ct − fgp[1])/fgp[3]) + "
     "fgp[2]. PyWake gibt keinen Bereich an."),
    ("PyWake (vortexdipole.py:33, rathmann.py:34, 122): «coefficient for scaling the effective forcing». PyWake no da "
     "rango.",
     "PyWake (vortexdipole.py:33, rathmann.py:34, 122): «coefficient for scaling the effective forcing». PyWake gives "
     "no range.",
     "PyWake (vortexdipole.py:33, rathmann.py:34, 122) : «coefficient for scaling the effective forcing». PyWake ne "
     "donne pas de plage.",
     "PyWake (vortexdipole.py:33, rathmann.py:34, 122): «coefficient for scaling the effective forcing». PyWake gibt "
     "keinen Bereich an."),
    ("PyWake no lo documenta: cambia la intensidad y la posición de la fuente con a (rankinehalfbody.py:54-62); "
     "Gribben y Hawkes (2019).",
     "PyWake does not document it: it changes the strength and the position of the source with a "
     "(rankinehalfbody.py:54-62); Gribben and Hawkes (2019).",
     "PyWake ne le documente pas : il change l’intensité et la position de la source avec a "
     "(rankinehalfbody.py:54-62) ; Gribben et Hawkes (2019).",
     "PyWake dokumentiert ihn nicht: es ändert Stärke und Lage der Quelle mit a (rankinehalfbody.py:54-62); Gribben "
     "und Hawkes (2019)."),
    # --- the reasons of the arguments left out (EXCLUDED), shown in the group ---
    ("PyWake 2.6.18 no lo lee: STF2005 usa las constantes de la norma (stf.py:107-110).",
     "PyWake 2.6.18 does not read it: STF2005 uses the constants of the standard (stf.py:107-110).",
     "PyWake 2.6.18 ne le lit pas : STF2005 utilise les constantes de la norme (stf.py:107-110).",
     "PyWake 2.6.18 liest ihn nicht: STF2005 verwendet die Konstanten der Norm (stf.py:107-110)."),
    ("El motor no lo invoca: la turbulencia solo se envuelve con su promedio de rotor (turbulence_model.py:26-30).",
     "The engine does not call it: the turbulence is only wrapped with its rotor average (turbulence_model.py:26-30).",
     "Le moteur ne l’appelle pas : la turbulence n’est enveloppée que par sa moyenne sur le rotor "
     "(turbulence_model.py:26-30).",
     "Der Rechenkern ruft es nicht auf: die Turbulenz wird nur mit ihrer Rotormittelung umhüllt "
     "(turbulence_model.py:26-30)."),
    ("Es la tabla de PyWake; el complemento no aporta otras.",
     "It is the table of PyWake; the plugin provides no others.",
     "C’est la table de PyWake ; l’extension n’en fournit pas d’autres.",
     "Es ist die Tabelle von PyWake; das Plugin liefert keine anderen."),
    ("Todavía no se ofrece: PyWake calcula con él, aunque lo llama sin algunos de sus envoltorios "
     "(hybridinduction.py:49-54); su clase y sus coeficientes cambian el cálculo.",
     "Not offered yet: PyWake calculates with it, although it calls it without some of its wrappers "
     "(hybridinduction.py:49-54); its class and its coefficients change the calculation.",
     "Pas encore proposé : PyWake calcule avec lui, bien qu’il l’appelle sans certaines de ses enveloppes "
     "(hybridinduction.py:49-54) ; sa classe et ses coefficients changent le calcul.",
     "Noch nicht angeboten: PyWake rechnet damit, ruft es aber ohne einige seiner Hüllen auf "
     "(hybridinduction.py:49-54); seine Klasse und seine Koeffizienten ändern die Berechnung."),
    ("Todavía no se ofrece: como near_rotor.", "Not offered yet: as near_rotor.", "Pas encore proposé : comme near_rotor.",
     "Noch nicht angeboten: wie near_rotor."),
    ("Pide otro parque con su modelo, que el complemento no aporta.",
     "It asks for another wind farm with its model, which the plugin does not provide.",
     "Il demande un autre parc avec son modèle, que l’extension ne fournit pas.",
     "Es verlangt einen anderen Windpark mit seinem Modell, den das Plugin nicht liefert."),
    # --- the controls (ui_core/wake_controls.py, ui_core/wake_group.py) ---
    ("Comprobar convergencia", "Check convergence", "Vérifier la convergence", "Konvergenz prüfen"),
    ("Una iteración (None)", "One iteration (None)", "Une itération (None)", "Eine Iteration (None)"),
    ("Parámetros del modelo de suelo…", "Parameters of the ground model…", "Paramètres du modèle de sol…",
     "Parameter des Bodenmodells…"),
    ("Parámetros del modelo de suelo", "Parameters of the ground model", "Paramètres du modèle de sol",
     "Parameter des Bodenmodells"),
    ("Heredar", "Inherit", "Hériter", "Erben"),
    ("Aceptar", "OK", "OK", "OK"),
    ("Cancelar", "Cancel", "Annuler", "Abbrechen"),
    ("Restablecer", "Reset", "Réinitialiser", "Zurücksetzen"),
)

SOURCES = tuple(r[0] for r in _ROWS)
TRANSLATIONS = {lang: {r[0]: r[i] for r in _ROWS} for i, lang in ((1, "en"), (2, "fr"), (3, "de"))}


def register_subordinates_translations():
    from ...i18n import register_language
    for language, mapping in TRANSLATIONS.items():
        register_language(language, mapping, {})
