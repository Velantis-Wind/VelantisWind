"""Translations for resource-coverage notices in the Energy results."""

TRANSLATIONS = {
    "en": {
        "Cálculo parcial: {inside} de {total} turbinas dentro del recurso; {skipped} fuera. El AEP, la potencia instalada y las pérdidas corresponden solo a las turbinas calculadas.": "Partial calculation: {inside} of {total} turbines inside the wind resource; {skipped} outside. AEP, installed capacity and losses only refer to calculated turbines.",
        "Turbinas excluidas por modelo: {details}.": "Excluded turbines by model: {details}.",
        "Las turbinas no calculadas pueden conservar resultados anteriores en su capa; esos valores no pertenecen a esta simulación.": "Turbines not calculated may retain previous results in their layer; those values do not belong to this simulation.",
        "Aviso de cobertura del recurso:": "Resource coverage warning:",
    },
    "fr": {
        "Cálculo parcial: {inside} de {total} turbinas dentro del recurso; {skipped} fuera. El AEP, la potencia instalada y las pérdidas corresponden solo a las turbinas calculadas.": "Calcul partiel : {inside} éoliennes sur {total} dans la zone de ressource ; {skipped} hors zone. L’AEP, la puissance installée et les pertes ne concernent que les éoliennes calculées.",
        "Turbinas excluidas por modelo: {details}.": "Éoliennes exclues par modèle : {details}.",
        "Las turbinas no calculadas pueden conservar resultados anteriores en su capa; esos valores no pertenecen a esta simulación.": "Les éoliennes non calculées peuvent conserver d’anciens résultats dans leur couche ; ces valeurs ne correspondent pas à cette simulation.",
        "Aviso de cobertura del recurso:": "Avertissement de couverture de la ressource :",
    },
    "de": {
        "Cálculo parcial: {inside} de {total} turbinas dentro del recurso; {skipped} fuera. El AEP, la potencia instalada y las pérdidas corresponden solo a las turbinas calculadas.": "Teilberechnung: {inside} von {total} Windturbinen innerhalb des Windressourcengebiets; {skipped} außerhalb. AEP, installierte Leistung und Verluste beziehen sich nur auf berechnete Windturbinen.",
        "Turbinas excluidas por modelo: {details}.": "Ausgeschlossene Windturbinen nach Modell: {details}.",
        "Las turbinas no calculadas pueden conservar resultados anteriores en su capa; esos valores no pertenecen a esta simulación.": "Nicht berechnete Windturbinen können ältere Ergebnisse in ihrem Layer behalten; diese Werte gehören nicht zu dieser Simulation.",
        "Aviso de cobertura del recurso:": "Hinweis zur Ressourcenabdeckung:",
    },
}


def register_coverage_translations():
    from ...i18n import register_language
    for language, mapping in TRANSLATIONS.items():
        register_language(language, mapping, mapping)
