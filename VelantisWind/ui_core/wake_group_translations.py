# -*- coding: utf-8 -*-
"""Translations of the texts of the «Modelo de estela» group (``wake_group.py``): Spanish source to en, fr and de.

Registered as whole strings only; a text that is also in another table has the same translation there (#67)."""

_ROWS = (
    # (es, en, fr, de)
    ("Modelo de estela", "Wake model", "Modèle de sillage", "Nachlaufmodell"),
    ("Motor", "Engine", "Moteur", "Rechenkern"),
    ("Déficit de estela", "Wake deficit", "Déficit de sillage", "Nachlaufdefizit"),
    ("Parámetros del déficit", "Deficit parameters", "Paramètres du déficit", "Parameter des Defizits"),
    ("Parámetros de la superposición", "Superposition parameters", "Paramètres de la superposition",
     "Parameter der Überlagerung"),
    ("Parámetros de la turbulencia", "Turbulence parameters", "Paramètres de la turbulence", "Parameter der Turbulenz"),
    ("Promedio de rotor", "Rotor averaging", "Moyenne sur le rotor", "Rotormittelung"),
    ("Suelo", "Ground", "Sol", "Boden"),
    ("Superposición de estelas", "Wake superposition", "Superposition des sillages", "Nachlaufüberlagerung"),
    ("Bloqueo", "Blockage", "Blocage", "Blockade"),
    ("Turbulencia añadida", "Added turbulence", "Turbulence ajoutée", "Zusätzliche Turbulenz"),
    ("Ajustes numéricos del motor", "Numerical settings of the engine", "Réglages numériques du moteur",
     "Numerische Einstellungen des Rechenkerns"),
    ("Ninguno", "None", "Aucun", "Keines"),
    ("Ninguna", "None", "Aucune", "Keine"),
    ("Ninguno: la velocidad en el centro del rotor, sin promediar.",
     "None: the wind speed at the rotor centre, not averaged.",
     "Aucun : la vitesse au centre du rotor, sans moyenne.",
     "Keines: die Geschwindigkeit in der Rotormitte, ohne Mittelung."),
    ("Ninguno: sin modelo de suelo.", "None: no ground model.", "Aucun : pas de modèle de sol.",
     "Keines: kein Bodenmodell."),
    ("Ninguna: sin turbulencia añadida por las estelas; la TI es la ambiente.",
     "None: no turbulence added by the wakes; the TI is the ambient one.",
     "Aucune : pas de turbulence ajoutée par les sillages ; la TI est la TI ambiante.",
     "Keine: keine durch die Nachläufe zusätzliche Turbulenz; die TI ist die Umgebungs-TI."),
    ("Ninguno: sin bloqueo.", "None: no blockage.", "Aucun : pas de blocage.", "Keines: keine Blockade."),
    ("Sin bloqueo, normalmente obtendrás resultados equivalentes con PropagateDownwind y menor coste de cálculo. "
     "Pueden existir diferencias numéricas según la configuración.",
     "Without blockage, you will normally obtain equivalent results with PropagateDownwind at a lower computational "
     "cost. There may be numerical differences depending on the configuration.",
     "Sans blocage, vous obtiendrez normalement des résultats équivalents avec PropagateDownwind pour un coût de calcul "
     "moindre. Des différences numériques peuvent exister selon la configuration.",
     "Ohne Blockade erhalten Sie normalerweise gleichwertige Ergebnisse mit PropagateDownwind bei geringerem "
     "Rechenaufwand. Je nach Konfiguration kann es numerische Unterschiede geben."),
    ("Sin bloqueo, PUD mantiene el requisito de usar velocidad efectiva y realiza una propagación adicional. "
     "PropagateDownwind permite calcular este escenario con menor coste.",
     "Without blockage, PUD keeps the requirement of using the effective wind speed and performs an additional "
     "propagation. PropagateDownwind can calculate this scenario at a lower cost.",
     "Sans blocage, PUD conserve l’exigence d’utiliser la vitesse effective et effectue une propagation "
     "supplémentaire. PropagateDownwind permet de calculer ce scénario à moindre coût.",
     "Ohne Blockade behält PUD die Anforderung bei, die effektive Geschwindigkeit zu verwenden, und führt eine "
     "zusätzliche Ausbreitung durch. PropagateDownwind berechnet dieses Szenario mit geringerem Aufwand."),
    ("PropagateUpDownIterative exige un déficit que escale con la velocidad efectiva, y {cls} no tiene "
     "use_effective_ws.",
     "PropagateUpDownIterative requires a deficit that scales with the effective wind speed, and {cls} has no "
     "use_effective_ws.",
     "PropagateUpDownIterative exige un déficit qui varie avec la vitesse effective, et {cls} n’a pas "
     "use_effective_ws.",
     "PropagateUpDownIterative verlangt ein Defizit, das mit der effektiven Geschwindigkeit skaliert, und {cls} hat "
     "kein use_effective_ws."),
    ("{cls} no usa la TI efectiva (use_effective_ti = False, o no lo tiene): la turbulencia elegida se calcula (la "
     "TI efectiva del resultado), pero no cambia el déficit.",
     "{cls} does not use the effective TI (use_effective_ti = False, or it does not have it): the chosen turbulence "
     "is calculated (the effective TI of the result), but it does not change the deficit.",
     "{cls} n’utilise pas la TI effective (use_effective_ti = False, ou il ne l’a pas) : la turbulence choisie est "
     "calculée (la TI effective du résultat), mais elle ne change pas le déficit.",
     "{cls} verwendet die effektive TI nicht (use_effective_ti = False, oder es hat sie nicht): die gewählte Turbulenz "
     "wird berechnet (die effektive TI des Ergebnisses), ändert aber das Defizit nicht."),
    ("La preferencia guardada «{value}» de {position} ya no es una opción: se abre con la de la firma ({default}).",
     "The saved preference «{value}» of {position} is no longer an option: it opens with the signature's ({default}).",
     "La préférence enregistrée « {value} » de {position} n’est plus une option : elle s’ouvre avec celle de la "
     "signature ({default}).",
     "Die gespeicherte Einstellung «{value}» für {position} ist keine Option mehr: es wird die der Signatur "
     "verwendet ({default})."),
    ("True: el bloqueo escala con la velocidad efectiva que llega a la turbina; False: con la velocidad libre. "
     "PropagateUpDownIterative exige True.",
     "True: the blockage scales with the effective wind speed reaching the turbine; False: with the free wind speed. "
     "PropagateUpDownIterative requires True.",
     "True : le blocage varie avec la vitesse effective qui atteint l’éolienne ; False : avec la vitesse libre. "
     "PropagateUpDownIterative exige True.",
     "True: die Blockade skaliert mit der effektiven Geschwindigkeit an der Windturbine; False: mit der freien Geschwindigkeit. PropagateUpDownIterative verlangt True."),
    ("No se puede leer el valor de «{arg}» de {cls}: escribe un número.",
     "The value of «{arg}» of {cls} cannot be read: type a number.",
     "La valeur de « {arg} » de {cls} ne peut pas être lue : saisissez un nombre.",
     "Der Wert von «{arg}» von {cls} kann nicht gelesen werden: geben Sie eine Zahl ein."),
    ("No se ofrece {name} = {value}: {reason}", "{name} = {value} is not offered: {reason}",
     "{name} = {value} n’est pas proposé : {reason}", "{name} = {value} wird nicht angeboten: {reason}"),
    ("Valor de la firma: {value}.", "Signature value: {value}.", "Valeur de la signature : {value}.",
     "Wert der Signatur: {value}."),
    ("El suelo la llama con un único array y WeightedSum necesita más datos: PyWake se detiene donde evalúa el suelo.",
     "The ground calls it with a single array and WeightedSum needs more data: PyWake stops where it evaluates the "
     "ground.",
     "Le sol l’appelle avec un seul tableau et WeightedSum a besoin de plus de données : PyWake s’arrête là où il "
     "évalue le sol.",
     "Der Boden ruft sie mit einem einzigen Array auf, und WeightedSum braucht mehr Daten: PyWake bricht dort ab, wo "
     "es den Boden auswertet."),
    ("El suelo la llama con un único array y CumulativeWakeSum necesita más datos: PyWake se detiene donde evalúa el "
     "suelo.",
     "The ground calls it with a single array and CumulativeWakeSum needs more data: PyWake stops where it evaluates "
     "the ground.",
     "Le sol l’appelle avec un seul tableau et CumulativeWakeSum a besoin de plus de données : PyWake s’arrête là où "
     "il évalue le sol.",
     "Der Boden ruft sie mit einem einzigen Array auf, und CumulativeWakeSum braucht mehr Daten: PyWake bricht dort "
     "ab, wo es den Boden auswertet."),
    ("SqrMaxSum no se puede llamar con un único array: PyWake se detiene donde evalúa el suelo.",
     "SqrMaxSum cannot be called with a single array: PyWake stops where it evaluates the ground.",
     "SqrMaxSum ne peut pas être appelé avec un seul tableau : PyWake s’arrête là où il évalue le sol.",
     "SqrMaxSum kann nicht mit einem einzigen Array aufgerufen werden: PyWake bricht dort ab, wo es den Boden "
     "auswertet."),
    ("Mínimo −2: de −2 a 0 no hay nodos y PyWake puede dar NaN; con −3 o menos no lo construye.",
     "Minimum −2: from −2 to 0 there are no nodes and PyWake can give NaN; with −3 or less it does not build it.",
     "Minimum −2 : de −2 à 0 il n’y a pas de nœuds et PyWake peut donner NaN ; avec −3 ou moins il ne le construit pas.",
     "Mindestens −2: von −2 bis 0 gibt es keine Knoten, und PyWake kann NaN liefern; mit −3 oder weniger baut es ihn "
     "nicht."),
    ("El promedio de rotor de este modelo, aparte del del déficit; ninguno: la velocidad en el centro del rotor.",
     "The rotor average of this model, apart from that of the deficit; none: the wind speed at the rotor centre.",
     "La moyenne sur le rotor de ce modèle, distincte de celle du déficit ; aucune : la vitesse au centre du rotor.",
     "Die Rotormittelung dieses Modells, getrennt von der des Defizits; keine: die Geschwindigkeit in der "
     "Rotormitte."),
    ("El modelo de suelo de este bloqueo, aparte del del déficit; ninguno: sin suelo.",
     "The ground model of this blockage, apart from that of the deficit; none: no ground.",
     "Le modèle de sol de ce blocage, distinct de celui du déficit ; aucun : sans sol.",
     "Das Bodenmodell dieser Blockade, getrennt von dem des Defizits; keines: ohne Boden."),
    ("Hereda la superposición del objeto que envuelve: la de las estelas en el suelo del déficit, la del bloqueo en "
     "el del bloqueo.",
     "Inherits the superposition of the object it wraps: that of the wakes in the ground of the deficit, that of the "
     "blockage in the ground of the blockage.",
     "Hérite de la superposition de l’objet qu’il enveloppe : celle des sillages dans le sol du déficit, celle du "
     "blocage dans le sol du blocage.",
     "Erbt die Überlagerung des Objekts, das er umhüllt: die der Nachläufe im Boden des Defizits, die der Blockade "
     "im Boden der Blockade."),
    ("TI efectiva = TI ambiente + la suma de las TI añadidas.",
     "Effective TI = ambient TI + the sum of the added TIs.",
     "TI effective = TI ambiante + la somme des TI ajoutées.",
     "Effektive TI = Umgebungs-TI + die Summe der zusätzlichen TI."),
    ("TI efectiva = TI ambiente + √(suma de los cuadrados de las TI añadidas).",
     "Effective TI = ambient TI + √(sum of the squares of the added TIs).",
     "TI effective = TI ambiante + √(somme des carrés des TI ajoutées).",
     "Effektive TI = Umgebungs-TI + √(Summe der Quadrate der zusätzlichen TI)."),
    ("TI efectiva = TI ambiente + la mayor de las TI añadidas.",
     "Effective TI = ambient TI + the largest of the added TIs.",
     "TI effective = TI ambiante + la plus grande des TI ajoutées.",
     "Effektive TI = Umgebungs-TI + die größte der zusätzlichen TI."),
    ("TI efectiva = √(TI ambiente² + (la mayor de las TI añadidas)²).",
     "Effective TI = √(ambient TI² + (the largest of the added TIs)²).",
     "TI effective = √(TI ambiante² + (la plus grande des TI ajoutées)²).",
     "Effektive TI = √(Umgebungs-TI² + (die größte der zusätzlichen TI)²)."),
    ("Peso en campana de la tesis de Frandsen (Eq. 3.16), según el desplazamiento lateral de la turbina respecto de "
     "la estela.",
     "Bell-shaped weight of Frandsen’s thesis (Eq. 3.16), by the lateral offset of the turbine from the wake.",
     "Poids en cloche de la thèse de Frandsen (éq. 3.16), selon le décalage latéral de l’éolienne par rapport au sillage.",
     "Glockenförmiges Gewicht aus Frandsens Dissertation (Gl. 3.16), nach dem seitlichen Versatz der Windturbine zum Nachlauf."),
    ("La TI añadida entera dentro de un sector de 21,6° aguas abajo y hasta distance_limit diámetros (IEC 61400-1).",
     "The whole added TI within a 21.6° sector downstream and up to distance_limit diameters (IEC 61400-1).",
     "La TI ajoutée entière dans un secteur de 21,6° en aval et jusqu’à distance_limit diamètres (CEI 61400-1).",
     "Die gesamte zusätzliche TI in einem 21,6°-Sektor stromabwärts und bis zu distance_limit Durchmessern "
     "(IEC 61400-1)."),
    ("La causa está en «Parámetros del modelo de suelo…» ({where}).",
     "The cause is in «Parameters of the ground model…» ({where}).",
     "La cause est dans « Paramètres du modèle de sol… » ({where}).",
     "Die Ursache liegt in «Parameter des Bodenmodells…» ({where})."),
    # --- The dialog of the Energy module (aep_setup_dialog.py) ---
    ("Las preferencias de física de la versión anterior (motor, déficit, rotor, superposición, turbulencia, bloqueo y "
     "parámetros avanzados) ya no se usan: el grupo «Modelo de estela» se abre con los valores de las firmas de PyWake "
     "y recuerda sus propias elecciones.",
     "The physics preferences of the previous version (engine, deficit, rotor, superposition, turbulence, blockage and advanced parameters) are no longer used: the “Wake model” group opens with the values of the PyWake signatures and remembers its own choices.",
     "Les préférences de physique de la version précédente (moteur, déficit, rotor, superposition, turbulence, blocage "
     "et paramètres avancés) ne sont plus utilisées : le groupe « Modèle de sillage » s’ouvre avec les valeurs des "
     "signatures de PyWake et retient ses propres choix.",
     "Die Physik-Einstellungen der vorherigen Version (Rechenkern, Defizit, Rotor, Überlagerung, Turbulenz, Blockade und erweiterte Parameter) werden nicht mehr verwendet: Die Gruppe „Nachlaufmodell“ öffnet sich mit den Werten der PyWake-Signaturen und merkt sich ihre eigenen Auswahlen."),
    ("No se puede calcular con esta configuración:", "It cannot be calculated with this configuration:",
     "Impossible de calculer avec cette configuration :", "Mit dieser Konfiguration kann nicht gerechnet werden:"),
    ("Se usará CGIRotorAvg(7) en vez de GaussianOverlapAvgModel porque no está disponible {libs}. Pulsa Continuar "
     "para calcular {what} con CGIRotorAvg(7).",
     "CGIRotorAvg(7) will be used instead of GaussianOverlapAvgModel because {libs} is not available. Press Continue "
     "to calculate {what} with CGIRotorAvg(7).",
     "CGIRotorAvg(7) sera utilisé à la place de GaussianOverlapAvgModel car {libs} n’est pas disponible. Cliquez sur Continuer pour calculer {what} avec CGIRotorAvg(7).",
     "Statt GaussianOverlapAvgModel wird CGIRotorAvg(7) verwendet, weil {libs} nicht verfügbar ist. Klicken Sie auf Fortfahren, um {what} mit CGIRotorAvg(7) zu berechnen."),
    ("Se usará CGIRotorAvg(7) en vez de GaussianOverlapAvgModel porque no están disponibles {libs}. Pulsa Continuar "
     "para calcular {what} con CGIRotorAvg(7).",
     "CGIRotorAvg(7) will be used instead of GaussianOverlapAvgModel because {libs} are not available. Press "
     "Continue to calculate {what} with CGIRotorAvg(7).",
     "CGIRotorAvg(7) sera utilisé à la place de GaussianOverlapAvgModel car {libs} ne sont pas disponibles. Cliquez sur Continuer pour calculer {what} avec CGIRotorAvg(7).",
     "Statt GaussianOverlapAvgModel wird CGIRotorAvg(7) verwendet, weil {libs} nicht verfügbar sind. Klicken Sie auf Fortfahren, um {what} mit CGIRotorAvg(7) zu berechnen."),
    ("el AEP", "the AEP", "l’AEP", "die AEP"),
    ("el ráster de estelas", "the wake raster", "le raster de sillages", "das Nachlaufraster"),
    ("la librería {name}", "the library {name}", "la bibliothèque {name}", "die Bibliothek {name}"),
    ("las librerías {names}", "the libraries {names}", "les bibliothèques {names}", "die Bibliotheken {names}"),
    (" y ", " and ", " et ", " und "),
    # A predefined model without the libraries of GaussianOverlapAvgModel (decision 17 of the predefined models).
    ("El resultado será una configuración adaptada a partir de {preset}.",
     "The result will be a configuration adapted from {preset}.",
     "Le résultat sera une configuration adaptée à partir de {preset}.",
     "Das Ergebnis ist eine aus {preset} angepasste Konfiguration."),
    # Remembering it for a predefined model (decision 21 of the predefined models).
    ("Recordar esta decisión para {preset} en futuros AEP y rásteres",
     "Remember this decision for {preset} in future AEP and rasters",
     "Retenir cette décision pour {preset} dans les futurs AEP et rasters",
     "Diese Entscheidung für {preset} bei künftigen AEP und Rastern merken"),
    ("Con la casilla marcada, se usará CGIRotorAvg(7) sin preguntar mientras no estén disponibles estas mismas "
     "librerías y el cálculo necesite GaussianOverlapAvgModel.",
     "With the box checked, CGIRotorAvg(7) will be used without asking while these same libraries are not available "
     "and the calculation needs GaussianOverlapAvgModel.",
     "Avec la case cochée, CGIRotorAvg(7) sera utilisé sans demander tant que ces mêmes bibliothèques ne sont pas "
     "disponibles et que le calcul a besoin de GaussianOverlapAvgModel.",
     "Mit aktiviertem Kästchen wird CGIRotorAvg(7) ohne Rückfrage verwendet, solange dieselben Bibliotheken nicht "
     "verfügbar sind und die Berechnung GaussianOverlapAvgModel braucht."),
    # The information points of the group: their tooltip and accessible name, and the window.
    ("Modelos predefinidos", "Predefined models", "Modèles prédéfinis", "Vordefinierte Modelle"),
    ("Modelos de parque con la configuración de PyWake: {link}",
     "Wind farm models with the PyWake configuration: {link}",
     "Modèles de parc avec la configuration de PyWake : {link}",
     "Windparkmodelle mit der PyWake-Konfiguration: {link}"),
    ("Para cambiar valores, usa el «Modo manual».",
     "To change values, use “Manual mode”.",
     "Pour modifier des valeurs, utilisez le « Mode manuel ».",
     "Um Werte zu ändern, „Manueller Modus“ verwenden."),
    ("Elige otro modelo predefinido o usa el «Modo manual».",
     "Choose another predefined model or use “Manual mode”.",
     "Choisissez un autre modèle prédéfini ou utilisez le « Mode manuel ».",
     "Ein anderes vordefiniertes Modell wählen oder „Manueller Modus“ verwenden."),
    ("Modo manual", "Manual mode", "Mode manuel", "Manueller Modus"),
    ("General", "Overview", "Général", "Allgemein"),
    ("¿Qué define este grupo?\nCómo se calculan las pérdidas por estela entre turbinas y, si se elige, el bloqueo. "
     "Hay dos modos:\n• Modelos predefinidos: configuraciones de referencia completas, basadas en PyWake 2.6.18, "
     "que se seleccionan de una vez.\n• Modo manual: cada componente se elige por separado, incluido el "
     "bloqueo.\n\nCada pestaña de esta ventana explica un modo. Además, cada selector tiene su propio icono de "
     "información con lo que controla y la opción elegida.",
     "What does this group define?\nHow wake losses between turbines are calculated and, if chosen, blockage. There "
     "are two modes:\n• Predefined models: complete reference configurations, based on PyWake 2.6.18, selected all "
     "at once.\n• Manual mode: each component is chosen separately, blockage included.\n\nEach tab of this window "
     "explains one mode. In addition, each selector has its own information icon describing what it controls and "
     "the chosen option.",
     "Que définit ce groupe ?\nLa façon de calculer les pertes de sillage entre éoliennes et, si on le choisit, le "
     "blocage. Il y a deux modes :\n• Modèles prédéfinis : des configurations de référence complètes, fondées sur "
     "PyWake 2.6.18, sélectionnées d’un seul coup.\n• Mode manuel : chaque composant est choisi séparément, blocage "
     "compris.\n\nChaque onglet de cette fenêtre explique un mode. De plus, chaque sélecteur a sa propre icône "
     "d’information, qui décrit ce qu’il contrôle et l’option choisie.",
     "Was legt diese Gruppe fest?\nWie die Nachlaufverluste zwischen den Windturbinen und, falls gewählt, die Blockade berechnet werden. Es gibt zwei Modi:\n• Vordefinierte Modelle: vollständige Referenzkonfigurationen auf Basis von PyWake 2.6.18, die auf einmal gewählt werden.\n• Manueller Modus: Jede Komponente wird einzeln gewählt, Blockade eingeschlossen.\n\nJede Registerkarte dieses Fensters erläutert einen Modus. Zusätzlich hat jedes Auswahlfeld ein eigenes Informationssymbol, das erklärt, was es steuert und welche Option gewählt ist."),
    ("Información",
     "Information",
     "Information",
     "Information"),
    ("Información sobre los parámetros",
     "Parameter information",
     "Informations sur les paramètres",
     "Informationen zu den Parametern"),
    ("Sin información adicional para esta opción.",
     "No further information for this option.",
     "Aucune information supplémentaire pour cette option.",
     "Keine weiteren Informationen zu dieser Option."),
    # The help of the modes and of the manual mode's examples and checks.
    ("¿Qué hace este modo?\nSelecciona una configuración de referencia completa: una combinación de "
     "componentes (motor, déficit, superposición, turbulencia, promedio de rotor y suelo) y de sus "
     "parámetros, basada en las clases predefinidas de PyWake 2.6.18, con las adaptaciones que el plugin "
     "documenta en cada modelo. Los ajustes aparecen debajo, solo para consulta; el icono junto a «Modelo» "
     "explica la formulación y las referencias del modelo elegido.\n\n¿Cuándo utilizarlo?\nPara calcular con "
     "una configuración conocida o compararla con otras. Los modelos predefinidos que ofrece este plugin no "
     "incluyen bloqueo; PyWake tiene otros que sí, como FugaBlockage, que aquí no se ofrece. Para construir "
     "otras combinaciones compatibles, con o sin bloqueo, usa el «Modo manual».\n\nVersiones y alcance\nLas "
     "configuraciones se definieron con PyWake 2.6.18; el cálculo usa la versión de PyWake instalada y el "
     "resultado registra las dos. Reproducir una configuración de referencia no garantiza su precisión para "
     "un parque concreto.",
     "What does this mode do?\nIt selects a complete reference configuration: a combination of components "
     "(engine, deficit, superposition, turbulence, rotor average and ground) and their parameters, based on "
     "the predefined classes of PyWake 2.6.18, with the adaptations the plugin documents for each model. The "
     "settings are shown below, for reference only; the icon next to “Model” explains the formulation and the "
     "references of the chosen model.\n\nWhen should you use it?\nTo calculate with a known configuration or "
     "to compare it with others. The predefined models offered by this plugin do not include blockage; PyWake "
     "has others that do, such as FugaBlockage, which is not offered here. To build other compatible "
     "combinations, with or without blockage, use “Manual mode”.\n\nVersions and scope\nThe configurations "
     "were defined with PyWake 2.6.18; the calculation uses the installed PyWake version and the result "
     "records both. Reproducing a reference configuration does not guarantee its accuracy for a specific wind "
     "farm.",
     "Que fait ce mode ?\nIl sélectionne une configuration de référence complète : une combinaison de "
     "composants (moteur, déficit, superposition, turbulence, moyenne sur le rotor et sol) et de leurs "
     "paramètres, fondée sur les classes prédéfinies de PyWake 2.6.18, avec les adaptations que le plugin "
     "documente pour chaque modèle. Les réglages sont affichés ci-dessous, en lecture seule ; l’icône à côté "
     "de « Modèle » explique la formulation et les références du modèle choisi.\n\nQuand l’utiliser ?\nPour "
     "calculer avec une configuration connue ou la comparer à d’autres. Les modèles prédéfinis proposés par "
     "ce plugin n’incluent pas le blocage ; PyWake en a d’autres qui l’incluent, comme FugaBlockage, qui "
     "n’est pas proposé ici. Pour construire d’autres combinaisons compatibles, avec ou sans blocage, "
     "utilisez le « Mode manuel ».\n\nVersions et portée\nLes configurations ont été définies avec PyWake "
     "2.6.18 ; le calcul utilise la version de PyWake installée et le résultat enregistre les deux. "
     "Reproduire une configuration de référence ne garantit pas son exactitude pour un parc donné.",
     "Was macht dieser Modus?\nEr wählt eine vollständige Referenzkonfiguration: eine Kombination von "
     "Komponenten (Rechenkern, Defizit, Überlagerung, Turbulenz, Rotormittelung und Boden) und ihren "
     "Parametern, beruhend auf den vordefinierten Klassen von PyWake 2.6.18, mit den Anpassungen, die das "
     "Plugin für jedes Modell dokumentiert. Die Einstellungen werden darunter nur zur Ansicht angezeigt; das "
     "Symbol neben „Modell“ erläutert die Formulierung und die Quellen des gewählten Modells.\n\nWann ist er "
     "sinnvoll?\nUm mit einer bekannten Konfiguration zu rechnen oder sie mit anderen zu vergleichen. Die von "
     "diesem Plugin angebotenen vordefinierten Modelle enthalten keine Blockade; PyWake hat andere, die sie "
     "enthalten, etwa FugaBlockage, das hier nicht angeboten wird. Für andere kompatible Kombinationen, mit "
     "oder ohne Blockade, „Manueller Modus“ verwenden.\n\nVersionen und Geltungsbereich\nDie "
     "Konfigurationen wurden mit PyWake 2.6.18 definiert; die Berechnung verwendet die installierte "
     "PyWake-Version, und das Ergebnis vermerkt beide. Die Wiedergabe einer Referenzkonfiguration garantiert "
     "nicht ihre Genauigkeit für einen bestimmten Windpark."),
    ("¿Qué permite este modo?\nElegir por separado el motor, el déficit de estela, la superposición de "
     "estelas, la turbulencia añadida, el promedio de rotor, el suelo y el bloqueo, con sus parámetros. El "
     "programa señala las combinaciones que PyWake no puede calcular. Que una combinación se pueda calcular "
     "no la valida para un emplazamiento, y que difiera de un modelo predefinido no la hace incorrecta. El "
     "icono de cada selector explica qué controla y la opción elegida.\n\nConfiguración de estelas\nEl motor "
     "determina cómo se propagan y resuelven las interacciones entre turbinas, no la precisión física del "
     "modelo. El déficit describe la reducción de velocidad detrás de cada turbina y cómo se ensancha la "
     "estela; la superposición, cómo se combinan los déficits de velocidad de varias estelas; la turbulencia "
     "añadida estima el aumento de la intensidad de turbulencia (TI) en las estelas, que solo influye si el "
     "déficit la utiliza.",
     "What does this mode allow?\nChoosing separately the engine, the wake deficit, the wake superposition, "
     "the added turbulence, the rotor average, the ground and the blockage, with their parameters. The "
     "program flags the combinations PyWake cannot calculate. A combination that can be calculated is not "
     "thereby validated for a site, and one that differs from a predefined model is not thereby wrong. The "
     "icon of each selector explains what it controls and the chosen option.\n\nWake configuration\nThe "
     "engine determines how interactions between turbines are propagated and resolved, not the physical "
     "accuracy of the model. The deficit describes the speed reduction behind each turbine and how the wake "
     "widens; the superposition, how the velocity deficits of several wakes are combined; the added "
     "turbulence estimates the increase of the turbulence intensity (TI) in the wakes, which only matters if "
     "the deficit uses it.",
     "Que permet ce mode ?\nChoisir séparément le moteur, le déficit de sillage, la superposition des "
     "sillages, la turbulence ajoutée, la moyenne sur le rotor, le sol et le blocage, avec leurs paramètres. "
     "Le programme signale les combinaisons que PyWake ne peut pas calculer. Une combinaison calculable n’est "
     "pas pour autant validée pour un site, et une combinaison différente d’un modèle prédéfini n’est pas "
     "pour autant incorrecte. L’icône de chaque sélecteur explique ce qu’il contrôle et l’option "
     "choisie.\n\nConfiguration des sillages\nLe moteur détermine comment les interactions entre éoliennes "
     "sont propagées et résolues, pas la précision physique du modèle. Le déficit décrit la réduction de "
     "vitesse derrière chaque éolienne et l’élargissement du sillage ; la superposition, la façon de combiner "
     "les déficits de vitesse de plusieurs sillages ; la turbulence ajoutée estime l’augmentation de "
     "l’intensité de turbulence (TI) dans les sillages, qui n’a d’effet que si le déficit l’utilise.",
     "Was ermöglicht dieser Modus?\nRechenkern, Nachlaufdefizit, Überlagerung der Nachläufe, zusätzliche Turbulenz, Rotormittelung, Boden und Blockade einzeln mit ihren Parametern zu wählen. Das Programm kennzeichnet die Kombinationen, die PyWake nicht berechnen kann. Eine berechenbare Kombination ist damit nicht für einen Standort validiert, und eine Kombination, die von einem vordefinierten Modell abweicht, ist damit nicht falsch. Das Symbol jeder Auswahl erläutert, was sie steuert, und die gewählte Option.\n\nKonfiguration der Nachläufe\nDer Rechenkern bestimmt, wie die Wechselwirkungen zwischen den Windturbinen ausgebreitet und gelöst werden, nicht die physikalische Genauigkeit des Modells. Das Defizit beschreibt die Geschwindigkeitsabnahme hinter jeder Windturbine und die Aufweitung des Nachlaufs; die Überlagerung, wie die Geschwindigkeitsdefizite mehrerer Nachläufe kombiniert werden; die zusätzliche Turbulenz schätzt die Zunahme der Turbulenzintensität (TI) in den Nachläufen, die nur wirkt, wenn das Defizit sie verwendet."),


    # The help of a predefined model, and the kinds of its references.
    ("{model}\nClase de referencia de PyWake 2.6.18: {reference}",
     "{model}\nPyWake 2.6.18 reference class: {reference}",
     "{model}\nClasse de référence de PyWake 2.6.18 : {reference}",
     "{model}\nReferenzklasse von PyWake 2.6.18: {reference}"),
    ("Los ajustes aparecen debajo. Las referencias describen la formulación del déficit; el resto de la "
     "combinación es la de la clase de PyWake y no siempre procede de ellas. Reproducir esta configuración no "
     "garantiza su precisión para un parque concreto.",
     "The settings are shown below. The references describe the formulation of the deficit; the rest of the "
     "combination is that of the PyWake class and does not always come from them. Reproducing this "
     "configuration does not guarantee its accuracy for a specific wind farm.",
     "Les réglages sont affichés ci-dessous. Les références décrivent la formulation du déficit ; le reste de "
     "la combinaison est celui de la classe de PyWake et n’en provient pas toujours. Reproduire cette "
     "configuration ne garantit pas son exactitude pour un parc donné.",
     "Die Einstellungen stehen darunter. Die Quellen beschreiben die Formulierung des Defizits; die übrigen "
     "Bestandteile der Kombination entsprechen der PyWake-Klasse und stammen nicht immer aus diesen Quellen. "
     "Die Wiedergabe dieser Konfiguration garantiert nicht ihre Genauigkeit für einen bestimmten Windpark."),
    ("Referencias",
     "References",
     "Références",
     "Quellen"),
    ("Documentación de PyWake: {url}",
     "PyWake documentation: {url}",
     "Documentation de PyWake : {url}",
     "PyWake-Dokumentation: {url}"),
    ("Particularidades de esta configuración",
     "Notes on this configuration",
     "Particularités de cette configuration",
     "Besonderheiten dieser Konfiguration"),
    ("Si faltan h5py o h5netcdf y aceptas sustituir GaussianOverlapAvgModel por CGIRotorAvg(7), el cálculo "
     "deja de corresponder a esta configuración de referencia y el resultado lo registra como configuración "
     "adaptada.",
     "If h5py or h5netcdf is missing and you accept replacing GaussianOverlapAvgModel with CGIRotorAvg(7), "
     "the calculation no longer corresponds to this reference configuration and the result records it as an "
     "adapted configuration.",
     "Si h5py ou h5netcdf fait défaut et que vous acceptez de remplacer GaussianOverlapAvgModel par "
     "CGIRotorAvg(7), le calcul ne correspond plus à cette configuration de référence et le résultat "
     "l’enregistre comme configuration adaptée.",
     "Fehlt h5py oder h5netcdf und stimmen Sie zu, GaussianOverlapAvgModel durch CGIRotorAvg(7) zu ersetzen, "
     "entspricht die Berechnung nicht mehr dieser Referenzkonfiguration, und das Ergebnis vermerkt sie als "
     "angepasste Konfiguration."),
    ("Artículo",
     "Article",
     "Article",
     "Artikel"),
    ("Informe técnico",
     "Technical report",
     "Rapport technique",
     "Technischer Bericht"),

    ("Documentación técnica y código",
     "Technical documentation and code",
     "Documentation technique et code",
     "Technische Dokumentation und Code"),
    # The formulation of each predefined model.
    ("Déficit de sombrero de copa (velocidad uniforme dentro de la estela) cuyo radio crece linealmente con "
     "la distancia según k (0,1 en esta clase). La clase de PyWake lo combina con AreaOverlapAvgModel, "
     "adecuado a ese perfil, y SquaredSum.",
     "Top-hat deficit (uniform speed inside the wake) whose radius grows linearly with distance according to "
     "k (k = 0.1 in this class). The PyWake class combines it with AreaOverlapAvgModel, suited to that "
     "profile, and SquaredSum.",
     "Déficit en chapeau haut-de-forme (vitesse uniforme dans le sillage) dont le rayon croît linéairement "
     "avec la distance selon k (k = 0,1 dans cette classe). La classe de PyWake le combine avec "
     "AreaOverlapAvgModel, adapté à ce profil, et SquaredSum.",
     "Zylinderhut-Defizit (gleichförmige Geschwindigkeit im Nachlauf), dessen Radius gemäß k linear mit dem "
     "Abstand wächst (k = 0,1 in dieser Klasse). Die PyWake-Klasse kombiniert es mit AreaOverlapAvgModel, das "
     "zu diesem Profil passt, und SquaredSum."),
    ("Déficit gaussiano deducido de la conservación de masa y de cantidad de movimiento; la anchura de la "
     "estela crece linealmente según k, que es constante e independiente de la intensidad de turbulencia "
     "(TI). La clase de PyWake usa LinearSum y la velocidad efectiva (use_effective_ws = True).",
     "Gaussian deficit derived from mass and momentum conservation; the wake width grows linearly with a "
     "constant k that is independent of the turbulence intensity (TI). The PyWake class uses LinearSum and "
     "the effective wind speed (use_effective_ws = True).",
     "Déficit gaussien déduit de la conservation de la masse et de la quantité de mouvement ; la largeur du "
     "sillage croît linéairement selon k, constant et indépendant de l’intensité de turbulence (TI). La "
     "classe de PyWake utilise LinearSum et la vitesse effective (use_effective_ws = True).",
     "Gaußsches Defizit, abgeleitet aus Massen- und Impulserhaltung; die Nachlaufbreite wächst linear mit "
     "einem konstanten k, das unabhängig von der Turbulenzintensität (TI) ist. Die PyWake-Klasse verwendet "
     "LinearSum und die effektive Geschwindigkeit (use_effective_ws = True)."),

    ("Extiende el déficit gaussiano de Bastankhah a parques: la expansión depende linealmente de la "
     "intensidad de turbulencia (TI) local, k = a₁·TI + a₂, con a = [0,3837; 0,003678]. Con use_effective_ti "
     "= True, la TI local incluye la turbulencia añadida que estima CrespoHernandez. La publicación lo validó "
     "con medidas de producción y LES del parque marino Horns Rev. La clase de PyWake añade "
     "GaussianOverlapAvgModel.",
     "Extends the Bastankhah Gaussian deficit to wind farms: the expansion depends linearly on the local "
     "turbulence intensity (TI), k = a₁·TI + a₂, with a = [0.3837, 0.003678]. With use_effective_ti = True, "
     "the local TI includes the added turbulence estimated by CrespoHernandez. The publication validated it "
     "against power measurements and LES of the Horns Rev offshore wind farm. The PyWake class adds "
     "GaussianOverlapAvgModel.",
     "Étend le déficit gaussien de Bastankhah aux parcs : l’expansion dépend linéairement de l’intensité de "
     "turbulence (TI) locale, k = a₁·TI + a₂, avec a = [0,3837 ; 0,003678]. Avec use_effective_ti = True, la "
     "TI locale inclut la turbulence ajoutée qu’estime CrespoHernandez. La publication l’a validé avec des "
     "mesures de production et des LES du parc en mer de Horns Rev. La classe de PyWake ajoute "
     "GaussianOverlapAvgModel.",
     "Erweitert das gaußsche Bastankhah-Defizit auf Windparks: Die Aufweitung hängt linear von der lokalen "
     "Turbulenzintensität (TI) ab, k = a₁·TI + a₂, mit a = [0,3837; 0,003678]. Mit use_effective_ti = True "
     "enthält die lokale TI die von CrespoHernandez geschätzte zusätzliche Turbulenz. Die Veröffentlichung "
     "validierte es mit Ertragsmessungen und LES des Offshore-Windparks Horns Rev. Die PyWake-Klasse fügt "
     "GaussianOverlapAvgModel hinzu."),
    ("Extiende Niayifar con un crecimiento gradual del empuje y una anchura de estela inspirada en Shapiro et "
     "al.; la expansión depende de la intensidad de turbulencia (TI) local. Se combina con WeightedSum, la "
     "superposición que conserva la cantidad de movimiento propuesta en la misma publicación, y con un "
     "CrespoHernandez con los coeficientes de la clase de PyWake.",
     "Extends Niayifar with a gradual growth of the thrust and a wake width inspired by Shapiro et al.; the "
     "expansion depends on the local turbulence intensity (TI). It is combined with WeightedSum, the "
     "momentum-conserving superposition proposed in the same publication, and with a CrespoHernandez using "
     "the coefficients of the PyWake class.",
     "Étend Niayifar avec une croissance progressive de la poussée et une largeur de sillage inspirée de "
     "Shapiro et al. ; l’expansion dépend de l’intensité de turbulence (TI) locale. Il est combiné avec "
     "WeightedSum, la superposition conservant la quantité de mouvement proposée dans la même publication, et "
     "avec un CrespoHernandez utilisant les coefficients de la classe de PyWake.",
     "Erweitert Niayifar um ein allmähliches Anwachsen des Schubs und eine von Shapiro et al. inspirierte "
     "Nachlaufbreite; die Aufweitung hängt von der lokalen Turbulenzintensität (TI) ab. Es wird mit "
     "WeightedSum kombiniert, der impulserhaltenden Überlagerung aus derselben Veröffentlichung, und mit "
     "einem CrespoHernandez mit den Koeffizienten der PyWake-Klasse."),
    ("Perfil supergaussiano: casi de sombrero de copa en la estela cercana y gaussiano en la lejana. La "
     "anchura depende de la intensidad de turbulencia (TI) y del Ct; en la implementación de PyWake 2.6.18, "
     "el orden del perfil depende solo de la distancia. PyWake toma los parámetros calibrados de la "
     "publicación y usa LinearSum.",
     "Super-Gaussian profile: close to top-hat in the near wake and Gaussian in the far wake. The width "
     "depends on the turbulence intensity (TI) and on Ct; in the PyWake 2.6.18 implementation, the profile "
     "order depends on distance only. PyWake takes the calibrated parameters from the publication and uses "
     "LinearSum.",
     "Profil super-gaussien : proche du chapeau haut-de-forme dans le sillage proche et gaussien dans le "
     "sillage lointain. La largeur dépend de l’intensité de turbulence (TI) et du Ct ; dans l’implémentation "
     "de PyWake 2.6.18, l’ordre du profil ne dépend que de la distance. PyWake reprend les paramètres "
     "calibrés de la publication et utilise LinearSum.",
     "Supergaußsches Profil: nahezu zylinderhutförmig im Nahnachlauf und gaußförmig im Fernnachlauf. Die "
     "Breite hängt von der Turbulenzintensität (TI) und von Ct ab; in der Implementierung von PyWake 2.6.18 "
     "hängt die Ordnung des Profils nur vom Abstand ab. PyWake übernimmt die kalibrierten Parameter aus der "
     "Veröffentlichung und verwendet LinearSum."),

    # What each selector controls.
    ("El motor determina cómo se propagan y resuelven las interacciones entre turbinas; no determina por sí "
     "solo la precisión física. PropagateDownwind propaga las estelas aguas abajo y no admite bloqueo. "
     "All2AllIterative y PropagateUpDownIterative iteran y admiten bloqueo, pero solo lo calculan si además "
     "se elige un modelo de bloqueo.",
     "The engine determines how interactions between turbines are propagated and resolved; it does not "
     "determine the physical accuracy on its own. PropagateDownwind propagates the wakes downstream and does "
     "not support blockage. All2AllIterative and PropagateUpDownIterative iterate and support blockage, but "
     "only calculate it if a blockage model is also chosen.",
     "Le moteur détermine comment les interactions entre éoliennes sont propagées et résolues ; il ne "
     "détermine pas à lui seul la précision physique. PropagateDownwind propage les sillages vers l’aval et "
     "n’admet pas le blocage. All2AllIterative et PropagateUpDownIterative itèrent et admettent le blocage, "
     "mais ne le calculent que si un modèle de blocage est aussi choisi.",
     "Der Rechenkern bestimmt, wie die Wechselwirkungen zwischen den Anlagen ausgebreitet und gelöst werden; "
     "er bestimmt nicht allein die physikalische Genauigkeit. PropagateDownwind breitet die Nachläufe "
     "stromabwärts aus und unterstützt keine Blockade. All2AllIterative und PropagateUpDownIterative "
     "iterieren und unterstützen Blockade, berechnen sie aber nur, wenn zusätzlich ein Blockademodell gewählt "
     "wird."),
    ("El déficit describe cuánto se reduce la velocidad detrás de una turbina y cómo se ensancha la estela "
     "con la distancia: con una expansión constante (k) o dependiente de la intensidad de turbulencia (TI). "
     "use_effective_ws hace que escale con la velocidad efectiva que recibe la turbina en vez de con la "
     "libre; use_effective_ti, que use la TI efectiva (la ambiente más la añadida por las estelas) en vez de "
     "la ambiente. Son ajustes independientes.",
     "The deficit describes how much the wind speed decreases behind a turbine and how the wake widens with "
     "distance: with a constant expansion (k) or one that depends on the turbulence intensity (TI). "
     "use_effective_ws makes it scale with the effective wind speed reaching the turbine instead of the free "
     "one; use_effective_ti makes it use the effective TI (the ambient TI plus the turbulence added by the "
     "wakes) instead of the ambient one. They are independent settings.",
     "Le déficit décrit la diminution de la vitesse derrière une éolienne et l’élargissement du sillage avec "
     "la distance : avec une expansion constante (k) ou dépendant de l’intensité de turbulence (TI). "
     "use_effective_ws le met à l’échelle avec la vitesse effective qui atteint l’éolienne au lieu de la "
     "vitesse libre ; use_effective_ti lui fait utiliser la TI effective (la TI ambiante plus la turbulence "
     "ajoutée par les sillages) au lieu de la TI ambiante. Ce sont des réglages indépendants.",
     "Das Defizit beschreibt, wie stark die Windgeschwindigkeit hinter einer Windturbine abnimmt und wie sich der Nachlauf mit dem Abstand aufweitet: mit konstanter Aufweitung (k) oder abhängig von der Turbulenzintensität (TI). use_effective_ws lässt es mit der effektiven Windgeschwindigkeit an der Windturbine statt mit der freien Windgeschwindigkeit skalieren; use_effective_ti lässt es die effektive TI (Umgebungs-TI plus die durch die Nachläufe zusätzliche Turbulenz) statt der Umgebungs-TI verwenden. Beide Einstellungen sind unabhängig."),
    ("Evalúa un déficit representativo sobre el área barrida por el rotor que recibe la estela. «Ninguno» y "
     "RotorCenter usan el centro; CGIRotorAvg (4, 7, 9 o 21 puntos) y EqGridRotorAvg muestrean puntos del "
     "rotor; GaussianOverlapAvgModel integra el solape con una estela gaussiana y AreaOverlapAvgModel calcula "
     "la fracción cubierta por una estela de sombrero de copa. Más puntos suelen mejorar la estimación del "
     "promedio, con más coste y según su distribución, pero no corrigen las hipótesis del modelo; ningún "
     "número de puntos es suficiente en general.",
     "It evaluates a representative deficit over the swept area of the rotor reached by the wake. “None” and "
     "RotorCenter use the centre; CGIRotorAvg (4, 7, 9 or 21 points) and EqGridRotorAvg sample points on the "
     "rotor; GaussianOverlapAvgModel integrates the overlap with a Gaussian wake and AreaOverlapAvgModel "
     "calculates the fraction covered by a top-hat wake. More points usually improve the estimate of the "
     "average, at a higher cost and depending on their distribution, but they do not correct the assumptions "
     "of the model; no number of points is sufficient in general.",
     "Évalue un déficit représentatif sur la surface balayée par le rotor atteint par le sillage. « Aucun » "
     "et RotorCenter utilisent le centre ; CGIRotorAvg (4, 7, 9 ou 21 points) et EqGridRotorAvg "
     "échantillonnent des points du rotor ; GaussianOverlapAvgModel intègre le recouvrement avec un sillage "
     "gaussien et AreaOverlapAvgModel calcule la fraction couverte par un sillage en chapeau haut-de-forme. "
     "Davantage de points améliorent généralement l’estimation de la moyenne, mais augmentent le coût et leur "
     "effet dépend de leur répartition ; ils ne corrigent pas les hypothèses du modèle ; aucun nombre de "
     "points n’est suffisant en général.",
     "Wertet ein repräsentatives Defizit über die überstrichene Fläche des Rotors aus, den der Nachlauf "
     "erreicht. „Keines“ und RotorCenter verwenden die Mitte; CGIRotorAvg (4, 7, 9 oder 21 Punkte) und "
     "EqGridRotorAvg tasten Punkte des Rotors ab; GaussianOverlapAvgModel integriert die Überdeckung mit "
     "einem gaußschen Nachlauf, und AreaOverlapAvgModel berechnet den von einem Zylinderhut-Nachlauf "
     "bedeckten Anteil. Mehr Punkte verbessern meist die Schätzung des Mittelwerts, bei höherem Aufwand und "
     "abhängig von ihrer Verteilung, korrigieren aber nicht die Annahmen des Modells; keine Punktzahl ist "
     "allgemein ausreichend."),
    ("Mirror refleja las turbinas en el plano del suelo para imponer una superficie ideal, sin velocidad "
     "normal a ella; no representa rugosidad, oleaje, orografía ni estabilidad atmosférica. Según la "
     "documentación de PyWake, muchos modelos de estela se calibraron con el efecto del suelo incluido y "
     "añadirlo puede contarlo dos veces; otros lo usan expresamente, como el modelo predefinido TurbOPark. "
     "MultiMirror añade un segundo plano de reflexión en altura (mirror_height) para representar el bloqueo "
     "adicional de una inversión térmica baja e intensa; su altura debe justificarse con datos del perfil "
     "atmosférico.",
     "Mirror reflects the turbines in the ground plane to impose an ideal surface, with no velocity normal to "
     "it; it does not represent roughness, waves, orography or atmospheric stability. According to the PyWake "
     "documentation, many wake models were calibrated with the ground effect included and adding it may count "
     "it twice; others use it explicitly, such as the TurbOPark predefined model. MultiMirror adds a second "
     "reflection plane aloft (mirror_height) to represent the additional blockage of a low, strong "
     "temperature inversion; its height must be justified with atmospheric profile data.",
     "Mirror réfléchit les éoliennes dans le plan du sol pour imposer une surface idéale, sans vitesse "
     "normale à celle-ci ; il ne représente ni la rugosité, ni la houle, ni l’orographie, ni la stabilité "
     "atmosphérique. Selon la documentation de PyWake, de nombreux modèles de sillage ont été calibrés avec "
     "l’effet du sol inclus et l’ajouter peut le compter deux fois ; d’autres l’utilisent explicitement, "
     "comme le modèle prédéfini TurbOPark. MultiMirror ajoute un second plan de réflexion en altitude "
     "(mirror_height) pour représenter le blocage supplémentaire d’une inversion thermique basse et intense ; "
     "sa hauteur doit être justifiée par des données de profil atmosphérique.",
     "Mirror spiegelt die Windturbinen an der Bodenebene, um eine ideale Oberfläche ohne Normalgeschwindigkeit vorzugeben; es bildet weder Rauigkeit noch Seegang, Orografie oder atmosphärische Stabilität ab. Laut PyWake-Dokumentation wurden viele Nachlaufmodelle mit eingeschlossenem Bodeneffekt kalibriert, und ihn hinzuzufügen kann ihn doppelt zählen; andere verwenden ihn ausdrücklich, wie das vordefinierte Modell TurbOPark. MultiMirror fügt eine zweite Spiegelebene in der Höhe (mirror_height) hinzu, um die zusätzliche Blockade einer niedrigen, starken Temperaturinversion abzubilden; ihre Höhe muss mit Daten zum atmosphärischen Profil begründet werden."),
    ("Indica cómo se combinan los déficits de velocidad de varias estelas que alcanzan una turbina; no suma "
     "pérdidas de energía. Las reglas parten de hipótesis distintas y no son intercambiables. La "
     "documentación de PyWake recomienda en general LinearSum con use_effective_ws = True, para evitar "
     "velocidades negativas, y suele usar SquaredSum con déficits escalados con la velocidad libre. La regla "
     "de un modelo predefinido no es la única admisible; que el programa acepte una combinación indica que se "
     "puede calcular, no que sus hipótesis sean coherentes ni que esté validada.",
     "It sets how the velocity deficits of several wakes reaching a turbine are combined; it does not add up "
     "energy losses. The rules rest on different assumptions and are not interchangeable. The PyWake "
     "documentation generally recommends LinearSum with use_effective_ws = True, to avoid negative wind "
     "speeds, and usually uses SquaredSum with deficits scaled with the free wind speed. The rule of a "
     "predefined model is not the only admissible one; the program accepting a combination means it can be "
     "calculated, not that its assumptions are consistent or that it is validated.",
     "Indique comment combiner les déficits de vitesse de plusieurs sillages qui atteignent une éolienne ; la "
     "superposition n’additionne pas des pertes d’énergie. Les règles reposent sur des hypothèses différentes "
     "et ne sont pas interchangeables. La documentation de PyWake recommande en général LinearSum avec "
     "use_effective_ws = True, pour éviter des vitesses négatives, et utilise habituellement SquaredSum avec "
     "des déficits mis à l’échelle avec la vitesse libre. La règle d’un modèle prédéfini n’est pas la seule "
     "admissible ; que le programme accepte une combinaison signifie qu’elle est calculable, non que ses "
     "hypothèses sont cohérentes ni qu’elle est validée.",
     "Legt fest, wie die Geschwindigkeitsdefizite mehrerer Nachläufe, die eine Windturbine erreichen, kombiniert werden; Energieverluste werden nicht addiert. Die Regeln beruhen auf unterschiedlichen Annahmen und sind nicht austauschbar. Die PyWake-Dokumentation empfiehlt allgemein LinearSum mit use_effective_ws = True, um negative Geschwindigkeiten zu vermeiden, und verwendet SquaredSum meist mit Defiziten, die mit der freien Windgeschwindigkeit skaliert werden. Die Regel eines vordefinierten Modells ist nicht die einzig zulässige; dass das Programm eine Kombination akzeptiert, heißt, dass sie berechenbar ist, nicht dass ihre Annahmen konsistent sind oder dass sie validiert ist."),
    ("El bloqueo es el efecto de inducción de las turbinas sobre el flujo, sobre todo aguas arriba del rotor; "
     "es distinto de las estelas aguas abajo y del relieve. «Ninguno»: no se calcula. "
     "SelfSimilarityDeficit2020 representa la inducción cerca de cada turbina; no basta por sí solo para la "
     "respuesta atmosférica de un gran parque ni para los efectos del terreno. Comparar con VortexCylinder u "
     "otros modelos sirve para estudiar la sensibilidad; VortexDipole se aproxima al cilindro solo en campo "
     "lejano (r/R > 6, según PyWake). Fuga depende de tablas LUT adecuadas, calculadas previamente con un "
     "modelo RANS linealizado, y no está en el catálogo del plugin.",
     "Blockage is the induction effect of the turbines on the flow, mainly upstream of the rotor; it differs "
     "from the wakes downstream and from terrain effects. “None”: it is not calculated. "
     "SelfSimilarityDeficit2020 represents the induction near each turbine; on its own it is not enough for "
     "the atmospheric response of a large wind farm or for terrain effects. Comparing with VortexCylinder or "
     "other models helps study the sensitivity; VortexDipole approximates the cylinder only in the far field "
     "(r/R > 6, according to PyWake). Fuga depends on suitable LUT tables, computed beforehand with a "
     "linearised RANS model, and is not in the plugin's catalogue.",
     "Le blocage est l’effet d’induction des éoliennes sur l’écoulement, surtout en amont du rotor ; il se "
     "distingue des sillages en aval et des effets du relief. « Aucun » : il n’est pas calculé. "
     "SelfSimilarityDeficit2020 représente l’induction près de chaque éolienne ; à lui seul, il ne suffit ni "
     "pour la réponse atmosphérique d’un grand parc ni pour les effets du relief. Comparer avec "
     "VortexCylinder ou d’autres modèles permet d’étudier la sensibilité ; VortexDipole n’approche le "
     "cylindre qu’en champ lointain (r/R > 6, selon PyWake). Fuga dépend de tables LUT adaptées, calculées au "
     "préalable avec un modèle RANS linéarisé, et ne figure pas dans le catalogue du plugin.",
     "Die Blockade ist die Induktionswirkung der Windturbinen auf die Strömung, vor allem stromaufwärts des Rotors; sie unterscheidet sich vom Nachlauf stromabwärts und von Geländeeffekten. „Keines“: Sie wird nicht berechnet. SelfSimilarityDeficit2020 bildet die Induktion nahe jeder Windturbine ab; allein reicht es weder für die atmosphärische Reaktion eines großen Windparks noch für Geländeeffekte. Ein Vergleich mit VortexCylinder oder anderen Modellen dient der Sensitivitätsuntersuchung; VortexDipole nähert den Zylinder nur im Fernfeld an (r/R > 6, laut PyWake). Fuga hängt von geeigneten LUT-Tabellen ab, die vorab mit einem linearisierten RANS-Modell berechnet werden, und ist nicht im Katalog des Plugins."),
    ("Indica cómo se combinan los déficits de bloqueo de varias turbinas. Es independiente de la "
     "superposición de estelas y puede usar la misma regla. Algunas reglas no se pueden calcular para el "
     "bloqueo: lo indica la ayuda de cada opción.",
     "It sets how the blockage deficits of several turbines are combined. Blockage superposition is "
     "independent of wake superposition and may use the same rule. Some rules cannot be calculated for "
     "blockage, as the help of each option says.",
     "Indique comment combiner les déficits de blocage de plusieurs éoliennes. La superposition du blocage "
     "est indépendante de celle des sillages et peut utiliser la même règle. Certaines règles ne peuvent pas "
     "être calculées pour le blocage : l’aide de chaque option l’indique.",
     "Legt fest, wie die Blockadedefizite mehrerer Windturbinen kombiniert werden. Die Überlagerung der Blockade ist von der Überlagerung der Nachläufe unabhängig und kann dieselbe Regel verwenden. Einige Regeln lassen sich für die Blockade nicht berechnen; das nennt die Hilfe der jeweiligen Option."),
    ("Estima la turbulencia añadida por las estelas; la intensidad de turbulencia (TI) efectiva combina la "
     "ambiente y la añadida. Solo cambia el déficit si este la utiliza: un déficit cuya expansión depende de "
     "la TI, con use_effective_ti = True. Con una expansión constante (k fijo), la turbulencia se calcula "
     "pero no modifica las pérdidas.",
     "It estimates the turbulence added by the wakes; the effective turbulence intensity (TI) combines the "
     "ambient TI and the added turbulence. It only changes the deficit if the deficit uses it: a deficit "
     "whose expansion depends on TI, with use_effective_ti = True. With a constant expansion (fixed k), the "
     "turbulence is calculated but does not change the losses.",
     "Estime la turbulence ajoutée par les sillages ; l’intensité de turbulence (TI) effective combine la TI "
     "ambiante et la turbulence ajoutée. Elle ne modifie le déficit que si celui-ci l’utilise : un déficit "
     "dont l’expansion dépend de la TI, avec use_effective_ti = True. Avec une expansion constante (k fixe), "
     "la turbulence est calculée mais ne modifie pas les pertes.",
     "Schätzt die durch die Nachläufe zusätzliche Turbulenz; die effektive Turbulenzintensität (TI) "
     "kombiniert die Umgebungs-TI und die zusätzliche Turbulenz. Sie ändert das Defizit nur, wenn es sie "
     "verwendet: ein Defizit, dessen Aufweitung von der TI abhängt, mit use_effective_ti = True. Bei "
     "konstanter Aufweitung (festes k) wird die Turbulenz berechnet, ändert aber die Verluste nicht."),
    ("Opción seleccionada: {name}\nDetalle del modelo:",
     "Selected option: {name}\nModel details:",
     "Option sélectionnée : {name}\nDétails du modèle :",
     "Ausgewählte Option: {name}\nModelldetails:"),
    ("Ver explicación",
     "Show explanation",
     "Afficher l’explication",
     "Erklärung anzeigen"),
)

SOURCES = tuple(r[0] for r in _ROWS)
TRANSLATIONS = {lang: {r[0]: r[i] for r in _ROWS} for i, lang in ((1, "en"), (2, "fr"), (3, "de"))}


def register_wake_group_translations():
    from ..i18n import register_language
    for language, mapping in TRANSLATIONS.items():
        register_language(language, mapping, {})
