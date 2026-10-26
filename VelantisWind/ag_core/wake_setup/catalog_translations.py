# -*- coding: utf-8 -*-
"""Translations of the help texts of the wake catalogue (``catalog.py``): Spanish source to en, fr and de.

Registered as whole strings only (no fragments), so a help text is never rewritten piece by piece.
"""

_ES = (
    "Propaga las estelas aguas abajo, turbina a turbina. No admite bloqueo.",
    "Calcula la influencia de todas las turbinas sobre todas e itera hasta cumplir su tolerancia o agotar "
    "sus iteraciones. Admite bloqueo si se elige un modelo de bloqueo.",
    "Propaga las estelas aguas abajo y el bloqueo aguas arriba, e itera. Admite bloqueo y exige que el déficit y el "
    "bloqueo usen la velocidad efectiva (use_effective_ws).",
    "Déficit gaussiano de Bastankhah y Porté-Agel (2014), con expansión k constante.",
    "Modelo predefinido de PyWake: Bastankhah_PorteAgel_2014, que exige dar k y usa ct2a_mom1d y la velocidad efectiva.",
    "Déficit gaussiano con expansión que depende de la TI local, k = a₁·TI + a₂ (Niayifar y Porté-Agel, 2016).",
    "Modelo predefinido de PyWake: Niayifar_PorteAgel_2016, con a = [0,3837; 0,003678], ct2a_mom1d, velocidad "
    "efectiva, GaussianOverlapAvgModel y CrespoHernandez.",
    "CrespoHernandez",
    "Extensión de Niayifar con el crecimiento gradual del empuje y la anchura de estela de Shapiro (Zong y Porté-Agel, "
    "2020).",
    "Modelo predefinido de PyWake: Zong_PorteAgel_2020, con eps_coeff = 0,35, velocidad efectiva, WeightedSum y un "
    "CrespoHernandez propio (ct2a_mom1d, c = [0,73; 0,83; 0,03; −0,32]).",
    "CrespoHernandez (con sus propios ct2a y c)",
    "Versión con constantes medidas con lidar: ε empírico y nuevas constantes de expansión (Carbajo Fuertes et al., "
    "2018).",
    "Modelo predefinido de PyWake: CarbajoFuertes_etal_2018, con ct2a_mom1d, velocidad efectiva, "
    "GaussianOverlapAvgModel y CrespoHernandez.",

    "Déficit gaussiano TurbOPark (Nygaard, 2022): la expansión combina la TI ambiente y la generada por la propia estela.",
    "Modelo predefinido de PyWake: Nygaard_2022 (TurbOPark), con ct2a_mom1d, ctlim = 0,96, GaussianOverlapAvgModel, "
    "Mirror(SquaredSum()), SquaredSum y la velocidad libre de la turbina afectada (WS_jlk), que no está en la firma de "
    "la clase y no se puede elegir.",
    "Super-gaussiano: perfil de sombrero de copa cerca y gaussiano lejos (Blondel y Cathelain, 2020).",
    "Modelo predefinido de PyWake: Blondel_Cathelain_2020, con velocidad efectiva; en PyWake 2.6.18 no trae turbulencia "
    "y PyWake lo rechaza por eso; su propio ejemplo usa CrespoHernandez.",
    "CrespoHernandez (en el ejemplo de PyWake; el modelo predefinido no trae ninguna)",
    "Super-gaussiano con los parámetros calibrados de Blondel (2023).",
    "Bastankhah simplificado del caso de estudio IEA37 (equivale a Bastankhah con β = 1/√8).",
    "Modelo predefinido de PyWake: IEA37CaseStudy1, con All2All (sin comprobar la convergencia) y SquaredSum, en el "
    "sitio y las turbinas de ese caso.",
    "Modelo semianalítico de G. C. Larsen (2009), con estela de simetría rotacional.",
    "Modelos predefinidos de PyWake: GCL (LinearSum, sin rotor ni turbulencia) y GCLLocal (velocidad y TI efectivas).",
    "Jensen (NOJ): déficit de sombrero de copa con expansión lineal k.",
    "Modelo predefinido de PyWake: Jensen_1983, con SquaredSum.",
    "Como NOJ, pero con la velocidad y la TI locales; k depende de la TI como en Niayifar.",
    "Modelo predefinido de PyWake: NOJLocal, con LinearSum y STF2017TurbulenceModel.",
    "STF2017TurbulenceModel",
    "NOJ con la expansión de Nygaard (2020), proporcional a la TI local en la estela.",
    "Un único punto en el centro del rotor, como modelo explícito.",
    "Integración gaussiana circular con n puntos (4, 7, 9 o 21; 7 en su firma).",
    "Rejilla regular de n × n puntos dentro del rotor (n = 4).",
    "Solape exacto de la estela gaussiana con el rotor, leído de una tabla de PyWake (necesita h5py y h5netcdf).",
    "Fracción del área del rotor dentro de una estela de sombrero de copa.",
    "El suelo como espejo: añade turbinas imagen bajo el terreno.",
    "El suelo y un espejo en altura (por defecto a 1000 m); el número de turbinas imagen crece como "
    "2^(2 + max(0, n_reps)).",
    "Suma de los déficits.",
    "Raíz de la suma de los cuadrados (Katic et al., 1986).",
    "El mayor de los déficits.",
    "Suma ponderada que conserva el momento (Zong y Porté-Agel, 2020); iterativa.",
    "Estela acumulada (Bastankhah et al., 2021).",
    "Con CumulativeWakeSum, PyWake 2.6.18 da resultados que dependen del orden de las turbinas (comprobado con tres "
    "turbinas iguales); no está verificado.",
    "Frandsen, según la IEC 61400-1 de 2005.",
    "Frandsen, según la IEC 61400-1 de 2017.",
    "G. C. Larsen, según Pierik et al.",
    "Crespo y Hernández (1996).",
    "Autosemejanza de Troldborg y Meyer Forsting, versión revisada (2020).",
    "Autosemejanza de Troldborg y Meyer Forsting (2016).",
    "Cilindro semiinfinito de vorticidad tangencial (Branlard).",
    "Con PropagateUpDownIterative, este bloqueo de PyWake 2.6.18 calcula con la velocidad libre aunque "
    "use_effective_ws esté marcado: no escala con la velocidad efectiva que PropagateUpDownIterative exige; no está "
    "verificado.",
    "Dipolo de vórtice: más simple que el cilindro de vórtice y, según PyWake, muy parecido a él solo en campo "
    "lejano (r/R > 6).",
    "Combina una aproximación cerca del rotor y otra lejana, con un radio de cambio.",
    "Semicuerpo de Rankine con la fuente fijada por el momento 1-D.",
    "Aproximación de Rathmann (DTU, 2020) al cilindro de vórtice.",
    "Rathmann escalado con el Ct para compensar la expansión de la estela.",
    "Suma de los bloqueos.",
    "El mayor de los bloqueos.",
    "Raíz de la suma de los cuadrados; PyWake no la admite con aceleraciones (valores negativos).",
    "Los motores de PyWake llaman a la superposición del bloqueo con una única matriz y WeightedSum necesita más datos: PyWake "
    "se detiene al evaluar el bloqueo entre turbinas (con All2AllIterative, siempre; con PropagateUpDownIterative, "
    "desde la segunda turbina).",
    "Los motores de PyWake llaman a la superposición del bloqueo con una única matriz y CumulativeWakeSum necesita más datos: PyWake "
    "se detiene al evaluar el bloqueo entre turbinas (con All2AllIterative, siempre; con PropagateUpDownIterative, "
    "desde la segunda turbina).",
    "True: el déficit escala con la velocidad efectiva que llega a la turbina; False: con la velocidad libre. "
    "PropagateUpDownIterative exige True.",
    "True: el déficit usa la TI efectiva (ambiente más la añadida por las estelas) y exige un modelo de turbulencia; "
    "False: usa la TI ambiente.",
    "Relación entre el Ct y el factor de inducción axial: ct2a_madsen, ajuste para Ct altos (Madsen et al., 2020); "
    "ct2a_mom1d, teoría de momento 1-D (Ct = 4a(1 − a), con min(1, Ct)).",
    "{name} (PyWake). Valor de la firma: {value}.",
    "ctlim (PyWake). Valor de la firma: {value}. ZongGaussianDeficit lo guarda, pero PyWake 2.6.18 no lo usa en el "
    "cálculo: su ε es constante (eps_coeff).",
    "Fuera del menú: las clases que necesitan tablas que el complemento no aporta (FugaDeficit, FugaMultiLUTDeficit, "
    "FugaYawDeficit, RANSLUTDemoDeficit, RANSLUTDeficit, RANSLUTConvDeficit, XRLUTDeficitModel); NoWakeDeficit, porque "
    "el caso sin estelas ni bloqueo ya lo da el AEP bruto (el escenario de solo bloqueo queda fuera por alcance); y la "
    "deflexión de estela, porque el complemento no calcula el AEP con yaw.",
)

_EN = (
    "Propagates the wakes downstream, turbine by turbine. Does not support blockage.",
    "Computes the influence of every turbine on every other one and iterates until it meets its tolerance or "
    "exhausts its iterations. Supports blockage if a blockage model is chosen.",
    "Propagates the wakes downstream and the blockage upstream, and iterates. Supports blockage and requires the "
    "deficit and the blockage to use the effective wind speed (use_effective_ws).",
    "Gaussian deficit of Bastankhah and Porté-Agel (2014), with a constant expansion k.",
    "PyWake predefined model: Bastankhah_PorteAgel_2014, which requires k and uses ct2a_mom1d and the effective wind "
    "speed.",
    "Gaussian deficit whose expansion depends on the local TI, k = a₁·TI + a₂ (Niayifar and Porté-Agel, 2016).",
    "PyWake predefined model: Niayifar_PorteAgel_2016, with a = [0.3837; 0.003678], ct2a_mom1d, effective wind speed, "
    "GaussianOverlapAvgModel and CrespoHernandez.",
    "CrespoHernandez",
    "Extension of Niayifar with the gradual growth of the thrust and the wake width of Shapiro (Zong and Porté-Agel, "
    "2020).",
    "PyWake predefined model: Zong_PorteAgel_2020, with eps_coeff = 0.35, effective wind speed, WeightedSum and its own "
    "CrespoHernandez (ct2a_mom1d, c = [0.73; 0.83; 0.03; −0.32]).",
    "CrespoHernandez (with its own ct2a and c)",
    "Version with constants measured with lidar: empirical ε and new expansion constants (Carbajo Fuertes et al., "
    "2018).",
    "PyWake predefined model: CarbajoFuertes_etal_2018, with ct2a_mom1d, effective wind speed, GaussianOverlapAvgModel "
    "and CrespoHernandez.",

    "Gaussian TurbOPark deficit (Nygaard, 2022): the expansion combines ambient TI and TI generated by the wake itself.",
    "PyWake predefined model: Nygaard_2022 (TurbOPark), with ct2a_mom1d, ctlim = 0.96, GaussianOverlapAvgModel, "
    "Mirror(SquaredSum()), SquaredSum and the free wind speed of the affected turbine (WS_jlk), which is not in the "
    "class signature and cannot be chosen.",
    "Super-Gaussian: top-hat profile near the rotor and Gaussian far from it (Blondel and Cathelain, 2020).",
    "PyWake predefined model: Blondel_Cathelain_2020, with effective wind speed; in PyWake 2.6.18 it has no turbulence "
    "model and PyWake rejects it for that reason; its own example uses CrespoHernandez.",
    "CrespoHernandez (in the PyWake example; the predefined model has none)",
    "Super-Gaussian with the calibrated parameters of Blondel (2023).",
    "Simplified Bastankhah of the IEA37 case study (equivalent to Bastankhah with β = 1/√8).",
    "PyWake predefined model: IEA37CaseStudy1, with All2All (without convergence check) and SquaredSum, on the site and "
    "turbines of that case.",
    "Semi-analytical model of G. C. Larsen (2009), with a rotationally symmetric wake.",
    "PyWake predefined models: GCL (LinearSum, no rotor average nor turbulence) and GCLLocal (effective wind speed and "
    "TI).",
    "Jensen (NOJ): top-hat deficit with a linear expansion k.",
    "PyWake predefined model: Jensen_1983, with SquaredSum.",
    "Like NOJ, but with the local wind speed and TI; k depends on the TI as in Niayifar.",
    "PyWake predefined model: NOJLocal, with LinearSum and STF2017TurbulenceModel.",
    "STF2017TurbulenceModel",
    "NOJ with the expansion of Nygaard (2020), proportional to the local TI in the wake.",
    "A single point at the rotor centre, as an explicit model.",
    "Circular Gauss integration with n points (4, 7, 9 or 21; 7 in its signature).",
    "Regular grid of n × n points inside the rotor (n = 4).",
    "Exact overlap of the Gaussian wake with the rotor, read from a PyWake table (requires h5py and h5netcdf).",
    "Fraction of the rotor area inside a top-hat wake.",
    "The ground as a mirror: adds image turbines below the terrain.",
    "The ground and a mirror aloft (at 1000 m by default); the number of image turbines grows as "
    "2^(2 + max(0, n_reps)).",
    "Sum of the deficits.",
    "Square root of the sum of the squares (Katic et al., 1986).",
    "The largest of the deficits.",
    "Weighted sum that conserves momentum (Zong and Porté-Agel, 2020); iterative.",
    "Cumulative wake (Bastankhah et al., 2021).",
    "With CumulativeWakeSum, PyWake 2.6.18 gives results that depend on the order of the turbines (checked with three "
    "identical turbines); it is not verified.",
    "Frandsen, according to IEC 61400-1 of 2005.",
    "Frandsen, according to IEC 61400-1 of 2017.",
    "G. C. Larsen, according to Pierik et al.",
    "Crespo and Hernández (1996).",
    "Self-similarity of Troldborg and Meyer Forsting, revised version (2020).",
    "Self-similarity of Troldborg and Meyer Forsting (2016).",
    "Semi-infinite cylinder of tangential vorticity (Branlard).",
    "With PropagateUpDownIterative, this PyWake 2.6.18 blockage model computes with the free wind speed even when "
    "use_effective_ws is set: it does not scale with the effective wind speed PropagateUpDownIterative requires; it is "
    "not verified.",
    "Vortex dipole: simpler than the vortex cylinder and, according to PyWake, very similar to it only in the "
    "far field (r/R > 6).",
    "Combines a near-rotor approximation and a far-field one, with a switch radius.",
    "Rankine half body with the source set by 1-D momentum.",
    "Rathmann's approximation (DTU, 2020) to the vortex cylinder.",
    "Rathmann scaled with Ct to compensate for the wake expansion.",
    "Sum of the blockages.",
    "The largest of the blockages.",
    "Square root of the sum of the squares; PyWake does not accept it with speed-ups (negative values).",
    "The PyWake engines call the blockage superposition with a single array and WeightedSum needs more data: PyWake stops "
    "when it evaluates the blockage between turbines (with All2AllIterative, always; with PropagateUpDownIterative, "
    "from the second turbine).",
    "The PyWake engines call the blockage superposition with a single array and CumulativeWakeSum needs more data: PyWake stops "
    "when it evaluates the blockage between turbines (with All2AllIterative, always; with PropagateUpDownIterative, "
    "from the second turbine).",
    "True: the deficit scales with the effective wind speed reaching the turbine; False: with the free wind speed. "
    "PropagateUpDownIterative requires True.",
    "True: the deficit uses the effective TI (ambient plus the one added by the wakes) and requires a turbulence model; "
    "False: it uses the ambient TI.",
    "Relation between Ct and the axial induction factor: ct2a_madsen, fit for high Ct (Madsen et al., 2020); "
    "ct2a_mom1d, 1-D momentum theory (Ct = 4a(1 − a), with min(1, Ct)).",
    "{name} (PyWake). Signature value: {value}.",
    "ctlim (PyWake). Signature value: {value}. ZongGaussianDeficit keeps it, but PyWake 2.6.18 does not use it in the "
    "calculation: its ε is constant (eps_coeff).",
    "Not in the menu: the classes that need tables the plugin does not provide (FugaDeficit, FugaMultiLUTDeficit, "
    "FugaYawDeficit, RANSLUTDemoDeficit, RANSLUTDeficit, RANSLUTConvDeficit, XRLUTDeficitModel); NoWakeDeficit, because "
    "the gross AEP already gives the case without wakes and blockage (the blockage-only scenario is out of scope); and "
    "wake deflection, because the plugin does not compute the AEP with yaw.",
)

_FR = (
    "Propage les sillages vers l’aval, éolienne par éolienne. N’admet pas le blocage.",
    "Calcule l’influence de chaque éolienne sur toutes les autres et itère jusqu’à atteindre sa tolérance ou "
    "épuiser ses itérations. Admet le blocage si un modèle de blocage est choisi.",
    "Propage les sillages vers l’aval et le blocage vers l’amont, et itère. Admet le blocage et exige que le déficit "
    "et le blocage utilisent la vitesse effective (use_effective_ws).",
    "Déficit gaussien de Bastankhah et Porté-Agel (2014), avec une expansion k constante.",
    "Modèle prédéfini de PyWake : Bastankhah_PorteAgel_2014, qui exige k et utilise ct2a_mom1d et la vitesse effective.",
    "Déficit gaussien dont l’expansion dépend de la TI locale, k = a₁·TI + a₂ (Niayifar et Porté-Agel, 2016).",
    "Modèle prédéfini de PyWake : Niayifar_PorteAgel_2016, avec a = [0,3837 ; 0,003678], ct2a_mom1d, vitesse "
    "effective, GaussianOverlapAvgModel et CrespoHernandez.",
    "CrespoHernandez",
    "Extension de Niayifar avec la croissance progressive de la poussée et la largeur de sillage de Shapiro (Zong et "
    "Porté-Agel, 2020).",
    "Modèle prédéfini de PyWake : Zong_PorteAgel_2020, avec eps_coeff = 0,35, vitesse effective, WeightedSum et son "
    "propre CrespoHernandez (ct2a_mom1d, c = [0,73 ; 0,83 ; 0,03 ; −0,32]).",
    "CrespoHernandez (avec ses propres ct2a et c)",
    "Version avec des constantes mesurées par lidar : ε empirique et nouvelles constantes d’expansion (Carbajo Fuertes "
    "et al., 2018).",
    "Modèle prédéfini de PyWake : CarbajoFuertes_etal_2018, avec ct2a_mom1d, vitesse effective, "
    "GaussianOverlapAvgModel et CrespoHernandez.",

    "Déficit gaussien TurbOPark (Nygaard, 2022) : l’expansion combine la TI ambiante et celle générée par le sillage lui-même.",
    "Modèle prédéfini de PyWake : Nygaard_2022 (TurbOPark), avec ct2a_mom1d, ctlim = 0,96, GaussianOverlapAvgModel, "
    "Mirror(SquaredSum()), SquaredSum et la vitesse libre de l’éolienne affectée (WS_jlk), qui n’est pas dans la "
    "signature de la classe et ne peut pas être choisie.",
    "Super-gaussien : profil en chapeau haut-de-forme près du rotor et gaussien loin (Blondel et Cathelain, 2020).",
    "Modèle prédéfini de PyWake : Blondel_Cathelain_2020, avec vitesse effective ; dans PyWake 2.6.18 il n’a pas de "
    "modèle de turbulence et PyWake le rejette pour cette raison ; son propre exemple utilise CrespoHernandez.",
    "CrespoHernandez (dans l’exemple de PyWake ; le modèle prédéfini n’en a aucun)",
    "Super-gaussien avec les paramètres calibrés de Blondel (2023).",
    "Bastankhah simplifié du cas d’étude IEA37 (équivaut à Bastankhah avec β = 1/√8).",
    "Modèle prédéfini de PyWake : IEA37CaseStudy1, avec All2All (sans contrôle de convergence) et SquaredSum, sur le "
    "site et les éoliennes de ce cas.",
    "Modèle semi-analytique de G. C. Larsen (2009), avec un sillage à symétrie de révolution.",
    "Modèles prédéfinis de PyWake : GCL (LinearSum, sans moyenne sur le rotor ni turbulence) et GCLLocal (vitesse et TI effectives).",
    "Jensen (NOJ) : déficit en chapeau haut-de-forme avec une expansion linéaire k.",
    "Modèle prédéfini de PyWake : Jensen_1983, avec SquaredSum.",
    "Comme NOJ, mais avec la vitesse et la TI locales ; k dépend de la TI comme dans Niayifar.",
    "Modèle prédéfini de PyWake : NOJLocal, avec LinearSum et STF2017TurbulenceModel.",
    "STF2017TurbulenceModel",
    "NOJ avec l’expansion de Nygaard (2020), proportionnelle à la TI locale dans le sillage.",
    "Un seul point au centre du rotor, comme modèle explicite.",
    "Intégration gaussienne circulaire à n points (4, 7, 9 ou 21 ; 7 dans sa signature).",
    "Grille régulière de n × n points dans le rotor (n = 4).",
    "Recouvrement exact du sillage gaussien avec le rotor, lu dans une table de PyWake (nécessite h5py et h5netcdf).",
    "Fraction de la surface du rotor dans un sillage en chapeau haut-de-forme.",
    "Le sol comme miroir : ajoute des éoliennes images sous le terrain.",
    "Le sol et un miroir en altitude (à 1000 m par défaut) ; le nombre d’éoliennes images croît comme "
    "2^(2 + max(0, n_reps)).",
    "Somme des déficits.",
    "Racine de la somme des carrés (Katic et al., 1986).",
    "Le plus grand des déficits.",
    "Somme pondérée qui conserve la quantité de mouvement (Zong et Porté-Agel, 2020) ; itérative.",
    "Sillage cumulé (Bastankhah et al., 2021).",
    "Avec CumulativeWakeSum, PyWake 2.6.18 donne des résultats qui dépendent de l’ordre des éoliennes (vérifié avec "
    "trois éoliennes identiques) ; ce n’est pas vérifié.",
    "Frandsen, selon la CEI 61400-1 de 2005.",
    "Frandsen, selon la CEI 61400-1 de 2017.",
    "G. C. Larsen, selon Pierik et al.",
    "Crespo et Hernández (1996).",
    "Autosimilarité de Troldborg et Meyer Forsting, version révisée (2020).",
    "Autosimilarité de Troldborg et Meyer Forsting (2016).",
    "Cylindre semi-infini de vorticité tangentielle (Branlard).",
    "Avec PropagateUpDownIterative, ce modèle de blocage de PyWake 2.6.18 calcule avec la vitesse libre même si "
    "use_effective_ws est coché : il ne suit pas la vitesse effective qu’exige PropagateUpDownIterative ; ce n’est pas "
    "vérifié.",
    "Dipôle tourbillonnaire : plus simple que le cylindre tourbillonnaire et, selon PyWake, très proche de lui "
    "seulement en champ lointain (r/R > 6).",
    "Combine une approximation près du rotor et une autre lointaine, avec un rayon de bascule.",
    "Demi-corps de Rankine avec la source fixée par la quantité de mouvement 1-D.",
    "Approximation de Rathmann (DTU, 2020) du cylindre tourbillonnaire.",
    "Rathmann mis à l’échelle avec le Ct pour compenser l’expansion du sillage.",
    "Somme des blocages.",
    "Le plus grand des blocages.",
    "Racine de la somme des carrés ; PyWake ne l’admet pas avec des accélérations (valeurs négatives).",
    "Les moteurs de PyWake appellent la superposition du blocage avec un seul tableau et WeightedSum a besoin de plus de données : PyWake s’arrête quand il évalue le blocage entre éoliennes (avec All2AllIterative, toujours ; avec PropagateUpDownIterative, à partir de la deuxième éolienne).",
    "Les moteurs de PyWake appellent la superposition du blocage avec un seul tableau et CumulativeWakeSum a besoin de plus de données : PyWake s’arrête quand il évalue le blocage entre éoliennes (avec All2AllIterative, toujours ; avec PropagateUpDownIterative, à partir de la deuxième éolienne).",
    "True : le déficit suit la vitesse effective qui arrive à l’éolienne ; False : la vitesse libre. "
    "PropagateUpDownIterative exige True.",
    "True : le déficit utilise la TI effective (ambiante plus celle ajoutée par les sillages) et exige un modèle de "
    "turbulence ; False : il utilise la TI ambiante.",
    "Relation entre le Ct et le facteur d’induction axiale : ct2a_madsen, ajustement pour les Ct élevés (Madsen et al., "
    "2020) ; ct2a_mom1d, théorie de la quantité de mouvement 1-D (Ct = 4a(1 − a), avec min(1, Ct)).",
    "{name} (PyWake). Valeur de la signature : {value}.",
    "ctlim (PyWake). Valeur de la signature : {value}. ZongGaussianDeficit la conserve, mais PyWake 2.6.18 ne "
    "l’utilise pas dans le calcul : son ε est constant (eps_coeff).",
    "Hors du menu : les classes qui nécessitent des tables que l’extension ne fournit pas (FugaDeficit, "
    "FugaMultiLUTDeficit, FugaYawDeficit, RANSLUTDemoDeficit, RANSLUTDeficit, RANSLUTConvDeficit, XRLUTDeficitModel) ; "
    "NoWakeDeficit, car l’AEP brut donne déjà le cas sans sillages ni blocage (le scénario de blocage seul est hors "
    "champ) ; et la déviation de sillage, car l’extension ne calcule pas l’AEP avec lacet.",
)

_DE = (
    "Propagiert die Nachläufe stromabwärts, Windturbine für Windturbine. Unterstützt keine Blockade.",
    "Berechnet den Einfluss jeder Windturbine auf alle anderen und iteriert, bis die Toleranz erreicht oder die "
    "Iterationen erschöpft sind. Unterstützt Blockade, wenn ein Blockademodell gewählt wird.",
    "Propagiert die Nachläufe stromabwärts und die Blockade stromaufwärts und iteriert. Unterstützt Blockade und "
    "verlangt, dass Defizit und Blockade die effektive Windgeschwindigkeit verwenden (use_effective_ws).",
    "Gaußsches Defizit nach Bastankhah und Porté-Agel (2014), mit konstanter Aufweitung k.",
    "Vordefiniertes PyWake-Modell: Bastankhah_PorteAgel_2014, das k verlangt und ct2a_mom1d sowie die effektive "
    "Windgeschwindigkeit verwendet.",
    "Gaußsches Defizit, dessen Aufweitung von der lokalen TI abhängt, k = a₁·TI + a₂ (Niayifar und Porté-Agel, 2016).",
    "Vordefiniertes PyWake-Modell: Niayifar_PorteAgel_2016, mit a = [0,3837; 0,003678], ct2a_mom1d, effektiver "
    "Windgeschwindigkeit, GaussianOverlapAvgModel und CrespoHernandez.",
    "CrespoHernandez",
    "Erweiterung von Niayifar mit dem allmählichen Schubanstieg und der Nachlaufbreite nach Shapiro (Zong und "
    "Porté-Agel, 2020).",
    "Vordefiniertes PyWake-Modell: Zong_PorteAgel_2020, mit eps_coeff = 0,35, effektiver Windgeschwindigkeit, "
    "WeightedSum und einem eigenen CrespoHernandez (ct2a_mom1d, c = [0,73; 0,83; 0,03; −0,32]).",
    "CrespoHernandez (mit eigenem ct2a und c)",
    "Version mit per Lidar gemessenen Konstanten: empirisches ε und neue Aufweitungskonstanten (Carbajo Fuertes et al., "
    "2018).",
    "Vordefiniertes PyWake-Modell: CarbajoFuertes_etal_2018, mit ct2a_mom1d, effektiver Windgeschwindigkeit, "
    "GaussianOverlapAvgModel und CrespoHernandez.",

    "Gaußsches TurbOPark-Defizit (Nygaard, 2022): Die Aufweitung kombiniert die Umgebungs-TI und die vom Nachlauf selbst erzeugte TI.",
    "Vordefiniertes PyWake-Modell: Nygaard_2022 (TurbOPark), mit ct2a_mom1d, ctlim = 0,96, GaussianOverlapAvgModel, "
    "Mirror(SquaredSum()), SquaredSum und der freien Windgeschwindigkeit der betroffenen Windturbine (WS_jlk), die "
    "nicht in der Signatur der Klasse steht und nicht gewählt werden kann.",
    "Super-Gauß: Zylinderhutprofil nahe am Rotor und gaußförmig weiter entfernt (Blondel und Cathelain, 2020).",
    "Vordefiniertes PyWake-Modell: Blondel_Cathelain_2020, mit effektiver Windgeschwindigkeit; in PyWake 2.6.18 hat es "
    "kein Turbulenzmodell und PyWake lehnt es deshalb ab; sein eigenes Beispiel verwendet CrespoHernandez.",
    "CrespoHernandez (im PyWake-Beispiel; das vordefinierte Modell hat keines)",
    "Super-Gauß mit den kalibrierten Parametern von Blondel (2023).",
    "Vereinfachtes Bastankhah der IEA37-Fallstudie (entspricht Bastankhah mit β = 1/√8).",
    "Vordefiniertes PyWake-Modell: IEA37CaseStudy1, mit All2All (ohne Konvergenzprüfung) und SquaredSum, am Standort und "
    "mit den Windturbinen dieses Falls.",
    "Halbanalytisches Modell von G. C. Larsen (2009), mit rotationssymmetrischem Nachlauf.",
    "Vordefinierte PyWake-Modelle: GCL (LinearSum, ohne Rotormittelung und Turbulenz) und GCLLocal (effektive "
    "Windgeschwindigkeit und TI).",
    "Jensen (NOJ): Zylinderhut-Defizit mit linearer Aufweitung k.",
    "Vordefiniertes PyWake-Modell: Jensen_1983, mit SquaredSum.",
    "Wie NOJ, aber mit lokaler Windgeschwindigkeit und TI; k hängt wie bei Niayifar von der TI ab.",
    "Vordefiniertes PyWake-Modell: NOJLocal, mit LinearSum und STF2017TurbulenceModel.",
    "STF2017TurbulenceModel",
    "NOJ mit der Aufweitung nach Nygaard (2020), proportional zur lokalen TI im Nachlauf.",
    "Ein einziger Punkt im Rotormittelpunkt, als explizites Modell.",
    "Kreisförmige Gauß-Integration mit n Punkten (4, 7, 9 oder 21; 7 in ihrer Signatur).",
    "Regelmäßiges Gitter von n × n Punkten innerhalb des Rotors (n = 4).",
    "Exakte Überlappung des gaußschen Nachlaufs mit dem Rotor, aus einer PyWake-Tabelle gelesen (benötigt h5py und "
    "h5netcdf).",
    "Anteil der Rotorfläche innerhalb eines Zylinderhut-Nachlaufs.",
    "Der Boden als Spiegel: fügt Spiegel-Windturbinen unter dem Gelände hinzu.",
    "Der Boden und ein Spiegel in der Höhe (standardmäßig in 1000 m); die Zahl der Spiegel-Windturbinen wächst wie "
    "2^(2 + max(0, n_reps)).",
    "Summe der Defizite.",
    "Wurzel aus der Summe der Quadrate (Katic et al., 1986).",
    "Das größte der Defizite.",
    "Gewichtete Summe, die den Impuls erhält (Zong und Porté-Agel, 2020); iterativ.",
    "Kumulierter Nachlauf (Bastankhah et al., 2021).",
    "Mit CumulativeWakeSum liefert PyWake 2.6.18 Ergebnisse, die von der Reihenfolge der Windturbinen abhängen (geprüft "
    "mit drei gleichen Windturbinen); nicht verifiziert.",
    "Frandsen, nach IEC 61400-1 von 2005.",
    "Frandsen, nach IEC 61400-1 von 2017.",
    "G. C. Larsen, nach Pierik et al.",
    "Crespo und Hernández (1996).",
    "Selbstähnlichkeit nach Troldborg und Meyer Forsting, überarbeitete Fassung (2020).",
    "Selbstähnlichkeit nach Troldborg und Meyer Forsting (2016).",
    "Halbunendlicher Zylinder tangentialer Wirbelstärke (Branlard).",
    "Mit PropagateUpDownIterative rechnet dieses Blockademodell von PyWake 2.6.18 mit der freien Windgeschwindigkeit, "
    "auch wenn use_effective_ws gesetzt ist: es skaliert nicht mit der effektiven Windgeschwindigkeit, die "
    "PropagateUpDownIterative verlangt; nicht verifiziert.",
    "Wirbeldipol: einfacher als der Wirbelzylinder und laut PyWake ihm nur im Fernfeld sehr ähnlich (r/R > 6).",
    "Kombiniert eine Näherung nahe am Rotor und eine im Fernfeld, mit einem Umschaltradius.",
    "Rankine-Halbkörper mit der Quellstärke aus dem 1-D-Impuls.",
    "Näherung von Rathmann (DTU, 2020) an den Wirbelzylinder.",
    "Rathmann, mit dem Ct skaliert, um die Nachlaufaufweitung auszugleichen.",
    "Summe der Blockaden.",
    "Die größte der Blockaden.",
    "Wurzel aus der Summe der Quadrate; PyWake lässt sie bei Beschleunigungen (negativen Werten) nicht zu.",
    "Die PyWake-Rechenkerne rufen die Überlagerung der Blockade mit einem einzigen Array auf, und WeightedSum braucht mehr Daten: PyWake bricht ab, wenn es die Blockade zwischen Windturbinen auswertet (mit All2AllIterative immer; mit PropagateUpDownIterative ab der zweiten Windturbine).",
    "Die PyWake-Rechenkerne rufen die Überlagerung der Blockade mit einem einzigen Array auf, und CumulativeWakeSum braucht mehr Daten: PyWake bricht ab, wenn es die Blockade zwischen Windturbinen auswertet (mit All2AllIterative immer; mit PropagateUpDownIterative ab der zweiten Windturbine).",
    "True: das Defizit skaliert mit der effektiven Windgeschwindigkeit an der Windturbine; False: mit der freien "
    "Windgeschwindigkeit. PropagateUpDownIterative verlangt True.",
    "True: das Defizit verwendet die effektive TI (Umgebung plus die von den Nachläufen hinzugefügte) und verlangt ein "
    "Turbulenzmodell; False: es verwendet die Umgebungs-TI.",
    "Beziehung zwischen Ct und axialem Induktionsfaktor: ct2a_madsen, Anpassung für hohe Ct (Madsen et al., 2020); "
    "ct2a_mom1d, 1-D-Impulstheorie (Ct = 4a(1 − a), mit min(1, Ct)).",
    "{name} (PyWake). Wert der Signatur: {value}.",
    "ctlim (PyWake). Wert der Signatur: {value}. ZongGaussianDeficit speichert ihn, aber PyWake 2.6.18 verwendet "
    "ihn nicht in der Berechnung: sein ε ist konstant (eps_coeff).",
    "Nicht im Menü: die Klassen, die Tabellen benötigen, die das Plugin nicht mitbringt (FugaDeficit, FugaMultiLUTDeficit, FugaYawDeficit, RANSLUTDemoDeficit, RANSLUTDeficit, RANSLUTConvDeficit, XRLUTDeficitModel); NoWakeDeficit, weil die Brutto-AEP den Fall ohne Nachläufe und Blockade bereits liefert (das Szenario nur mit Blockade liegt außerhalb des Umfangs); und die Nachlaufablenkung, weil das Plugin die AEP nicht mit Gierwinkel berechnet.",
)

assert len(_ES) == len(_EN) == len(_FR) == len(_DE), "the four tables must have the same texts"
TRANSLATIONS = {lang: dict(zip(_ES, texts)) for lang, texts in (("en", _EN), ("fr", _FR), ("de", _DE))}


def register_catalog_translations():
    from ...i18n import register_language
    for language, mapping in TRANSLATIONS.items():
        register_language(language, mapping, {})
