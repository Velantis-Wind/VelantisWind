# -*- coding: utf-8 -*-
"""Translations of the messages of the wake validation, the factory and the class check (Spanish templates).

The data of a template (class names, arguments, values) are not translated. Registered as whole strings only.
"""

_ROWS = (
    ('Marca use_effective_ws en los parámetros del bloqueo.',
     "Set use_effective_ws in the blockage parameters.",
     "Cochez use_effective_ws dans les paramètres du blocage.",
     "Setzen Sie use_effective_ws in den Parametern der Blockade."),
    # (es, en, fr, de)
    ("{cls} no admite el argumento «{arg}».",
     "{cls} does not accept the argument «{arg}».",
     "{cls} n’admet pas l’argument « {arg} ».",
     "{cls} akzeptiert das Argument «{arg}» nicht."),
    ("Falta el argumento «{arg}» de {cls}.",
     "The argument «{arg}» of {cls} is missing.",
     "L’argument « {arg} » de {cls} manque.",
     "Das Argument «{arg}» von {cls} fehlt."),
    ("Valor no válido para «{arg}» de {cls}: {value!r}.",
     "Invalid value for «{arg}» of {cls}: {value!r}.",
     "Valeur non valide pour « {arg} » de {cls} : {value!r}.",
     "Ungültiger Wert für «{arg}» von {cls}: {value!r}."),
    ("{option} no es una opción de {position}.",
     "{option} is not an option of {position}.",
     "{option} n’est pas une option de {position}.",
     "{option} ist keine Option für {position}."),
    ("{option} no es una opción de «{arg}» de {cls}.",
     "{option} is not an option of «{arg}» of {cls}.",
     "{option} n’est pas une option de « {arg} » de {cls}.",
     "{option} ist keine Option für «{arg}» von {cls}."),
    ("La instalación de PyWake no tiene la clase {cls}.",
     "The installed PyWake does not have the class {cls}.",
     "L’installation de PyWake n’a pas la classe {cls}.",
     "Die PyWake-Installation hat die Klasse {cls} nicht."),
    ("La superposición del bloqueo se indica si y solo si hay bloqueo.",
     "The blockage superposition is given if and only if there is a blockage model.",
     "La superposition du blocage est indiquée si et seulement s’il y a un modèle de blocage.",
     "Die Überlagerung der Blockade wird genau dann angegeben, wenn es ein Blockademodell gibt."),
    ("PropagateDownwind no admite bloqueo.",
     "PropagateDownwind does not support blockage.",
     "PropagateDownwind n’admet pas le blocage.",
     "PropagateDownwind unterstützt keine Blockade."),
    ("{deficit} usa la TI efectiva (use_effective_ti = True) y PyWake exige un modelo de turbulencia.",
     "{deficit} uses the effective TI (use_effective_ti = True) and PyWake requires a turbulence model.",
     "{deficit} utilise la TI effective (use_effective_ti = True) et PyWake exige un modèle de turbulence.",
     "{deficit} verwendet die effektive TI (use_effective_ti = True), und PyWake verlangt ein Turbulenzmodell."),
    ("Elige una turbulencia (el modelo predefinido de PyWake usa {turb}) o desmarca use_effective_ti.",
     "Choose a turbulence model (the PyWake predefined model uses {turb}) or clear use_effective_ti.",
     "Choisissez un modèle de turbulence (le modèle prédéfini de PyWake utilise {turb}) ou décochez use_effective_ti.",
     "Wählen Sie ein Turbulenzmodell (das vordefinierte PyWake-Modell verwendet {turb}) oder deaktivieren Sie use_effective_ti."),
    ("Elige una turbulencia o desmarca use_effective_ti.",
     "Choose a turbulence model or clear use_effective_ti.",
     "Choisissez un modèle de turbulence ou décochez use_effective_ti.",
     "Wählen Sie ein Turbulenzmodell oder deaktivieren Sie use_effective_ti."),
    ("PropagateUpDownIterative exige un déficit que escale con la velocidad efectiva.",
     "PropagateUpDownIterative requires a deficit that scales with the effective wind speed.",
     "PropagateUpDownIterative exige un déficit qui suit la vitesse effective.",
     "PropagateUpDownIterative verlangt ein Defizit, das mit der effektiven Windgeschwindigkeit skaliert."),
    ("Marca use_effective_ws en los parámetros del déficit.",
     "Set use_effective_ws in the deficit parameters.",
     "Cochez use_effective_ws dans les paramètres du déficit.",
     "Setzen Sie use_effective_ws in den Parametern des Defizits."),
    ("{deficit} no tiene use_effective_ws: elige otro motor u otra clase.",
     "{deficit} has no use_effective_ws: choose another engine or another class.",
     "{deficit} n’a pas use_effective_ws : choisissez un autre moteur ou une autre classe.",
     "{deficit} hat kein use_effective_ws: wählen Sie einen anderen Rechenkern oder eine andere Klasse."),
    ("PropagateUpDownIterative exige un bloqueo que escale con la velocidad efectiva.",
     "PropagateUpDownIterative requires a blockage model that scales with the effective wind speed.",
     "PropagateUpDownIterative exige un modèle de blocage qui suit la vitesse effective.",
     "PropagateUpDownIterative verlangt ein Blockademodell, das mit der effektiven Windgeschwindigkeit skaliert."),
    ("PropagateUpDownIterative no admite SquaredSum en un bloqueo con efecto aguas arriba y abajo.",
     "PropagateUpDownIterative does not accept SquaredSum for a blockage model acting upstream and downstream.",
     "PropagateUpDownIterative n’admet pas SquaredSum pour un blocage agissant vers l’amont et vers l’aval.",
     "PropagateUpDownIterative akzeptiert SquaredSum nicht für eine Blockade mit Wirkung stromauf- und stromabwärts."),
    ("Elige LinearSum o MaxSum para el bloqueo.",
     "Choose LinearSum or MaxSum for the blockage.",
     "Choisissez LinearSum ou MaxSum pour le blocage.",
     "Wählen Sie LinearSum oder MaxSum für die Blockade."),
    ("{bsup} no se puede usar como superposición del bloqueo: los motores de PyWake la llaman con un único array y "
     "{bsup} necesita más datos.",
     "{bsup} cannot be used as blockage superposition: the PyWake engines call it with a single array and {bsup} "
     "needs more data.",
     "{bsup} ne peut pas servir de superposition du blocage : les moteurs de PyWake l’appellent avec un seul tableau et "
     "{bsup} a besoin de plus de données.",
     "{bsup} kann nicht als Überlagerung der Blockade verwendet werden: die PyWake-Modelle rufen sie mit einem einzigen Array auf, und {bsup} braucht mehr Daten."),
    ("{field}: los nombres de los argumentos tienen que ser textos.",
     "{field}: the names of the arguments must be texts.",
     "{field} : les noms des arguments doivent être des textes.",
     "{field}: die Namen der Argumente müssen Texte sein."),
    ("Elige LinearSum para el bloqueo.",
     "Choose LinearSum for the blockage.",
     "Choisissez LinearSum pour le blocage.",
     "Wählen Sie LinearSum für die Blockade."),
    ("Elige LinearSum o MaxSum.", "Choose LinearSum or MaxSum.", "Choisissez LinearSum ou MaxSum.",
     "Wählen Sie LinearSum oder MaxSum."),
    ("Elige LinearSum.", "Choose LinearSum.", "Choisissez LinearSum.", "Wählen Sie LinearSum."),
    ("{sup} exige un déficit de convección (ConvectionDeficitModel); {deficit} no lo es.",
     "{sup} requires a convection deficit (ConvectionDeficitModel); {deficit} is not one.",
     "{sup} exige un déficit de convection (ConvectionDeficitModel) ; {deficit} n’en est pas un.",
     "{sup} verlangt ein Konvektionsdefizit (ConvectionDeficitModel); {deficit} ist keines."),
    ("WeightedSum no está implementado en PyWake para los déficits NOJ.",
     "WeightedSum is not implemented in PyWake for the NOJ deficits.",
     "WeightedSum n’est pas implémenté dans PyWake pour les déficits NOJ.",
     "WeightedSum ist in PyWake für die NOJ-Defizite nicht implementiert."),
    ("WeightedSum no admite modelo de suelo.",
     "WeightedSum does not accept a ground model.",
     "WeightedSum n’admet pas de modèle de sol.",
     "WeightedSum akzeptiert kein Bodenmodell."),
    ("CumulativeWakeSum no funciona en PyWake con los déficits NOJ.",
     "CumulativeWakeSum does not work in PyWake with the NOJ deficits.",
     "CumulativeWakeSum ne fonctionne pas dans PyWake avec les déficits NOJ.",
     "CumulativeWakeSum funktioniert in PyWake nicht mit den NOJ-Defiziten."),
    ("CumulativeWakeSum con All2AllIterative no admite un suelo que herede su superposición.",
     "CumulativeWakeSum with All2AllIterative does not support a ground that inherits its superposition.",
     "CumulativeWakeSum avec All2AllIterative n’admet pas un sol qui hérite de sa superposition.",
     "CumulativeWakeSum mit All2AllIterative unterstützt keinen Boden, der seine Superposition erbt."),
    ("En el bloqueo, MultiMirror sin superposición propia no funciona en PyWake con un promedio de rotor.",
     "In the blockage, MultiMirror without a superposition of its own does not work in PyWake with a rotor average.",
     "Dans le blocage, MultiMirror sans superposition propre ne fonctionne pas dans PyWake avec une moyenne sur le "
     "rotor.",
     "In der Blockade funktioniert MultiMirror ohne eigene Überlagerung in PyWake nicht mit einem Rotormittelwert."),
    ("En «{where}{path}», con limiter = 0, VortexDipole solo excluye el centro del rotor dentro de la estela del "
     "déficit (exclude_wake): donde su radio de estela no es positivo, PyWake {version} da NaN en la propia turbina.",
     "In «{where}{path}», with limiter = 0, VortexDipole only excludes the centre of the rotor inside the wake of the "
     "deficit (exclude_wake): where its wake radius is not positive, PyWake {version} gives NaN at the turbine itself.",
     "Dans « {where}{path} », avec limiter = 0, VortexDipole n’exclut le centre du rotor qu’à l’intérieur du sillage du déficit (exclude_wake) : là où son rayon de sillage n’est pas positif, PyWake {version} donne NaN sur l’éolienne elle-même.",
     "In «{where}{path}» schließt VortexDipole mit limiter = 0 die Rotormitte nur innerhalb des Nachlaufs des Defizits aus (exclude_wake): wo dessen Nachlaufradius nicht positiv ist, liefert PyWake {version} NaN an der Windturbine selbst."),
    ("En «{where}{path}», con limiter = {value}, VortexDipole no regulariza el centro del rotor: PyWake {version} da "
     "NaN en cualquier punto que caiga en el centro de una turbina (en el ráster, una celda sobre una turbina).",
     "In «{where}{path}», with limiter = {value}, VortexDipole does not regularise the centre of the rotor: PyWake "
     "{version} gives NaN at any point that falls on the centre of a turbine (in the raster, a cell on a turbine).",
     "Dans « {where}{path} », avec limiter = {value}, VortexDipole ne régularise pas le centre du rotor : PyWake {version} donne NaN en tout point qui tombe au centre d’une éolienne (dans le raster, une cellule sur une éolienne).",
     "In «{where}{path}» regularisiert VortexDipole mit limiter = {value} die Rotormitte nicht: PyWake {version} liefert NaN an jedem Punkt, der auf die Mitte einer Windturbine fällt (im Raster eine Zelle auf einer Windturbine)."),
    ("EqGridRotorAvg con n = {value} en «{where} · {arg}»: PyWake no lo construye (np.linspace con n + 2 < 0); el mínimo "
     "es −2.",
     "EqGridRotorAvg with n = {value} in «{where} · {arg}»: PyWake does not build it (np.linspace with n + 2 < 0); the "
     "minimum is −2.",
     "EqGridRotorAvg avec n = {value} dans « {where} · {arg} » : PyWake ne le construit pas (np.linspace avec n + 2 < 0) ; "
     "le minimum est −2.",
     "EqGridRotorAvg mit n = {value} in «{where} · {arg}»: PyWake baut es nicht (np.linspace mit n + 2 < 0); das Minimum "
     "ist −2."),
    ("Usa n ≥ −2.", "Use n ≥ −2.", "Utilisez n ≥ −2.", "Verwenden Sie n ≥ −2."),
    ("PyWake {version} falla al calcular con PropagateUpDownIterative, {sup} y MaxSum como superposición del bloqueo: "
     "desde la segunda turbina busca el máximo de una lista vacía de contribuciones del bloqueo.",
     "PyWake {version} fails when calculating with PropagateUpDownIterative, {sup} and MaxSum as the blockage "
     "superposition: from the second turbine on it looks for the maximum of an empty list of blockage contributions.",
     "PyWake {version} échoue en calculant avec PropagateUpDownIterative, {sup} et MaxSum comme superposition du blocage : dès la deuxième éolienne, il cherche le maximum d’une liste vide de contributions du blocage.",
     "PyWake {version} scheitert bei der Berechnung mit PropagateUpDownIterative, {sup} und MaxSum als Überlagerung der Blockade: ab der zweiten Windturbine sucht es das Maximum einer leeren Liste von Blockadebeiträgen."),
    ("Por esta causa, con {engine}, PyWake {version} se detiene desde la segunda turbina.",
     "For this cause, with {engine}, PyWake {version} stops from the second turbine.",
     "Pour cette cause, avec {engine}, PyWake {version} s’arrête dès la deuxième éolienne.",
     "Aus diesem Grund bricht PyWake {version} mit {engine} ab der zweiten Windturbine ab."),
    ("Por esta causa, con {engine}, PyWake {version} se detiene desde la tercera turbina.",
     "For this cause, with {engine}, PyWake {version} stops from the third turbine.",
     "Pour cette cause, avec {engine}, PyWake {version} s’arrête dès la troisième éolienne.",
     "Aus diesem Grund bricht PyWake {version} mit {engine} ab der dritten Windturbine ab."),
    ("Por esta causa, el mapa del ráster no se calcula, ni con una sola turbina.",
     "For this cause, the map of the raster is not calculated, not even with a single turbine.",
     "Pour cette cause, la carte du raster n’est pas calculée, même avec une seule éolienne.",
     "Aus diesem Grund wird die Karte des Rasters nicht berechnet, auch nicht mit einer einzigen Windturbine."),
    ("Por esta causa, el mapa del ráster no se calcula desde la segunda turbina.",
     "For this cause, the map of the raster is not calculated from the second turbine.",
     "Pour cette cause, la carte du raster n’est pas calculée dès la deuxième éolienne.",
     "Aus diesem Grund wird die Karte des Rasters ab der zweiten Windturbine nicht berechnet."),
    ("En «{where} · {arg}», con None, PyWake {version} se detiene al usar ese argumento.",
     "In «{where} · {arg}», with None, PyWake {version} stops when it uses that argument.",
     "Dans « {where} · {arg} », avec None, PyWake {version} s’arrête en utilisant cet argument.",
     "In «{where} · {arg}» bricht PyWake {version} mit None ab, wenn es dieses Argument verwendet."),
    ("Indica un valor.", "Enter a value.", "Indiquez une valeur.", "Geben Sie einen Wert an."),
    ("En «{where} · {arg}», la lista tiene {count} elementos y PyWake {version} usa {length}: se detiene al leerla.",
     "In «{where} · {arg}», the list has {count} elements and PyWake {version} uses {length}: it stops when reading "
     "it.",
     "Dans « {where} · {arg} », la liste a {count} éléments et PyWake {version} en utilise {length} : il s’arrête en "
     "la lisant.",
     "In «{where} · {arg}» hat die Liste {count} Elemente, und PyWake {version} verwendet {length}: es bricht beim "
     "Lesen ab."),
    ("Da a la lista sus {length} elementos.", "Give the list its {length} elements.",
     "Donnez à la liste ses {length} éléments.", "Geben Sie der Liste ihre {length} Elemente."),
    ("{rotor} como promedio de rotor de {owner} no funciona en PyWake {version}: se detiene al evaluarlo entre turbinas.",
     "{rotor} as the rotor average of {owner} does not work in PyWake {version}: it stops when evaluating it between "
     "turbines.",
     "{rotor} comme moyenne sur le rotor de {owner} ne fonctionne pas dans PyWake {version} : il s’arrête en l’évaluant entre éoliennes.",
     "{rotor} als Rotormittelung von {owner} funktioniert in PyWake {version} nicht: es bricht bei der Auswertung zwischen Windturbinen ab."),
    ("{sum} como superposición propia del suelo de «{where}» no funciona en PyWake {version}: el suelo la llama con un "
     "único array.",
     "{sum} as the own superposition of the ground of «{where}» does not work in PyWake {version}: the ground calls "
     "it with a single array.",
     "{sum} comme superposition propre du sol de « {where} » ne fonctionne pas dans PyWake {version} : le sol "
     "l’appelle avec un seul tableau.",
     "{sum} als eigene Überlagerung des Bodens von «{where}» funktioniert in PyWake {version} nicht: der Boden ruft "
     "sie mit einem einzigen Array auf."),
    ("El complemento no ofrece «{arg}» de {cls}: {reason}",
     "The plugin does not offer «{arg}» of {cls}: {reason}",
     "L’extension ne propose pas « {arg} » de {cls} : {reason}",
     "Das Plugin bietet «{arg}» von {cls} nicht an: {reason}"),
    ("En «{where}{path}», {arg} tiene {count} elementos: PyWake {version} solo lee los {length} primeros; los demás se "
     "conservan sin efecto.",
     "In «{where}{path}», {arg} has {count} elements: PyWake {version} only reads the first {length}; the others are "
     "kept without effect.",
     "Dans « {where}{path} », {arg} a {count} éléments : PyWake {version} ne lit que les {length} premiers ; les "
     "autres sont conservés sans effet.",
     "In «{where}{path}» hat {arg} {count} Elemente: PyWake {version} liest nur die ersten {length}; die übrigen "
     "bleiben ohne Wirkung erhalten."),
    ("En «{where}{path}», con All2AllIterative y un promedio de rotor del bloqueo con un nodo en el centro, ese centro es "
     "el de la propia turbina: PyWake {version} da NaN en las velocidades y en el AEP.",
     "In «{where}{path}», with All2AllIterative and a rotor average of the blockage with a node at the centre, that centre "
     "is the one of the turbine itself: PyWake {version} gives NaN in the wind speeds and in the AEP.",
     "Dans « {where}{path} », avec All2AllIterative et une moyenne sur le rotor du blocage avec un nœud au centre, ce centre est celui de l’éolienne elle-même : PyWake {version} donne NaN dans les vitesses et dans l’AEP.",
     "In «{where}{path}» ist mit All2AllIterative und einer Rotormittelung der Blockade mit einem Knoten in der Mitte "
     "diese Mitte die der Turbine selbst: PyWake {version} liefert NaN in den Geschwindigkeiten und im AEP."),
    ("En «{where}{path}», con n = {value}, EqGridRotorAvg no tiene nodos: NumPy promedia una lista vacía (con su propio "
     "aviso) y PyWake {version} puede dar NaN en las velocidades y en el AEP.",
     "In «{where}{path}», with n = {value}, EqGridRotorAvg has no nodes: NumPy averages an empty list (with its own "
     "warning) and PyWake {version} can give NaN in the wind speeds and in the AEP.",
     "Dans « {where}{path} », avec n = {value}, EqGridRotorAvg n’a pas de nœuds : NumPy fait la moyenne d’une liste vide "
     "(avec son propre avertissement) et PyWake {version} peut donner NaN dans les vitesses et dans l’AEP.",
     "In «{where}{path}» hat EqGridRotorAvg mit n = {value} keine Knoten: NumPy mittelt eine leere Liste (mit eigener "
     "Warnung), und PyWake {version} kann NaN in den Geschwindigkeiten und im AEP liefern."),
    ("En «{where}{path}», con n = {value}, EqGridRotorAvg no tiene nodos: NumPy promedia una lista vacía (con su propio "
     "aviso) y PyWake {version} puede dar NaN en la TI efectiva.",
     "In «{where}{path}», with n = {value}, EqGridRotorAvg has no nodes: NumPy averages an empty list (with its own "
     "warning) and PyWake {version} can give NaN in the effective TI.",
     "Dans « {where}{path} », avec n = {value}, EqGridRotorAvg n’a pas de nœuds : NumPy fait la moyenne d’une liste vide "
     "(avec son propre avertissement) et PyWake {version} peut donner NaN dans la TI effective.",
     "In «{where}{path}» hat EqGridRotorAvg mit n = {value} keine Knoten: NumPy mittelt eine leere Liste (mit eigener "
     "Warnung), und PyWake {version} kann NaN in der effektiven TI liefern."),
    ("En «{where}{path}», con c = [0, 0], la turbulencia añadida de STF2017 es infinita a cualquier distancia: PyWake "
     "{version} puede dar una TI efectiva, unas velocidades o un AEP no finitos, según el motor, el número de turbinas "
     "y el déficit.",
     "In «{where}{path}», with c = [0, 0], the added turbulence of STF2017 is infinite at any distance: PyWake {version} "
     "can give a non-finite effective TI, wind speeds or AEP, depending on the engine, the number of turbines and the "
     "deficit.",
     "Dans « {where}{path} », avec c = [0, 0], la turbulence ajoutée de STF2017 est infinie à toute distance : PyWake {version} peut donner une TI effective, des vitesses ou un AEP non finis, selon le moteur, le nombre d’éoliennes et le déficit.",
     "In «{where}{path}» ist die zusätzliche Turbulenz von STF2017 mit c = [0, 0] in jeder Entfernung unendlich: PyWake {version} kann eine nicht endliche effektive TI, Geschwindigkeiten oder eine nicht endliche AEP liefern, je nach Rechenmodell, Anzahl der Windturbinen und Defizit."),
    ("En «{where}{path}», con c[0] = 0, la turbulencia añadida de STF2017 es infinita a distancia 0: con All2AllIterative "
     "y un promedio de rotor de la turbulencia con un nodo en el centro, PyWake {version} puede dar una TI efectiva o un "
     "AEP no finitos; en el mapa, TI NaN en los puntos que caen sobre un buje.",
     "In «{where}{path}», with c[0] = 0, the added turbulence of STF2017 is infinite at distance 0: with All2AllIterative "
     "and a rotor average of the turbulence with a node at the centre, PyWake {version} can give a non-finite effective "
     "TI or AEP; in the map, NaN TI at the points that fall on a hub.",
     "Dans « {where}{path} », avec c[0] = 0, la turbulence ajoutée de STF2017 est infinie à distance 0 : avec "
     "All2AllIterative et une moyenne sur le rotor de la turbulence avec un nœud au centre, PyWake {version} peut "
     "donner une TI effective ou un AEP non finis ; dans la carte, TI NaN aux points qui tombent sur un moyeu.",
     "In «{where}{path}» ist die zusätzliche Turbulenz von STF2017 mit c[0] = 0 in der Entfernung 0 unendlich: mit "
     "All2AllIterative und einer Rotormittelung der Turbulenz mit einem Knoten in der Mitte kann PyWake {version} eine "
     "nicht endliche effektive TI oder eine nicht endliche AEP liefern; in der Karte NaN-TI an den Punkten, die auf "
     "eine Nabe fallen."),
    ("En «{where}{path}», con fgp[3] = 0, SelfSimilarityDeficit2020 divide por cero: PyWake {version} puede dar NaN en las "
     "velocidades y en el AEP.",
     "In «{where}{path}», with fgp[3] = 0, SelfSimilarityDeficit2020 divides by zero: PyWake {version} can give NaN in "
     "the wind speeds and in the AEP.",
     "Dans « {where}{path} », avec fgp[3] = 0, SelfSimilarityDeficit2020 divise par zéro : PyWake {version} peut donner "
     "NaN dans les vitesses et dans l’AEP.",
     "In «{where}{path}» teilt SelfSimilarityDeficit2020 mit fgp[3] = 0 durch null: PyWake {version} kann NaN in den "
     "Geschwindigkeiten und im AEP liefern."),
    ("AreaOverlapAvgModel solo tiene sentido con déficits de sombrero de copa (NOJ).",
     "AreaOverlapAvgModel only makes sense with top-hat deficits (NOJ).",
     "AreaOverlapAvgModel n’a de sens qu’avec des déficits en chapeau haut-de-forme (NOJ).",
     "AreaOverlapAvgModel ist nur mit Zylinderhut-Defiziten (NOJ) sinnvoll."),
    ("GaussianOverlapAvgModel necesita una estela gaussiana.",
     "GaussianOverlapAvgModel needs a Gaussian wake.",
     "GaussianOverlapAvgModel a besoin d’un sillage gaussien.",
     "GaussianOverlapAvgModel braucht einen gaußschen Nachlauf."),
    ("GaussianOverlapAvgModel necesita estas librerías, que no están disponibles: {modules}.",
     "GaussianOverlapAvgModel needs these libraries, which are not available: {modules}.",
     "GaussianOverlapAvgModel a besoin de ces bibliothèques, qui ne sont pas disponibles : {modules}.",
     "GaussianOverlapAvgModel braucht diese Bibliotheken, die nicht verfügbar sind: {modules}."),
    ("MultiMirror sin superposición propia no funciona en PyWake con un promedio de rotor.",
     "MultiMirror without a superposition of its own does not work in PyWake with a rotor average.",
     "MultiMirror sans superposition propre ne fonctionne pas dans PyWake avec une moyenne sur le rotor.",
     "MultiMirror ohne eigene Überlagerung funktioniert in PyWake nicht mit einem Rotormittelwert."),
    ("PyWake no pudo construir {cls} ({position}): {error}",
     "PyWake could not build {cls} ({position}): {error}",
     "PyWake n’a pas pu construire {cls} ({position}) : {error}",
     "PyWake konnte {cls} ({position}) nicht erstellen: {error}"),
    ("Comprobación de clases: en {position} se esperaba {expected} y el modelo construido tiene {observed}; no se ha "
     "simulado.",
     "Class check: {expected} was expected in {position} and the built model has {observed}; nothing was simulated.",
     "Contrôle des classes : {expected} était attendu dans {position} et le modèle construit a {observed} ; rien n’a été "
     "simulé.",
     "Klassenprüfung: in {position} wurde {expected} erwartet, und das erstellte Modell hat {observed}; es wurde nicht "
     "simuliert."),
    ("Comprobación de clases: no se pudo leer {position} del modelo construido: {diagnosis}; no se ha simulado.",
     "Class check: {position} of the built model could not be read: {diagnosis}; nothing was simulated.",
     "Contrôle des classes : {position} du modèle construit n’a pas pu être lu : {diagnosis} ; rien n’a été simulé.",
     "Klassenprüfung: {position} des erstellten Modells konnte nicht gelesen werden: {diagnosis}; es wurde nicht "
     "simuliert."),
    ("ninguno", "none", "aucun", "keiner"),
    ("ninguna", "none", "aucune", "keine"),
    ("sin bloqueo (no es el campo del AEP)", "without blockage (not the field of the AEP)",
     "sans blocage (ce n’est pas le champ de l’AEP)", "ohne Blockade (nicht das Feld der AEP)"),
    ("PyWake no expuso el campo WS libre ({error}): no se han escrito el viento libre ni los déficits.",
     "PyWake did not give the free WS field ({error}): neither the free wind nor the deficits have been written.",
     "PyWake n’a pas fourni le champ WS libre ({error}) : ni le vent libre ni les déficits n’ont été écrits.",
     "PyWake hat das freie WS-Feld nicht geliefert ({error}): weder der freie Wind noch die Defizite wurden geschrieben."),
    ("PyWake no calcula el mapa de flujo con CumulativeWakeSum y un modelo de suelo (el AEP sí).",
     "PyWake does not calculate the flow map with CumulativeWakeSum and a ground model (the AEP, it does).",
     "PyWake ne calcule pas la carte d’écoulement avec CumulativeWakeSum et un modèle de sol (l’AEP, si).",
     "PyWake berechnet die Strömungskarte mit CumulativeWakeSum und einem Bodenmodell nicht (die AEP schon)."),
    # The identification of a configuration (config.identification).
    ("{deficit} · motor {engine} · superposición {superposition} · turbulencia {turbulence} · bloqueo {blockage} · "
     "valores de su firma",
     "{deficit} · engine {engine} · superposition {superposition} · turbulence {turbulence} · blockage {blockage} · "
     "values of its signature",
     "{deficit} · moteur {engine} · superposition {superposition} · turbulence {turbulence} · blocage {blockage} · "
     "valeurs de sa signature",
     "{deficit} · Rechenkern {engine} · Überlagerung {superposition} · Turbulenz {turbulence} · Blockade {blockage} · Werte seiner Signatur"),
    ("{deficit} · motor {engine} · superposición {superposition} · turbulencia {turbulence} · bloqueo {blockage} · "
     "valores de su firma salvo: {differences}",
     "{deficit} · engine {engine} · superposition {superposition} · turbulence {turbulence} · blockage {blockage} · "
     "values of its signature except: {differences}",
     "{deficit} · moteur {engine} · superposition {superposition} · turbulence {turbulence} · blocage {blockage} · "
     "valeurs de sa signature sauf : {differences}",
     "{deficit} · Rechenkern {engine} · Überlagerung {superposition} · Turbulenz {turbulence} · Blockade {blockage} · Werte seiner Signatur außer: {differences}"),
    ("motor", "engine", "moteur", "Rechenkern"),
    ("déficit de estela", "wake deficit", "déficit de sillage", "Nachlaufdefizit"),
    ("promedio de rotor", "rotor averaging", "moyenne sur le rotor", "Rotormittelung"),
    ("suelo", "ground", "sol", "Boden"),
    ("superposición de estelas", "wake superposition", "superposition des sillages", "Nachlaufüberlagerung"),
    ("turbulencia añadida", "added turbulence", "turbulence ajoutée", "zusätzliche Turbulenz"),
    # --- Q5e: the resolutions that take the cause away without another rule, R8, SquaredSum in the blockage ---
    ("Elige All2AllIterative (o PropagateUpDownIterative, con use_effective_ws en el déficit y en el bloqueo), o quita "
     "el bloqueo.",
     "Choose All2AllIterative (or PropagateUpDownIterative, with use_effective_ws in the deficit and in the blockage), "
     "or remove the blockage.",
     "Choisissez All2AllIterative (ou PropagateUpDownIterative, avec use_effective_ws dans le déficit et dans le blocage), ou retirez le blocage.",
     "Wählen Sie All2AllIterative (oder PropagateUpDownIterative, mit use_effective_ws im Defizit und in der Blockade) oder entfernen Sie die Blockade."),
    ("Elige LinearSum para el bloqueo, cambia a All2AllIterative o a LinearSum, SquaredSum o MaxSum como "
     "superposición de estelas, o quita el bloqueo.",
     "Choose LinearSum for the blockage, change to All2AllIterative or to LinearSum, SquaredSum or MaxSum as the wake "
     "superposition, or remove the blockage.",
     "Choisissez LinearSum pour le blocage, passez à All2AllIterative ou à LinearSum, SquaredSum ou MaxSum comme superposition des sillages, ou retirez le blocage.",
     "Wählen Sie LinearSum für die Blockade, wechseln Sie zu All2AllIterative oder zu LinearSum, SquaredSum oder MaxSum als Nachlaufüberlagerung, oder entfernen Sie die Blockade."),
    ("Elige LinearSum para el bloqueo, cambia a All2AllIterative con Suelo «Ninguno» o a LinearSum, SquaredSum o "
     "MaxSum como superposición de estelas, o quita el bloqueo.",
     "Choose LinearSum for the blockage, change to All2AllIterative with Ground «None» or to LinearSum, SquaredSum or "
     "MaxSum as the wake superposition, or remove the blockage.",
     "Choisissez LinearSum pour le blocage, passez à All2AllIterative avec Sol « Aucun » ou à LinearSum, SquaredSum ou MaxSum comme superposition des sillages, ou retirez le blocage.",
     "Wählen Sie LinearSum für die Blockade, wechseln Sie zu All2AllIterative mit Boden «Keines» oder zu LinearSum, SquaredSum oder MaxSum als Nachlaufüberlagerung, oder entfernen Sie die Blockade."),
    ("Elige LinearSum para el bloqueo, cambia a All2AllIterative con Suelo «Ninguno» o a LinearSum, SquaredSum o "
     "MaxSum como superposición de estelas con una superposición propia para MultiMirror, o quita el bloqueo.",
     "Choose LinearSum for the blockage, change to All2AllIterative with Ground «None» or to LinearSum, SquaredSum or "
     "MaxSum as the wake superposition with a superposition of its own for MultiMirror, or remove the blockage.",
     "Choisissez LinearSum pour le blocage, passez à All2AllIterative avec Sol « Aucun » ou à LinearSum, SquaredSum ou MaxSum comme superposition des sillages avec une superposition propre pour MultiMirror, ou retirez le blocage.",
     "Wählen Sie LinearSum für die Blockade, wechseln Sie zu All2AllIterative mit Boden «Keines» oder zu LinearSum, SquaredSum oder MaxSum als Nachlaufüberlagerung mit einer eigenen Überlagerung für MultiMirror, oder entfernen Sie die Blockade."),
    ("Elige LinearSum para el bloqueo, cambia a All2AllIterative o a LinearSum, SquaredSum o MaxSum como superposición "
     "de estelas con Suelo «Ninguno», o quita el bloqueo.",
     "Choose LinearSum for the blockage, change to All2AllIterative or to LinearSum, SquaredSum or MaxSum as the wake "
     "superposition with Ground «None», or remove the blockage.",
     "Choisissez LinearSum pour le blocage, passez à All2AllIterative ou à LinearSum, SquaredSum ou MaxSum comme superposition des sillages avec Sol « Aucun », ou retirez le blocage.",
     "Wählen Sie LinearSum für die Blockade, wechseln Sie zu All2AllIterative oder zu LinearSum, SquaredSum oder MaxSum als Nachlaufüberlagerung mit Boden «Keines», oder entfernen Sie die Blockade."),
    ("Elige Suelo «Ninguno» con rotor Ninguno, CGIRotorAvg o EqGridRotorAvg, o LinearSum, SquaredSum o MaxSum.",
     "Choose Ground «None» with rotor average None, CGIRotorAvg or EqGridRotorAvg, or LinearSum, SquaredSum or MaxSum.",
     "Choisissez Sol « Aucun » avec la moyenne sur le rotor Aucune, CGIRotorAvg ou EqGridRotorAvg, ou LinearSum, SquaredSum ou MaxSum.",
     "Wählen Sie Boden «Keines» mit der Rotormittelung Keine, CGIRotorAvg oder EqGridRotorAvg, oder LinearSum, SquaredSum oder MaxSum."),
    ("Elige Suelo «Ninguno» con rotor Ninguno, CGIRotorAvg o EqGridRotorAvg, o LinearSum, SquaredSum o MaxSum y una "
     "superposición propia para MultiMirror.",
     "Choose Ground «None» with rotor average None, CGIRotorAvg or EqGridRotorAvg, or LinearSum, SquaredSum or MaxSum "
     "and a superposition of its own for MultiMirror.",
     "Choisissez Sol « Aucun » avec la moyenne sur le rotor Aucune, CGIRotorAvg ou EqGridRotorAvg, ou LinearSum, SquaredSum ou MaxSum et une superposition propre pour MultiMirror.",
     "Wählen Sie Boden «Keines» mit der Rotormittelung Keine, CGIRotorAvg oder EqGridRotorAvg, oder LinearSum, SquaredSum oder MaxSum und eine eigene Überlagerung für MultiMirror."),
    ("Elige LinearSum para el bloqueo, o quita el bloqueo.", "Choose LinearSum for the blockage, or remove the blockage.",
     "Choisissez LinearSum pour le blocage, ou retirez le blocage.",
     "Wählen Sie LinearSum für die Blockade oder entfernen Sie die Blockade."),
    ("Elige LinearSum, SquaredSum o MaxSum.", "Choose LinearSum, SquaredSum or MaxSum.",
     "Choisissez LinearSum, SquaredSum ou MaxSum.", "Wählen Sie LinearSum, SquaredSum oder MaxSum."),
    ("Elige Ninguno, CGIRotorAvg o EqGridRotorAvg.", "Choose None, CGIRotorAvg or EqGridRotorAvg.",
     "Choisissez Aucun, CGIRotorAvg ou EqGridRotorAvg.", "Wählen Sie Keines, CGIRotorAvg oder EqGridRotorAvg."),
    ("Elige All2AllIterative, o quita el bloqueo.", "Choose All2AllIterative, or remove the blockage.",
     "Choisissez All2AllIterative, ou retirez le blocage.", "Wählen Sie All2AllIterative oder entfernen Sie die Blockade."),
    ("Elige Suelo «Ninguno», o LinearSum, SquaredSum o MaxSum.",
     "Choose Ground «None», or LinearSum, SquaredSum or MaxSum.",
     "Choisissez Sol « Aucun », ou LinearSum, SquaredSum ou MaxSum.",
     "Wählen Sie Boden «Keines» oder LinearSum, SquaredSum oder MaxSum."),
    ("Elige rotor «Ninguno», Mirror, o dale a MultiMirror una superposición propia (LinearSum, SquaredSum o MaxSum).",
     "Choose rotor «None», Mirror, or give MultiMirror a superposition of its own (LinearSum, SquaredSum or MaxSum).",
     "Choisissez rotor « Aucun », Mirror, ou donnez à MultiMirror une superposition propre (LinearSum, SquaredSum ou MaxSum).",
     "Wählen Sie Rotor «Keines», Mirror, oder geben Sie MultiMirror eine eigene Überlagerung (LinearSum, SquaredSum oder MaxSum)."),
    ("Elige rotor Ninguno, CGIRotorAvg o EqGridRotorAvg.",
     "Choose rotor average None, CGIRotorAvg or EqGridRotorAvg.",
     "Choisissez la moyenne sur le rotor Aucune, CGIRotorAvg ou EqGridRotorAvg.",
     "Wählen Sie die Rotormittelung Keine, CGIRotorAvg oder EqGridRotorAvg."),
    ("Elige rotor «Ninguno», RotorCenter, CGIRotorAvg o EqGridRotorAvg.",
     "Choose rotor «None», RotorCenter, CGIRotorAvg or EqGridRotorAvg.",
     "Choisissez rotor « Aucun », RotorCenter, CGIRotorAvg ou EqGridRotorAvg.",
     "Wählen Sie Rotor «Keines», RotorCenter, CGIRotorAvg oder EqGridRotorAvg."),
    ("Elige LinearSum, SquaredSum o MaxSum y una superposición propia para MultiMirror.",
     "Choose LinearSum, SquaredSum or MaxSum and a superposition of its own for MultiMirror.",
     "Choisissez LinearSum, SquaredSum ou MaxSum et une superposition propre pour MultiMirror.",
     "Wählen Sie LinearSum, SquaredSum oder MaxSum und eine eigene Überlagerung für MultiMirror."),
    ("Elige Suelo «Ninguno», o LinearSum, SquaredSum o MaxSum y una superposición propia para MultiMirror.",
     "Choose Ground «None», or LinearSum, SquaredSum or MaxSum and a superposition of its own for MultiMirror.",
     "Choisissez Sol « Aucun », ou LinearSum, SquaredSum ou MaxSum et une superposition propre pour MultiMirror.",
     "Wählen Sie Boden «Keines» oder LinearSum, SquaredSum oder MaxSum und eine eigene Überlagerung für MultiMirror."),
    ("Para el ráster, elige Suelo «Ninguno», o LinearSum, SquaredSum o MaxSum y una superposición propia para "
     "MultiMirror.",
     "For the raster, choose Ground «None», or LinearSum, SquaredSum or MaxSum and a superposition of its own for "
     "MultiMirror.",
     "Pour le raster, choisissez Sol « Aucun », ou LinearSum, SquaredSum ou MaxSum et une superposition propre pour MultiMirror.",
     "Für das Raster wählen Sie Boden «Keines» oder LinearSum, SquaredSum oder MaxSum und eine eigene Überlagerung für MultiMirror."),
    ("Para el ráster, elige Suelo «Ninguno», o LinearSum, SquaredSum o MaxSum.",
     "For the raster, choose Ground «None», or LinearSum, SquaredSum or MaxSum.",
     "Pour le raster, choisissez Sol « Aucun », ou LinearSum, SquaredSum ou MaxSum.",
     "Für das Raster wählen Sie Boden «Keines» oder LinearSum, SquaredSum oder MaxSum."),
    ("Quita el promedio de rotor del bloqueo, usa Mirror, o dale a MultiMirror una superposición propia (LinearSum o "
     "MaxSum).",
     "Remove the rotor average of the blockage, use Mirror, or give MultiMirror a superposition of its own (LinearSum "
     "or MaxSum).",
     "Retirez la moyenne sur le rotor du blocage, utilisez Mirror, ou donnez à MultiMirror une superposition propre (LinearSum ou MaxSum).",
     "Entfernen Sie die Rotormittelung der Blockade, verwenden Sie Mirror oder geben Sie MultiMirror eine eigene Überlagerung (LinearSum oder MaxSum)."),
    ("WeightedSum y CumulativeWakeSum solo funcionan en PyWake con promedios de rotor por nodos que no sean "
     "WSPowerRotorAvg; {rotor} no lo es.",
     "WeightedSum and CumulativeWakeSum only work in PyWake with node-based rotor averages other than "
     "WSPowerRotorAvg; {rotor} is not one.",
     "WeightedSum et CumulativeWakeSum ne fonctionnent dans PyWake qu’avec des moyennes de rotor par nœuds autres que "
     "WSPowerRotorAvg ; {rotor} n’en est pas une.",
     "WeightedSum und CumulativeWakeSum funktionieren in PyWake nur mit knotenbasierten Rotormittelungen außer "
     "WSPowerRotorAvg; {rotor} ist keine."),
    ("En «{where}{path}», weight_limit = {value} (≤ 0) es el máximo del peso de cada contribución que WeightedSum "
     "pondera cuando itera (las que superan delta; el menor entre el cociente de velocidades de convección y "
     "weight_limit, superposition_models.py:148): con un cociente positivo pesan {value} (con 0 se anulan; con un "
     "negativo se invierten); con uno menor conservan el suyo. Si no itera (según max_err, max_iter y los valores), "
     "suma linealmente.",
     "In «{where}{path}», weight_limit = {value} (≤ 0) is the maximum of the weight of each contribution WeightedSum "
     "weighs when it iterates (those above delta; the smaller of the ratio of convection velocities and weight_limit, "
     "superposition_models.py:148): with a positive ratio they weigh {value} (with 0 they cancel; with a negative they "
     "are inverted); with a smaller one they keep theirs. If it does not iterate (depending on max_err, max_iter and "
     "the values), it sums linearly.",
     "Dans « {where}{path} », weight_limit = {value} (≤ 0) est le maximum du poids de chaque contribution que "
     "WeightedSum pondère quand il itère (celles au-dessus de delta ; le plus petit du rapport des vitesses de "
     "convection et de weight_limit, superposition_models.py:148) : avec un rapport positif elles pèsent {value} (avec "
     "0 elles s’annulent ; avec un négatif elles s’inversent) ; avec un rapport inférieur elles gardent le leur. S’il "
     "n’itère pas (selon max_err, max_iter et les valeurs), il somme linéairement.",
     "In «{where}{path}» ist weight_limit = {value} (≤ 0) das Maximum des Gewichts jedes Beitrags, den WeightedSum "
     "gewichtet, wenn es iteriert (die über delta; das Kleinere aus dem Verhältnis der Konvektionsgeschwindigkeiten "
     "und weight_limit, superposition_models.py:148): mit positivem Verhältnis wiegen sie {value} (mit 0 heben sie sich "
     "auf; mit einem negativen Wert kehren sie sich um); mit einem kleineren behalten sie ihres. Iteriert es nicht "
     "(je nach max_err, max_iter und den Werten), summiert es linear."),
    ("PyWake {version}: con SquaredSum en «{where}», el cálculo se detiene si alguna contribución del bloqueo es una "
     "aceleración, lo habitual en un bloqueo (superposition_models.py:55); depende de los valores: es un error del "
     "cálculo.",
     "PyWake {version}: with SquaredSum in «{where}», the calculation stops if any contribution of the blockage is a "
     "speed-up, the usual in a blockage (superposition_models.py:55); it depends on the values: it is an error of the "
     "calculation.",
     "PyWake {version} : avec SquaredSum dans « {where} », le calcul s’arrête si une contribution du blocage est une "
     "accélération, ce qui est habituel dans un blocage (superposition_models.py:55) ; cela dépend des valeurs : "
     "c’est une erreur du calcul.",
     "PyWake {version}: mit SquaredSum in «{where}» bricht die Berechnung ab, wenn ein Beitrag der Blockade eine "
     "Beschleunigung ist, was bei einer Blockade üblich ist (superposition_models.py:55); es hängt von den Werten ab: "
     "es ist ein Fehler der Berechnung."),
    ("bloqueo", "blockage", "blocage", "Blockade"),
    ("{label} · {path}", "{label} · {path}", "{label} · {path}", "{label} · {path}"),  # a route in a position
    ("superposición del bloqueo", "blockage superposition", "superposition du blocage", "Überlagerung der Blockade"),
    ("PyWake no tiene el módulo {module} de {cls}: {error}",
     "PyWake does not have the module {module} of {cls}: {error}",
     "PyWake n’a pas le module {module} de {cls} : {error}",
     "PyWake hat das Modul {module} von {cls} nicht: {error}"),
    ("La instalación de PyWake no tiene la clase {cls} en {module}.",
     "The PyWake installation does not have the class {cls} in {module}.",
     "L’installation de PyWake n’a pas la classe {cls} dans {module}.",
     "Die PyWake-Installation hat die Klasse {cls} in {module} nicht."),
    ("La instalación de PyWake no tiene la función {cls} en {module}.",
     "The PyWake installation does not have the function {cls} in {module}.",
     "L’installation de PyWake n’a pas la fonction {cls} dans {module}.",
     "Die PyWake-Installation hat die Funktion {cls} in {module} nicht."),
    # --- The contract of the API (api.py), the AEP and the notices (notices.py) ---
    ("La petición mezcla wake_physics con campos del esquema anterior ({fields}): usa solo wake_physics.",
     "The request mixes wake_physics with fields of the previous schema ({fields}): use only wake_physics.",
     "La demande mélange wake_physics avec des champs de l’ancien schéma ({fields}) : utilisez seulement wake_physics.",
     "Die Anfrage mischt wake_physics mit Feldern des früheren Schemas ({fields}): verwenden Sie nur wake_physics."),
    ("La petición usaba el esquema anterior de la física ({given}); se ha traducido como {translated}. La traducción "
     "no reproduce el comportamiento anterior: lo que se calcula es exactamente esa configuración.",
     "The request used the previous schema of the physics ({given}); it was translated as {translated}. The "
     "translation does not reproduce the previous behaviour: what is calculated is exactly that configuration.",
     "La demande utilisait l’ancien schéma de la physique ({given}) ; elle a été traduite en {translated}. La "
     "traduction ne reproduit pas l’ancien comportement : ce qui est calculé est exactement cette configuration.",
     "Die Anfrage verwendete das frühere Schema der Physik ({given}); sie wurde übersetzt als {translated}. Die "
     "Übersetzung reproduziert nicht das frühere Verhalten: berechnet wird genau diese Konfiguration."),
    ("No se puede calcular con esta configuración: {reasons}",
     "It cannot be calculated with this configuration: {reasons}",
     "Impossible de calculer avec cette configuration : {reasons}",
     "Mit dieser Konfiguration kann nicht gerechnet werden: {reasons}"),
    ("rotor_avg_model = {a!r} y wake_deficit_kwargs['rotorAvgModel'] = {b!r} se contradicen: indica el rotor una sola "
     "vez.",
     "rotor_avg_model = {a!r} and wake_deficit_kwargs['rotorAvgModel'] = {b!r} contradict each other: give the rotor "
     "only once.",
     "rotor_avg_model = {a!r} et wake_deficit_kwargs['rotorAvgModel'] = {b!r} se contredisent : indiquez le rotor une seule fois.",
     "rotor_avg_model = {a!r} und wake_deficit_kwargs['rotorAvgModel'] = {b!r} widersprechen sich: geben Sie den Rotor nur einmal an."),
    ("wake_model ya no se usa: indica la física con wake_physics (o con los campos del esquema anterior).",
     "wake_model is no longer used: give the physics with wake_physics (or with the fields of the previous schema).",
     "wake_model n’est plus utilisé : indiquez la physique avec wake_physics (ou avec les champs de l’ancien schéma).",
     "wake_model wird nicht mehr verwendet: geben Sie die Physik mit wake_physics an (oder mit den Feldern des früheren Schemas)."),
    ("wake_physics.adaptations: se esperaba una lista de diccionarios.",
     "wake_physics.adaptations: a list of dictionaries was expected.",
     "wake_physics.adaptations : une liste de dictionnaires était attendue.",
     "wake_physics.adaptations: es wurde eine Liste von Wörterbüchern erwartet."),
    ("wake_physics.blockage: sus argumentos van en blockage_params.",
     "wake_physics.blockage: its arguments go in blockage_params.",
     "wake_physics.blockage : ses arguments vont dans blockage_params.",
     "wake_physics.blockage: seine Argumente gehören in blockage_params."),
    ("wake_physics.blockage_params: hay argumentos del bloqueo, pero no hay bloqueo.",
     "wake_physics.blockage_params: there are blockage arguments, but no blockage model.",
     "wake_physics.blockage_params : il y a des arguments du blocage, mais pas de modèle de blocage.",
     "wake_physics.blockage_params: es gibt Argumente der Blockade, aber kein Blockademodell."),
    ("wake_physics.superposition: no puede faltar; déjalo sin indicar para usar la de la firma.",
     "wake_physics.superposition: it cannot be absent; leave it out to use the signature's.",
     "wake_physics.superposition : elle ne peut pas manquer ; ne l’indiquez pas pour utiliser celle de la signature.",
     "wake_physics.superposition: sie darf nicht fehlen; lassen Sie sie weg, um die der Signatur zu verwenden."),
    ("wake_physics.{key}: no puede faltar; déjalo sin indicar para usar el valor por defecto.",
     "wake_physics.{key}: it cannot be absent; leave it out to use the default value.",
     "wake_physics.{key} : il ne peut pas manquer ; ne l’indiquez pas pour utiliser la valeur par défaut.",
     "wake_physics.{key}: darf nicht fehlen; lassen Sie es weg, um den Standardwert zu verwenden."),
    ("wake_physics.{key}: se esperaba el nombre de una clase, no {value!r}.",
     "wake_physics.{key}: the name of a class was expected, not {value!r}.",
     "wake_physics.{key} : le nom d’une classe était attendu, pas {value!r}.",
     "wake_physics.{key}: es wurde der Name einer Klasse erwartet, nicht {value!r}."),
    ("wake_physics: claves desconocidas: {keys}.",
     "wake_physics: unknown keys: {keys}.",
     "wake_physics : clés inconnues : {keys}.",
     "wake_physics: unbekannte Schlüssel: {keys}."),
    ("wake_physics: se esperaba un diccionario, no {value!r}.",
     "wake_physics: a dictionary was expected, not {value!r}.",
     "wake_physics : un dictionnaire était attendu, pas {value!r}.",
     "wake_physics: es wurde ein Wörterbuch erwartet, nicht {value!r}."),
    ("wake_physics: versión {value!r}; se espera {version}.",
     "wake_physics: version {value!r}; {version} is expected.",
     "wake_physics : version {value!r} ; {version} est attendue.",
     "wake_physics: Version {value!r}; erwartet wird {version}."),
    ("{field}: se esperaba el nombre de una clase o {{'class': …}}, no {value!r}.",
     "{field}: the name of a class or {{'class': …}} was expected, not {value!r}.",
     "{field} : le nom d’une classe ou {{'class': …}} était attendu, pas {value!r}.",
     "{field}: es wurde der Name einer Klasse oder {{'class': …}} erwartet, nicht {value!r}."),
    ("{field}: se esperaba un diccionario de argumentos, no {value!r}.",
     "{field}: a dictionary of arguments was expected, not {value!r}.",
     "{field} : un dictionnaire d’arguments était attendu, pas {value!r}.",
     "{field}: es wurde ein Wörterbuch von Argumenten erwartet, nicht {value!r}."),
    ("{field}: se esperaba una clave o el nombre de una clase, no {value!r}.",
     "{field}: a key or the name of a class was expected, not {value!r}.",
     "{field} : une clé ou le nom d’une classe était attendu, pas {value!r}.",
     "{field}: es wurde ein Schlüssel oder der Name einer Klasse erwartet, nicht {value!r}."),
    ("{field}: una cadena solo de espacios no es un valor.",
     "{field}: a string of spaces only is not a value.",
     "{field} : une chaîne composée uniquement d’espaces n’est pas une valeur.",
     "{field}: eine Zeichenkette nur aus Leerzeichen ist kein Wert."),
    ("{field}: {cls} necesita sus argumentos ({args}): indícalo como {{'class': '{cls}', …}}.",
     "{field}: {cls} needs its arguments ({args}): give it as {{'class': '{cls}', …}}.",
     "{field} : {cls} a besoin de ses arguments ({args}) : indiquez-le comme {{'class': '{cls}', …}}.",
     "{field}: {cls} braucht seine Argumente ({args}): geben Sie es als {{'class': '{cls}', …}} an."),
    ("{field}: «AUTO» ya no es una opción; indica la clase (o déjalo sin indicar para usar el valor de la firma).",
     "{field}: «AUTO» is no longer an option; give the class (or leave it out to use the value of the signature).",
     "{field} : « AUTO » n’est plus une option ; indiquez la classe (ou ne l’indiquez pas pour utiliser la valeur de la signature).",
     "{field}: «AUTO» ist keine Option mehr; geben Sie die Klasse an (oder lassen Sie es weg, um den Wert der Signatur zu verwenden)."),
    ("{field}: «NONE» no es una opción.",
     "{field}: «NONE» is not an option.",
     "{field} : « NONE » n’est pas une option.",
     "{field}: «NONE» ist keine Option."),
    ("{field}: «{value}» no es una clave del esquema anterior ni una clase de {position}.",
     "{field}: «{value}» is neither a key of the previous schema nor a class of {position}.",
     "{field} : « {value} » n’est ni une clé de l’ancien schéma ni une classe de {position}.",
     "{field}: «{value}» ist weder ein Schlüssel des früheren Schemas noch eine Klasse für {position}."),
    ("{flag} = False contradice {field} = {value!r}: quita uno de los dos.",
     "{flag} = False contradicts {field} = {value!r}: remove one of the two.",
     "{flag} = False contredit {field} = {value!r} : retirez l’un des deux.",
     "{flag} = False widerspricht {field} = {value!r}: entfernen Sie eines der beiden."),
    ("{flag} = True contradice {field} = NONE: quita uno de los dos.",
     "{flag} = True contradicts {field} = NONE: remove one of the two.",
     "{flag} = True contredit {field} = NONE : retirez l’un des deux.",
     "{flag} = True widerspricht {field} = NONE: entfernen Sie eines der beiden."),
    ("{flag} = True sin {field}: elige la clase.",
     "{flag} = True without {field}: choose the class.",
     "{flag} = True sans {field} : choisissez la classe.",
     "{flag} = True ohne {field}: wählen Sie die Klasse."),
    ("{flag}: se esperaba True o False, no {value!r}.",
     "{flag}: True or False was expected, not {value!r}.",
     "{flag} : True ou False était attendu, pas {value!r}.",
     "{flag}: es wurde True oder False erwartet, nicht {value!r}."),
    ("{name} no es una opción de {position}.",
     "{name} is not an option of {position}.",
     "{name} n’est pas une option de {position}.",
     "{name} ist keine Option für {position}."),
    ("Configuración principal · PyWake {version} · {engine}: con CumulativeWakeSum, PyWake toma del déficit solo su "
     "anchura y el promedio de rotor de su distancia transversal, y calcula la intensidad del déficit en la "
     "superposición; por eso estos argumentos del déficit no afectan al resultado numérico por esta ruta: {args}. "
     "CumulativeWakeSum sigue usando la velocidad efectiva. Esto no elimina los requisitos de construcción ni los "
     "errores que PyWake pueda dar al evaluar. Este aviso no describe las variantes del desglose.",
     "Main configuration · PyWake {version} · {engine}: with CumulativeWakeSum, PyWake takes from the deficit only its "
     "width and the rotor average of its crosswind distance, and computes the strength of the deficit in the "
     "superposition; so these arguments of the deficit do not affect the numerical result along this path: {args}. "
     "CumulativeWakeSum still uses the effective wind speed. This does not remove the requirements to build the model "
     "nor the errors PyWake may give when evaluating it. This warning does not describe the variants of the breakdown.",
     "Configuration principale · PyWake {version} · {engine} : avec CumulativeWakeSum, PyWake ne prend du déficit que "
     "sa largeur et la moyenne sur le rotor de sa distance transversale, et calcule l’intensité du déficit dans la "
     "superposition ; ces arguments du déficit n’ont donc pas d’effet sur le résultat numérique par ce chemin : {args}. "
     "CumulativeWakeSum utilise toujours la vitesse effective. Cela ne supprime ni les exigences de construction ni les "
     "erreurs que PyWake peut donner à l’évaluation. Cet avertissement ne décrit pas les variantes de la décomposition.",
     "Hauptkonfiguration · PyWake {version} · {engine}: mit CumulativeWakeSum nimmt PyWake vom Defizit nur seine Breite und den Rotormittelwert seines Querabstands und berechnet die Stärke des Defizits in der Überlagerung; daher wirken sich diese Argumente des Defizits auf diesem Weg nicht auf das numerische Ergebnis aus: {args}. CumulativeWakeSum verwendet weiterhin die effektive Windgeschwindigkeit. Das hebt weder die Anforderungen an den Aufbau noch die Fehler auf, die PyWake bei der Auswertung melden kann. Diese Warnung beschreibt nicht die Varianten der Aufschlüsselung."),
    ("PyWake {version}: con PropagateUpDownIterative y {sup}, la simulación de las turbinas omite el bloqueo aguas "
     "abajo durante la pasada «down»; la pasada «up» conserva el bloqueo aguas arriba.",
     "PyWake {version}: with PropagateUpDownIterative and {sup}, the simulation of the turbines leaves out the "
     "downstream blockage during the «down» pass; the «up» pass keeps the upstream blockage.",
     "PyWake {version} : avec PropagateUpDownIterative et {sup}, la simulation des éoliennes omet le blocage en aval pendant la passe « down » ; la passe « up » conserve le blocage en amont.",
     "PyWake {version}: mit PropagateUpDownIterative und {sup} lässt die Simulation der Windturbinen die Blockade stromabwärts im «down»-Durchlauf weg; der «up»-Durchlauf behält die Blockade stromaufwärts."),
    ("La evaluación del campo sí calcula el bloqueo en sus puntos, con el estado de las turbinas de esa simulación.",
     "The evaluation of the field does calculate the blockage at its points, with the state of the turbines of that "
     "simulation.",
     "L’évaluation du champ calcule bien le blocage en ses points, avec l’état des éoliennes de cette simulation.",
     "Die Auswertung des Feldes berechnet die Blockade an seinen Punkten, mit dem Zustand der Windturbinen aus dieser Simulation."),
    ("En los puntos del campo, PyWake no aplica el promedio de rotor a la distancia transversal; el estado de las "
     "turbinas sale de la simulación anterior.",
     "At the points of the field, PyWake does not apply the rotor average to the crosswind distance; the state of the "
     "turbines comes from the previous simulation.",
     "Aux points du champ, PyWake n’applique pas la moyenne sur le rotor à la distance transversale ; l’état des éoliennes vient de la simulation précédente.",
     "An den Punkten des Feldes wendet PyWake den Rotormittelwert nicht auf den Querabstand an; der Zustand der Windturbinen stammt aus der vorherigen Simulation."),
    ("Convergencia de {loop}: no disponible en {count} de {calls} ({reasons}).",
     "Convergence of {loop}: not available in {count} of {calls} ({reasons}).",
     "Convergence de {loop} : non disponible dans {count} sur {calls} ({reasons}).",
     "Konvergenz von {loop}: in {count} von {calls} nicht verfügbar ({reasons})."),
    ("{cls} no usa la TI efectiva (use_effective_ti = False, o no lo tiene): la turbulencia elegida se calcula (la "
     "TI efectiva del resultado), pero no cambia el déficit.",
     "{cls} does not use the effective TI (use_effective_ti = False, or it does not have it): the chosen turbulence "
     "is calculated (the effective TI of the result), but it does not change the deficit.",
     "{cls} n’utilise pas la TI effective (use_effective_ti = False, ou il ne l’a pas) : la turbulence choisie est "
     "calculée (la TI effective du résultat), mais elle ne change pas le déficit.",
     "{cls} verwendet die effektive TI nicht (use_effective_ti = False, oder es hat sie nicht): die gewählte Turbulenz "
     "wird berechnet (die effektive TI des Ergebnisses), ändert aber das Defizit nicht."),
    ("causa no registrada", "cause not recorded", "cause non enregistrée", "Ursache nicht erfasst"),
    ("Convergencia de {loop}: {count} residuo(s) no finito(s).", "Convergence of {loop}: {count} non-finite residual(s).",
     "Convergence de {loop} : {count} résidu(s) non fini(s).", "Konvergenz von {loop}: {count} nicht endliche Residuen."),
    ("Convergencia de {loop}: una iteración; convergencia no comprobada.",
     "Convergence of {loop}: one iteration; convergence not checked.",
     "Convergence de {loop} : une itération ; convergence non vérifiée.",
     "Konvergenz von {loop}: eine Iteration; Konvergenz nicht geprüft."),
    ("En «{where}{path}», con convergence_tolerance = None, All2AllIterative hace una sola iteración y no comprueba "
     "la convergencia.",
     "In «{where}{path}», with convergence_tolerance = None, All2AllIterative makes a single iteration and does not "
     "check the convergence.",
     "Dans « {where}{path} », avec convergence_tolerance = None, All2AllIterative fait une seule itération et ne "
     "vérifie pas la convergence.",
     "In «{where}{path}» macht All2AllIterative mit convergence_tolerance = None eine einzige Iteration und prüft "
     "die Konvergenz nicht."),
    ("En «{where}{path}», con convergence_tolerance = {value} (≤ 0), All2AllIterative nunca cumple su criterio y "
     "agota sus iteraciones (como mucho, max(número de turbinas, 20)).",
     "In «{where}{path}», with convergence_tolerance = {value} (≤ 0), All2AllIterative never meets its criterion and "
     "uses up its iterations (at most max(number of turbines, 20)).",
     "Dans « {where}{path} », avec convergence_tolerance = {value} (≤ 0), All2AllIterative ne remplit jamais son critère et épuise ses itérations (au plus max(nombre d’éoliennes, 20)).",
     "In «{where}{path}» erfüllt All2AllIterative mit convergence_tolerance = {value} (≤ 0) sein Kriterium nie und "
     "braucht seine Iterationen auf (höchstens max(Anzahl der Turbinen, 20))."),
    ("En «{where}{path}», con convergence_tolerance = {value} (≤ 0), PropagateUpDownIterative nunca cumple su "
     "criterio y agota sus pasadas.",
     "In «{where}{path}», with convergence_tolerance = {value} (≤ 0), PropagateUpDownIterative never meets its "
     "criterion and uses up its passes.",
     "Dans « {where}{path} », avec convergence_tolerance = {value} (≤ 0), PropagateUpDownIterative ne remplit jamais "
     "son critère et épuise ses passes.",
     "In «{where}{path}» erfüllt PropagateUpDownIterative mit convergence_tolerance = {value} (≤ 0) sein Kriterium "
     "nie und braucht seine Durchläufe auf."),
    ("En «{where}{path}», MultiMirror representa cada turbina {count} veces (2^(2 + max(0, n_reps))): el coste del "
     "cálculo crece en esa proporción.",
     "In «{where}{path}», MultiMirror represents each turbine {count} times (2^(2 + max(0, n_reps))): the cost of "
     "the calculation grows in that proportion.",
     "Dans « {where}{path} », MultiMirror représente chaque éolienne {count} fois (2^(2 + max(0, n_reps))) : le coût du calcul croît dans cette proportion.",
     "In «{where}{path}» stellt MultiMirror jede Windturbine {count}-mal dar (2^(2 + max(0, n_reps))): der Rechenaufwand wächst im selben Verhältnis."),
    ("En «{where}{path}», con n_reps = {value}, PyWake {version} repite imágenes de las turbinas.",
     "In «{where}{path}», with n_reps = {value}, PyWake {version} repeats images of the turbines.",
     "Dans « {where}{path} », avec n_reps = {value}, PyWake {version} répète des images des éoliennes.",
     "In «{where}{path}» wiederholt PyWake {version} mit n_reps = {value} Spiegelbilder der Windturbinen."),
    ("En «{where}{path}», con n_reps = {value}, PyWake {version} añade también {copies} imagen(es) a la altura de la "
     "turbina real (a menos de 1 µm): aparece {times} veces en la suma del suelo.",
     "In «{where}{path}», with n_reps = {value}, PyWake {version} also adds {copies} image(s) at the height of the real "
     "turbine (within 1 µm): it appears {times} times in the sum of the ground.",
     "Dans « {where}{path} », avec n_reps = {value}, PyWake {version} ajoute aussi {copies} image(s) à la hauteur de l’éolienne réelle (à moins de 1 µm) : elle apparaît {times} fois dans la somme du sol.",
     "In «{where}{path}» fügt PyWake {version} mit n_reps = {value} auch {copies} Spiegelbild(er) auf der Höhe der echten Windturbine hinzu (bis auf 1 µm): sie erscheint {times}-mal in der Summe des Bodens."),
    ("En «{where}{path}», con n_reps = {value}, PyWake {version} añade también {copies} imagen(es) a la altura de la "
     "turbina real (a menos de 1 µm): aparece {times} veces en la suma del suelo (con un buje que no esté a la altura "
     "de un espejo; con las turbinas, al calcular, se cuenta exactamente).",
     "In «{where}{path}», with n_reps = {value}, PyWake {version} also adds {copies} image(s) at the height of the real "
     "turbine (within 1 µm): it appears {times} times in the sum of the ground (with a hub that is not at the height "
     "of a mirror; with the turbines, when calculating, it is counted exactly).",
     "Dans « {where}{path} », avec n_reps = {value}, PyWake {version} ajoute aussi {copies} image(s) à la hauteur de l’éolienne réelle (à moins de 1 µm) : elle apparaît {times} fois dans la somme du sol (avec un moyeu qui n’est pas à la hauteur d’un miroir ; avec les éoliennes, lors du calcul, le compte est exact).",
     "In «{where}{path}» fügt PyWake {version} mit n_reps = {value} auch {copies} Spiegelbild(er) auf der Höhe der echten Windturbine hinzu (bis auf 1 µm): sie erscheint {times}-mal in der Summe des Bodens (mit einer Nabe, die nicht auf der Höhe eines Spiegels liegt; mit den Windturbinen wird beim Berechnen genau gezählt)."),
    ("En «{where}{path}», n_reps = {value} es negativo: PyWake no añade repeticiones, como con 0.",
     "In «{where}{path}», n_reps = {value} is negative: PyWake adds no repetitions, as with 0.",
     "Dans « {where}{path} », n_reps = {value} est négatif : PyWake n’ajoute aucune répétition, comme avec 0.",
     "In «{where}{path}» ist n_reps = {value} negativ: PyWake fügt keine Wiederholungen hinzu, wie mit 0."),
    ("En «{where}{path}», con mirror_height = 0 el espejo superior coincide con el suelo: cada imagen de PyWake cae "
     "sobre la turbina real o sobre su imagen en el suelo.",
     "In «{where}{path}», with mirror_height = 0 the upper mirror is the ground: every image of PyWake falls on the "
     "real turbine or on its image in the ground.",
     "Dans « {where}{path} », avec mirror_height = 0 le miroir supérieur coïncide avec le sol : chaque image de PyWake tombe sur l’éolienne réelle ou sur son image dans le sol.",
     "In «{where}{path}» fällt mit mirror_height = 0 der obere Spiegel mit dem Boden zusammen: jedes Spiegelbild von PyWake liegt auf der echten Windturbine oder auf ihrem Spiegelbild im Boden."),
    ("En «{where}{path}», con n_reps = {value}, PyWake {version} añade también imágenes a la altura de la turbina real "
     "(a menos de 1 µm): aparece al menos {times} veces en la suma del suelo.",
     "In «{where}{path}», with n_reps = {value}, PyWake {version} also adds images at the height of the real turbine "
     "(within 1 µm): it appears at least {times} times in the sum of the ground.",
     "Dans « {where}{path} », avec n_reps = {value}, PyWake {version} ajoute aussi des images à la hauteur de l’éolienne réelle (à moins de 1 µm) : elle apparaît au moins {times} fois dans la somme du sol.",
     "In «{where}{path}» fügt PyWake {version} mit n_reps = {value} auch Spiegelbilder auf der Höhe der echten Windturbine hinzu (bis auf 1 µm): sie erscheint mindestens {times}-mal in der Summe des Bodens."),
    ("En «{where}{path}», el espejo superior de MultiMirror (mirror_height = {value} m) está a la altura de un buje "
     "o por debajo ({hub} m): sus imágenes no son las de un espejo por encima de las turbinas.",
     "In «{where}{path}», the upper mirror of MultiMirror (mirror_height = {value} m) is at the height of a hub or "
     "below it ({hub} m): its images are not those of a mirror above the turbines.",
     "Dans « {where}{path} », le miroir supérieur de MultiMirror (mirror_height = {value} m) est à la hauteur d’un moyeu ou en dessous ({hub} m) : ses images ne sont pas celles d’un miroir au-dessus des éoliennes.",
     "In «{where}{path}» liegt der obere Spiegel von MultiMirror (mirror_height = {value} m) auf Nabenhöhe oder darunter ({hub} m): seine Spiegelbilder sind nicht die eines Spiegels über den Windturbinen."),
    ("En «{where}{path}», si el espejo superior de MultiMirror queda a la altura de un buje o por debajo, sus "
     "imágenes no son las de un espejo por encima de las turbinas (se comprueba con las turbinas al calcular).",
     "In «{where}{path}», if the upper mirror of MultiMirror is at the height of a hub or below it, its images are "
     "not those of a mirror above the turbines (checked with the turbines when calculating).",
     "Dans « {where}{path} », si le miroir supérieur de MultiMirror est à la hauteur d’un moyeu ou en dessous, ses images ne sont pas celles d’un miroir au-dessus des éoliennes (vérifié avec les éoliennes lors du calcul).",
     "In «{where}{path}»: liegt der obere Spiegel von MultiMirror auf Nabenhöhe oder darunter, sind seine Spiegelbilder nicht die eines Spiegels über den Windturbinen (wird beim Rechnen mit den Windturbinen geprüft)."),
    ("En «{where}{path}», con {arg} = {value}, WeightedSum no pondera: suma las estelas linealmente.",
     "In «{where}{path}», with {arg} = {value}, WeightedSum does not weigh: it sums the wakes linearly.",
     "Dans « {where}{path} », avec {arg} = {value}, WeightedSum ne pondère pas : il somme les sillages linéairement.",
     "In «{where}{path}» gewichtet WeightedSum mit {arg} = {value} nicht: es summiert die Nachläufe linear."),
    ("En «{where}{path}», WeightedSum iterará hasta max_iter si el residuo no baja de max_err (max_err = {max_err}, "
     "max_iter = {max_iter}): con un valor alto, el cálculo puede tardar mucho o no terminar.",
     "In «{where}{path}», WeightedSum will iterate up to max_iter if the residual does not go under max_err (max_err = "
     "{max_err}, max_iter = {max_iter}): with a high value, the calculation may take very long or not end.",
     "Dans « {where}{path} », WeightedSum itérera jusqu’à max_iter si le résidu ne descend pas sous max_err (max_err = "
     "{max_err}, max_iter = {max_iter}) : avec une valeur élevée, le calcul peut être très long ou ne pas se terminer.",
     "In «{where}{path}» iteriert WeightedSum bis max_iter, wenn das Residuum nicht unter max_err sinkt (max_err = "
     "{max_err}, max_iter = {max_iter}): bei einem hohen Wert kann die Berechnung sehr lange dauern oder nicht enden."),
    ("En «{where}{path}», con max_iter = +inf, si la malla de velocidades incluye 0 m/s su nodo no se calcula aparte: "
     "sin él, WeightedSum podría no terminar.",
     "In «{where}{path}», with max_iter = +inf, if the grid of wind speeds includes 0 m/s its node is not calculated "
     "apart: without it, WeightedSum might not end.",
     "Dans « {where}{path} », avec max_iter = +inf, si la grille des vitesses inclut 0 m/s, son nœud n’est pas calculé "
     "à part : sans lui, WeightedSum pourrait ne pas se terminer.",
     "In «{where}{path}» wird mit max_iter = +inf der Knoten bei 0 m/s nicht getrennt berechnet, wenn das "
     "Geschwindigkeitsgitter 0 m/s enthält: ohne ihn könnte WeightedSum nicht enden."),
    ("En «{where}{path}», con delta = {value} (≤ 0), PyWake limita internamente el umbral a 1e-30.",
     "In «{where}{path}», with delta = {value} (≤ 0), PyWake limits the threshold internally to 1e-30.",
     "Dans « {where}{path} », avec delta = {value} (≤ 0), PyWake limite en interne le seuil à 1e-30.",
     "In «{where}{path}» begrenzt PyWake mit delta = {value} (≤ 0) den Schwellenwert intern auf 1e-30."),
    ("En «{where}{path}», con ss_lambda = {lam} y ss_eta = {eta}, ss_lambda·(ss_eta + x²) es negativo o nulo en parte "
     "del dominio: según las distancias, el promedio de rotor, la exclusión de la estela y ss_alpha, PyWake {version} "
     "puede dar NaN en las velocidades y en el AEP, o un error de cálculo.",
     "In «{where}{path}», with ss_lambda = {lam} and ss_eta = {eta}, ss_lambda·(ss_eta + x²) is negative or zero in "
     "part of the domain: depending on the distances, the rotor average, the exclusion of the wake and ss_alpha, "
     "PyWake {version} can give NaN in the wind speeds and in the AEP, or an error of the calculation.",
     "Dans « {where}{path} », avec ss_lambda = {lam} et ss_eta = {eta}, ss_lambda·(ss_eta + x²) est négatif ou nul "
     "dans une partie du domaine : selon les distances, la moyenne sur le rotor, l’exclusion du sillage et ss_alpha, "
     "PyWake {version} peut donner NaN dans les vitesses et dans l’AEP, ou une erreur de calcul.",
     "In «{where}{path}» ist ss_lambda·(ss_eta + x²) mit ss_lambda = {lam} und ss_eta = {eta} in einem Teil des "
     "Bereichs negativ oder null: je nach Abständen, Rotormittelung, Ausschluss des Nachlaufs und ss_alpha kann "
     "PyWake {version} NaN in den Geschwindigkeiten und im AEP liefern oder einen Rechenfehler."),
    ("En «{where}{path}», con high_ct_mod = True, PyWake {version} modifica en su sitio las distancias aguas abajo "
     "cuando se calcula con una sola velocidad, y con a ≥ 0,5 anula el bloqueo sin error.",
     "In «{where}{path}», with high_ct_mod = True, PyWake {version} modifies the downstream distances in place when "
     "calculating with a single wind speed, and with a ≥ 0.5 it cancels the blockage without an error.",
     "Dans « {where}{path} », avec high_ct_mod = True, PyWake {version} modifie sur place les distances en aval "
     "lorsqu’on calcule avec une seule vitesse, et avec a ≥ 0,5 il annule le blocage sans erreur.",
     "In «{where}{path}» ändert PyWake {version} mit high_ct_mod = True die Abstände stromabwärts an Ort und Stelle, "
     "wenn mit einer einzigen Windgeschwindigkeit gerechnet wird, und hebt mit a ≥ 0,5 die Blockade ohne Fehler auf."),
    ("Convergencia de {loop}: {states}. El resultado se conserva, pero no es un cálculo convergido.",
     "Convergence of {loop}: {states}. The result is kept, but it is not a converged calculation.",
     "Convergence de {loop} : {states}. Le résultat est conservé, mais ce n’est pas un calcul convergé.",
     "Konvergenz von {loop}: {states}. Das Ergebnis wird beibehalten, ist aber keine konvergierte Berechnung."),
    ("Cálculo principal: {warning}", "Main calculation: {warning}", "Calcul principal : {warning}",
     "Hauptberechnung: {warning}"),
    ("Variantes del desglose: {warning}", "Variants of the breakdown: {warning}",
     "Variantes de la décomposition : {warning}", "Varianten der Aufschlüsselung: {warning}"),
    ("Variantes del desglose de pérdidas…", "Variants of the loss breakdown…",
     "Variantes de la décomposition des pertes…", "Varianten der Verlustaufschlüsselung…"),
    ("[AEP] No se pudo calcular {term}: {error}", "[AEP] {term} could not be calculated: {error}",
     "[AEP] {term} n’a pas pu être calculé : {error}", "[AEP] {term} konnte nicht berechnet werden: {error}"),
    # --- The wake raster with the configuration of the AEP (wake_core/raster.py) ---
    ("Con WeightedSum, PyWake calcula sus pesos con un máximo global de cada cálculo: el mapa, calculado en {tiles} "
     "teselas, puede diferir del calculado de una vez (sensibilidad de PyWake, no un error del complemento).",
     "With WeightedSum, PyWake calculates its weights with a global maximum of each calculation: the map, calculated "
     "in {tiles} tiles, may differ from the one calculated at once (a sensitivity of PyWake, not an error of the "
     "plugin).",
     "Avec WeightedSum, PyWake calcule ses poids avec un maximum global de chaque calcul : la carte, calculée en "
     "{tiles} tuiles, peut différer de celle calculée en une fois (sensibilité de PyWake, pas une erreur de "
     "l’extension).",
     "Mit WeightedSum berechnet PyWake seine Gewichte mit einem globalen Maximum jeder Berechnung: die in {tiles} "
     "Kacheln berechnete Karte kann von der in einem Schritt berechneten abweichen (eine Empfindlichkeit von PyWake, "
     "kein Fehler des Plugins)."),
    ("La fábrica de turbinas no está disponible.", "The turbine factory is not available.",
     "La fabrique d’éoliennes n’est pas disponible.", "Die Windturbinenfabrik ist nicht verfügbar."),
    ("No se pudo identificar el sector dominante del recurso: indica una dirección.",
     "The dominant sector of the resource could not be identified: give a direction.",
     "Le secteur dominant de la ressource n’a pas pu être identifié : indiquez une direction.",
     "Der dominante Sektor der Ressource konnte nicht bestimmt werden: Geben Sie eine Richtung an."),
    ("No se puede calcular el ráster con esta configuración: {reasons}",
     "The raster cannot be calculated with this configuration: {reasons}",
     "Impossible de calculer le raster avec cette configuration : {reasons}",
     "Das Raster kann mit dieser Konfiguration nicht berechnet werden: {reasons}"),
    ("Se omitieron {n_out} de {n_total} turbinas fuera del dominio del recurso.",
     "{n_out} of {n_total} turbines outside the domain of the resource were left out.",
     "{n_out} des {n_total} éoliennes hors du domaine de la ressource ont été omises.",
     "{n_out} von {n_total} Windturbinen außerhalb des Ressourcenbereichs wurden ausgelassen."),
    ("Todas las turbinas están fuera del dominio del recurso ({kind}).",
     "All the turbines are outside the domain of the resource ({kind}).",
     "Toutes les éoliennes sont hors du domaine de la ressource ({kind}).",
     "Alle Windturbinen liegen außerhalb des Ressourcenbereichs ({kind})."),
    ("escenario recalculado sin bloqueo; no representa el campo de la configuración del diálogo",
     "scenario recalculated without blockage; it does not represent the field of the configuration of the dialog",
     "scénario recalculé sans blocage ; il ne représente pas le champ de la configuration de la boîte de dialogue",
     "ohne Blockade neu berechnetes Szenario; es stellt nicht das Feld der Konfiguration des Dialogs dar"),
    ("Se ha usado CGIRotorAvg(7) en vez de GaussianOverlapAvgModel porque no está disponible {missing} (elegido con «Continuar»). {install}",
     "CGIRotorAvg(7) was used instead of GaussianOverlapAvgModel because {missing} is not available (chosen with «Continue»). {install}",
     "CGIRotorAvg(7) a été utilisé à la place de GaussianOverlapAvgModel car {missing} n’est pas disponible (choisi avec « Continuer »). {install}",
     "Statt GaussianOverlapAvgModel wurde CGIRotorAvg(7) verwendet, weil {missing} nicht verfügbar ist (mit «Fortfahren» gewählt). {install}"),
    ("Se ha usado CGIRotorAvg(7) en vez de GaussianOverlapAvgModel porque no están disponibles {missing} (elegido con «Continuar»). {install}",
     "CGIRotorAvg(7) was used instead of GaussianOverlapAvgModel because {missing} are not available (chosen with «Continue»). {install}",
     "CGIRotorAvg(7) a été utilisé à la place de GaussianOverlapAvgModel car {missing} ne sont pas disponibles (choisi avec « Continuer »). {install}",
     "Statt GaussianOverlapAvgModel wurde CGIRotorAvg(7) verwendet, weil {missing} nicht verfügbar sind (mit «Fortfahren» gewählt). {install}"),
    # Applied by the decision saved for a predefined model (decision 21 of the predefined models).
    ("Se ha usado CGIRotorAvg(7) en vez de GaussianOverlapAvgModel porque no está disponible {missing} (aplicado por la decisión guardada para este modelo). {install}",
     "CGIRotorAvg(7) was used instead of GaussianOverlapAvgModel because {missing} is not available (applied by the decision saved for this model). {install}",
     "CGIRotorAvg(7) a été utilisé à la place de GaussianOverlapAvgModel car {missing} n’est pas disponible (appliqué par la décision enregistrée pour ce modèle). {install}",
     "Statt GaussianOverlapAvgModel wurde CGIRotorAvg(7) verwendet, weil {missing} nicht verfügbar ist (durch die für dieses Modell gespeicherte Entscheidung angewendet). {install}"),
    ("Se ha usado CGIRotorAvg(7) en vez de GaussianOverlapAvgModel porque no están disponibles {missing} (aplicado por la decisión guardada para este modelo). {install}",
     "CGIRotorAvg(7) was used instead of GaussianOverlapAvgModel because {missing} are not available (applied by the decision saved for this model). {install}",
     "CGIRotorAvg(7) a été utilisé à la place de GaussianOverlapAvgModel car {missing} ne sont pas disponibles (appliqué par la décision enregistrée pour ce modèle). {install}",
     "Statt GaussianOverlapAvgModel wurde CGIRotorAvg(7) verwendet, weil {missing} nicht verfügbar sind (durch die für dieses Modell gespeicherte Entscheidung angewendet). {install}"),
    # How to install what is missing (``validation.install_hint``).
    ("Si falta, puedes instalarlo con «python -m pip install {packages}» y reiniciar QGIS; si ya está instalado y no carga, consulta las instrucciones de instalación.",
     "If it is missing, you can install it with «python -m pip install {packages}» and restart QGIS; if it is already installed and does not load, see the installation instructions.",
     "S’il manque, vous pouvez l’installer avec « python -m pip install {packages} » et redémarrer QGIS ; s’il est déjà installé et ne se charge pas, consultez les instructions d’installation.",
     "Falls es fehlt, können Sie es mit «python -m pip install {packages}» installieren und QGIS neu starten; falls es bereits installiert ist und nicht lädt, lesen Sie die Installationsanleitung."),
    ("Si faltan, puedes instalarlos con «python -m pip install {packages}» y reiniciar QGIS; si ya están instalados y no cargan, consulta las instrucciones de instalación.",
     "If they are missing, you can install them with «python -m pip install {packages}» and restart QGIS; if they are already installed and do not load, see the installation instructions.",
     "S’ils manquent, vous pouvez les installer avec « python -m pip install {packages} » et redémarrer QGIS ; s’ils sont déjà installés et ne se chargent pas, consultez les instructions d’installation.",
     "Falls sie fehlen, können Sie sie mit «python -m pip install {packages}» installieren und QGIS neu starten; falls sie bereits installiert sind und nicht laden, lesen Sie die Installationsanleitung."),
    ("En QGIS para Windows, h5py no se instala con pip, porque su HDF5 puede chocar con la que ya carga QGIS: consulta las instrucciones de instalación.",
     "In QGIS on Windows, h5py is not installed with pip, because its HDF5 may conflict with the one QGIS already loads: see the installation instructions.",
     "Dans QGIS sous Windows, h5py ne s’installe pas avec pip, car sa HDF5 peut entrer en conflit avec celle que QGIS charge déjà : consultez les instructions d’installation.",
     "In QGIS unter Windows wird h5py nicht mit pip installiert, weil seine HDF5 mit der kollidieren kann, die QGIS bereits lädt: Lesen Sie die Installationsanleitung."),
    ("Puedes instalar el resto con «python -m pip install {packages}» y reiniciar QGIS; en QGIS para Windows, h5py no se instala con pip, porque su HDF5 puede chocar con la que ya carga QGIS: consulta las instrucciones de instalación.",
     "You can install the rest with «python -m pip install {packages}» and restart QGIS; in QGIS on Windows, h5py is not installed with pip, because its HDF5 may conflict with the one QGIS already loads: see the installation instructions.",
     "Vous pouvez installer le reste avec « python -m pip install {packages} » et redémarrer QGIS ; dans QGIS sous Windows, h5py ne s’installe pas avec pip, car sa HDF5 peut entrer en conflit avec celle que QGIS charge déjà : consultez les instructions d’installation.",
     "Den Rest können Sie mit «python -m pip install {packages}» installieren und QGIS neu starten; in QGIS unter Windows wird h5py nicht mit pip installiert, weil seine HDF5 mit der kollidieren kann, die QGIS bereits lädt: Lesen Sie die Installationsanleitung."),
    # A predefined model adapted with «Continuar» (decision 19 of the predefined models).
    ("Configuración adaptada a partir de {preset}: CGIRotorAvg(7)",
     "Configuration adapted from {preset}: CGIRotorAvg(7)",
     "Configuration adaptée à partir de {preset} : CGIRotorAvg(7)",
     "Aus {preset} angepasste Konfiguration: CGIRotorAvg(7)"),
    ("[REPORT] Configuración adaptada a partir del modelo predefinido {preset}, revisión {revision} ({reference} de "
     "PyWake {reference_version}), calculada con PyWake {executed_version}.",
     "[REPORT] Configuration adapted from the predefined model {preset}, revision {revision} ({reference} of PyWake "
     "{reference_version}), calculated with PyWake {executed_version}.",
     "[REPORT] Configuration adaptée à partir du modèle prédéfini {preset}, révision {revision} ({reference} de "
     "PyWake {reference_version}), calculée avec PyWake {executed_version}.",
     "[REPORT] Aus dem vordefinierten Modell {preset}, Revision {revision} ({reference} von PyWake "
     "{reference_version}), angepasste Konfiguration, berechnet mit PyWake {executed_version}."),
    # The notes of the predefined models (presets.NOTES), under «Modelo», in the help of a model and in the results.
    ("k = 0,0324555, fijo: PyWake no da a este modelo un valor de k. Se toma el valor de k por defecto de "
     "BastankhahGaussianDeficit en PyWake 2.6.18.",
     "k = 0.0324555, fixed: PyWake gives this model no value of k. The default k of BastankhahGaussianDeficit in "
     "PyWake 2.6.18 is used.",
     "k = 0,0324555, fixe : PyWake ne donne pas de valeur de k à ce modèle. On prend la valeur de k par défaut de "
     "BastankhahGaussianDeficit dans PyWake 2.6.18.",
     "k = 0,0324555, fest: PyWake gibt diesem Modell keinen Wert für k vor. Es wird der Standardwert von k aus "
     "BastankhahGaussianDeficit in PyWake 2.6.18 übernommen."),
    ("Usa CrespoHernandez, como la documentación de PyWake y el ejemplo de PyWake 2.6.18. En 2.6.18 su firma no trae "
     "turbulencia y no se puede construir con sus valores por defecto; este preset la incorpora explícitamente.",
     "Uses CrespoHernandez, like the PyWake documentation and the PyWake 2.6.18 example. In 2.6.18 its signature has "
     "no turbulence model and it cannot be built with its defaults; this preset adds it explicitly.",
     "Utilise CrespoHernandez, comme la documentation de PyWake et l’exemple de PyWake 2.6.18. En 2.6.18, sa signature "
     "n’inclut pas de turbulence et il ne peut pas être construit avec ses valeurs par défaut ; ce modèle prédéfini "
     "l’ajoute explicitement.",
     "Verwendet CrespoHernandez wie die PyWake-Dokumentation und das Beispiel von PyWake 2.6.18. In 2.6.18 enthält "
     "seine Signatur keine Turbulenz, und es lässt sich mit seinen Standardwerten nicht erstellen; dieses "
     "vordefinierte Modell fügt sie ausdrücklich hinzu."),
    ("Modelo de parque de referencia marcado como obsoleto por PyWake.",
     "Reference wind farm model marked as deprecated by PyWake.",
     "Modèle de parc de référence marqué comme obsolète par PyWake.",
     "Von PyWake als veraltet markiertes Referenz-Windparkmodell."),
    # The edge cases of a calculation (#63: ag_core/edge_cases.py and ag_core/simulation/zero_node.py).
    ("Aviso no disponible: {error}", "Warning not available: {error}", "Avertissement non disponible : {error}",
     "Hinweis nicht verfügbar: {error}"),
    ("{label}: velocidad efectiva negativa en {count} de {cells} casos (turbina × dirección × velocidad; mínimo finito "
     "{min} m/s; turbinas {turbines}). PyWake la calcula sin error; el resultado se conserva.",
     "{label}: negative effective wind speed in {count} of {cells} cases (turbine × direction × speed; finite minimum "
     "{min} m/s; turbines {turbines}). PyWake calculates it without an error; the result is kept.",
     "{label} : vitesse effective négative dans {count} cas sur {cells} (éolienne × direction × vitesse ; minimum fini "
     "{min} m/s ; éoliennes {turbines}). PyWake la calcule sans erreur ; le résultat est conservé.",
     "{label}: negative effektive Windgeschwindigkeit in {count} von {cells} Fällen (Windturbine × Richtung × Geschwindigkeit; endliches Minimum {min} m/s; Windturbinen {turbines}). PyWake berechnet sie ohne Fehler; das Ergebnis bleibt erhalten."),
    ("{label}: velocidad efectiva no finita en {count} casos (NaN {nan}, +inf {pinf}, −inf {ninf}).",
     "{label}: non-finite effective wind speed in {count} cases (NaN {nan}, +inf {pinf}, −inf {ninf}).",
     "{label} : vitesse effective non finie dans {count} cas (NaN {nan}, +inf {pinf}, −inf {ninf}).",
     "{label}: nicht endliche effektive Windgeschwindigkeit in {count} Fällen (NaN {nan}, +inf {pinf}, −inf {ninf})."),
    ("{label}: {name} no finita en {count} casos (NaN {nan}, +inf {pinf}, −inf {ninf}).",
     "{label}: non-finite {name} in {count} cases (NaN {nan}, +inf {pinf}, −inf {ninf}).",
     "{label} : {name} non finie dans {count} cas (NaN {nan}, +inf {pinf}, −inf {ninf}).",
     "{label}: nicht endliche {name} in {count} Fällen (NaN {nan}, +inf {pinf}, −inf {ninf})."),
    ("{label}: clasificación de los casos no finitos no disponible ({error}): todos cuentan como casos con energía.",
     "{label}: classification of the non-finite cases not available ({error}): all count as cases with energy.",
     "{label} : classification des cas non finis non disponible ({error}) : tous comptent comme des cas avec énergie.",
     "{label}: Einordnung der nicht endlichen Fälle nicht verfügbar ({error}): alle zählen als Fälle mit Energie."),
    ("{label}: {count} casos sin energía (P = 0, o P no finita en un sector de frecuencia nula) con AEP no finito: no "
     "aportan energía y las sumas los omiten.",
     "{label}: {count} cases without energy (P = 0, or non-finite P in a sector of zero frequency) with a non-finite "
     "AEP: they contribute no energy and the sums leave them out.",
     "{label} : {count} cas sans énergie (P = 0, ou P non finie dans un secteur de fréquence nulle) avec un AEP non "
     "fini : ils n’apportent pas d’énergie et les sommes les omettent.",
     "{label}: {count} Fälle ohne Energie (P = 0 oder nicht endliches P in einem Sektor mit Häufigkeit null) mit nicht endlicher AEP: Sie tragen keine Energie bei, und die Summen lassen sie aus."),
    ("{label}: AEP no finito en {count} casos que pueden tener energía (NaN {nan}, +inf {pinf}, −inf {ninf}).",
     "{label}: non-finite AEP in {count} cases that may have energy (NaN {nan}, +inf {pinf}, −inf {ninf}).",
     "{label} : AEP non fini dans {count} cas qui peuvent avoir de l’énergie (NaN {nan}, +inf {pinf}, −inf {ninf}).",
     "{label}: nicht endliche AEP in {count} Fällen, die Energie haben können (NaN {nan}, +inf {pinf}, −inf {ninf})."),
    ("{label}: AEP parcial (omite casos no finitos con energía) en las turbinas {turbines}, y en el total del parque.",
     "{label}: partial AEP (it leaves out non-finite cases with energy) for the turbines {turbines}, and in the farm "
     "total.",
     "{label} : AEP partiel (il omet des cas non finis avec énergie) pour les éoliennes {turbines}, et dans le total du "
     "parc.",
     "{label}: unvollständige AEP (sie lässt nicht endliche Fälle mit Energie aus) bei den Windturbinen {turbines} und in der Summe des Parks."),
    ("{label}: AEP por sector no finito en los sectores {sectors}° (su suma desborda).",
     "{label}: non-finite AEP per sector in the sectors {sectors}° (their sum overflows).",
     "{label} : AEP par secteur non fini dans les secteurs {sectors}° (leur somme déborde).",
     "{label}: nicht endliche AEP je Sektor in den Sektoren {sectors}° (ihre Summe läuft über)."),
    ("{label}: AEP total del parque no finito.", "{label}: non-finite AEP of the farm total.",
     "{label} : AEP total du parc non fini.", "{label}: nicht endliche AEP in der Summe des Parks."),
    ("{label}: una suma del AEP desborda: da un infinito sin ningún caso infinito.",
     "{label}: a sum of the AEP overflows: it gives an infinite value without any infinite case.",
     "{label} : une somme de l’AEP déborde : elle donne une valeur infinie sans aucun cas infini.",
     "{label}: Eine Summe der AEP läuft über: Sie ergibt einen unendlichen Wert ohne einen unendlichen Fall."),
    ("{label}: AEP por sector parcial en los sectores {sectors}°: omite los casos no finitos con energía y toda la "
     "energía de las direcciones cuya suma no es finita ({directions}°).",
     "{label}: partial AEP per sector in the sectors {sectors}°: it leaves out the non-finite cases with energy and "
     "all the energy of the directions whose sum is not finite ({directions}°).",
     "{label} : AEP par secteur partiel dans les secteurs {sectors}° : il omet les cas non finis avec énergie et "
     "toute l’énergie des directions dont la somme n’est pas finie ({directions}°).",
     "{label}: unvollständige AEP je Sektor in den Sektoren {sectors}°: Sie lässt die nicht endlichen Fälle mit Energie und die gesamte Energie der Richtungen aus, deren Summe nicht endlich ist ({directions}°)."),
    ("{label}: AEP no finito en las turbinas {turbines}, y en el total del parque.",
     "{label}: non-finite AEP for the turbines {turbines}, and in the farm total.",
     "{label} : AEP non fini pour les éoliennes {turbines}, et dans le total du parc.",
     "{label}: nicht endliche AEP bei den Windturbinen {turbines} und in der Summe des Parks."),
    ("{label}: AEP por sector parcial (omite casos no finitos con energía) en los sectores {sectors}°.",
     "{label}: partial AEP per sector (it leaves out non-finite cases with energy) in the sectors {sectors}°.",
     "{label} : AEP par secteur partiel (il omet des cas non finis avec énergie) dans les secteurs {sectors}°.",
     "{label}: unvollständige AEP je Sektor (sie lässt nicht endliche Fälle mit Energie aus) in den Sektoren {sectors}°."),
    ("no disponible: la simulación no da la TI efectiva", "not available: the simulation does not give the effective TI",
     "non disponible : la simulation ne donne pas la TI effective",
     "nicht verfügbar: die Simulation liefert die effektive TI nicht"),
    ("infinita", "infinite", "infinie", "unendlich"),
    ("NaN por ponderación con una P no finita", "NaN from weighting with a non-finite P",
     "NaN par pondération avec une P non finie", "NaN durch Gewichtung mit einem nicht endlichen P"),
    ("indefinida por peso total nulo", "undefined because the total weight is zero",
     "indéfinie car le poids total est nul", "undefiniert, weil das Gesamtgewicht null ist"),
    ("no finita en la reducción", "not finite in the reduction", "non finie dans la réduction",
     "nicht endlich in der Reduktion"),
    ("Con WeightedSum, el nodo de 0 m/s se calcula aparte: las simulaciones van sin él, para que WeightedSum pueda "
     "ponderar, y su parte del AEP sale de una simulación pequeña con las velocidades {small} m/s.",
     "With WeightedSum, the 0 m/s node is calculated apart: the simulations run without it, so that WeightedSum can "
     "weight, and its part of the AEP comes from a small simulation with the wind speeds {small} m/s.",
     "Avec WeightedSum, le nœud de 0 m/s est calculé à part : les simulations se font sans lui, pour que WeightedSum "
     "puisse pondérer, et sa part de l’AEP vient d’une petite simulation avec les vitesses {small} m/s.",
     "Mit WeightedSum wird der Knoten bei 0 m/s getrennt berechnet: die Simulationen laufen ohne ihn, damit "
     "WeightedSum gewichten kann, und sein Anteil am AEP stammt aus einer kleinen Simulation mit den "
     "Geschwindigkeiten {small} m/s."),
    ("Excepción de WeightedSum con el nodo de 0 m/s no aplicada: {reason}",
     "Exception of WeightedSum with the 0 m/s node not applied: {reason}",
     "Exception de WeightedSum avec le nœud de 0 m/s non appliquée : {reason}",
     "Ausnahme von WeightedSum mit dem Knoten bei 0 m/s nicht angewendet: {reason}"),
    ("con max_iter = +inf, WeightedSum podría no terminar sin el nodo de 0 m/s.",
     "with max_iter = +inf, WeightedSum might not end without the 0 m/s node.",
     "avec max_iter = +inf, WeightedSum pourrait ne pas se terminer sans le nœud de 0 m/s.",
     "mit max_iter = +inf könnte WeightedSum ohne den Knoten bei 0 m/s nicht enden."),
    ("sin el nodo de 0 m/s, la malla quedaría con un solo nodo.",
     "without the 0 m/s node, the grid would be left with a single node.",
     "sans le nœud de 0 m/s, la grille n’aurait plus qu’un seul nœud.",
     "ohne den Knoten bei 0 m/s bliebe das Gitter mit einem einzigen Knoten."),
    ("no se pudo preparar ({error}).", "it could not be prepared ({error}).", "elle n’a pas pu être préparée ({error}).",
     "sie konnte nicht vorbereitet werden ({error})."),
    ("con la malla sin 0 m/s PyWake da un error: {error}", "with the grid without 0 m/s PyWake gives an error: {error}",
     "avec la grille sans 0 m/s, PyWake donne une erreur : {error}",
     "mit dem Gitter ohne 0 m/s gibt PyWake einen Fehler: {error}"),
    ("Simulación auxiliar de 0 m/s", "Auxiliary simulation of 0 m/s", "Simulation auxiliaire de 0 m/s",
     "Hilfssimulation bei 0 m/s"),
    ("Simulación auxiliar de 0 m/s: {warning}", "Auxiliary simulation of 0 m/s: {warning}",
     "Simulation auxiliaire de 0 m/s : {warning}", "Hilfssimulation bei 0 m/s: {warning}"),
    ("no comparable: valor no finito", "not comparable: value not finite", "non comparable : valeur non finie",
     "nicht vergleichbar: Wert nicht endlich"),
    ("Variantes del desglose ({term})", "Variants of the breakdown ({term})", "Variantes de la décomposition ({term})",
     "Varianten der Aufschlüsselung ({term})"),
    ("TI efectiva {reason} en las turbinas {turbines}: no se guarda ningún valor.",
     "Effective TI {reason} at the turbines {turbines}: no value is kept.",
     "TI effective {reason} aux éoliennes {turbines} : aucune valeur n’est conservée.",
     "Effektive TI {reason} an den Windturbinen {turbines}: es wird kein Wert gespeichert."),
    ("velocidad efectiva", "effective speed", "vitesse effective", "effektive Geschwindigkeit"),
    ("velocidad libre", "free speed", "vitesse libre", "freie Geschwindigkeit"),
    ("Ráster: {name} negativa en {count} de {cells} celdas (mínimo finito {min} m/s). PyWake la calcula sin error; el "
     "mapa se conserva.",
     "Raster: negative {name} in {count} of {cells} cells (finite minimum {min} m/s). PyWake calculates it without an "
     "error; the map is kept.",
     "Raster : {name} négative dans {count} des {cells} cellules (minimum fini {min} m/s). PyWake la calcule sans "
     "erreur ; la carte est conservée.",
     "Raster: negative {name} in {count} von {cells} Zellen (endliches Minimum {min} m/s). PyWake berechnet sie ohne "
     "Fehler; die Karte bleibt erhalten."),
    ("Ráster: {name} no finita en {count} celdas (NaN {nan}, +inf {pinf}, −inf {ninf}): son NoData, y las estadísticas "
     "solo cubren las celdas finitas.",
     "Raster: non-finite {name} in {count} cells (NaN {nan}, +inf {pinf}, −inf {ninf}): they are NoData, and the "
     "statistics only cover the finite cells.",
     "Raster : {name} non finie dans {count} cellules (NaN {nan}, +inf {pinf}, −inf {ninf}) : ce sont des NoData, et les "
     "statistiques ne couvrent que les cellules finies.",
     "Raster: nicht endliche {name} in {count} Zellen (NaN {nan}, +inf {pinf}, −inf {ninf}): sie sind NoData, und die "
     "Statistiken umfassen nur die endlichen Zellen."),
    ("Ráster: con velocidad libre negativa, el déficit relativo cambia de signo en {count} celdas.",
     "Raster: with a negative free speed, the relative deficit changes sign in {count} cells.",
     "Raster : avec une vitesse libre négative, le déficit relatif change de signe dans {count} cellules.",
     "Raster: bei negativer freier Geschwindigkeit wechselt das relative Defizit in {count} Zellen das Vorzeichen."),
    ("Ráster: el déficit relativo no está definido con velocidad libre nula: {count} celdas son NoData.",
     "Raster: the relative deficit is not defined with a null free speed: {count} cells are NoData.",
     "Raster : le déficit relatif n’est pas défini avec une vitesse libre nulle : {count} cellules sont des NoData.",
     "Raster: das relative Defizit ist bei freier Geschwindigkeit null nicht definiert: {count} Zellen sind NoData."),
    ("Ráster: la capa {layer} no tiene celdas finitas: se escribe entera como NoData y sin estilo.",
     "Raster: the layer {layer} has no finite cells: it is written entirely as NoData and without a style.",
     "Raster : la couche {layer} n’a aucune cellule finie : elle est écrite entièrement en NoData et sans style.",
     "Raster: Der Layer {layer} hat keine endlichen Zellen: Er wird vollständig als NoData und ohne Stil geschrieben."),
    ("Ráster: la capa {layer} tiene {count} celdas no finitas por desbordamiento al escribirla en float32: son NoData.",
     "Raster: the layer {layer} has {count} non-finite cells from an overflow when written in float32: they are NoData.",
     "Raster : la couche {layer} a {count} cellules non finies par dépassement lors de son écriture en float32 : ce sont "
     "des NoData.",
     "Raster: Der Layer {layer} hat {count} nicht endliche Zellen durch Überlauf beim Schreiben in float32: Sie sind NoData."),
    ("Ráster: sin estelas: la velocidad efectiva es igual a la libre en todas las celdas.",
     "Raster: no wakes: the effective speed equals the free speed in every cell.",
     "Raster : pas de sillages : la vitesse effective est égale à la vitesse libre dans toutes les cellules.",
     "Raster: keine Nachläufe: die effektive Geschwindigkeit ist in allen Zellen gleich der freien."),
)

SOURCES = tuple(r[0] for r in _ROWS)
TRANSLATIONS = {lang: {r[0]: r[i] for r in _ROWS} for i, lang in ((1, "en"), (2, "fr"), (3, "de"))}


def register_messages_translations():
    from ...i18n import register_language
    for language, mapping in TRANSLATIONS.items():
        register_language(language, mapping, {})
