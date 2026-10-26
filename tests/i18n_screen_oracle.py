"""Deliberately lexical oracle, independent of translation tables and their inverse maps.

Only language-exclusive markers belong here: French «é», «de», «la», «un»,
«avec» are not Spanish leaks. Exceptions remove exact fragments at exact paths,
never a whole widget subtree or a language-wide word.
"""
from html import unescape
from html.parser import HTMLParser
import re

# Whole words: avoid treating e.g. the German «gestartet» as Spanish «esta».
SPANISH = frozenset('''abrir aceptar actualizar aerogenerador aerogeneradores ajustes altura alturas ancho archivo archivos
asignar ayuda buje buscar cada calcular calculado cambiar cambios cancelar capa capas cargar cerrar columna columnas
comprobar con configurado coordenadas crear creado cuando curva curvas desde detectar devuelve distancia elegir
el eliminar emplazamiento entrada entradas entre error está este esta estos estas estela estelas exportar faltan
fuente fuentes generado guardar hay hasta idioma informe inicio la las leer leyenda limpiar longitud los mapa
modelo modelos mostrar muestra neto ninguna ninguno nombre nombres nueva nuevo ocultar opciones pantalla parque
para pero por potencia promedio prueba puntos que quitar ruido salida seleccionar seleccionado seleccionada
seleccionados seleccionadas separador sin sobre suelo sus tabla tamaño todos todas turbina turbinas usar utiliza
valor valores velocidad velocidades viento vuelve añadir año español cálculo configuración diámetro dirección
energía máximo máxima mínimo mínima módulo número pérdida pérdidas parámetros perímetro ráster receptor receptores
resumen sección según separación sí sólo también último vacía vacío válida válido definición fichero ficheros
estado terreno umbral ponderado apantallados obstáculo obstáculos superposición bloqueo advertencia advertencias
pendiente pendientes origen negro blanca desplegar plegar manualmente
mientras mediante disponible disponibles fuera dentro borrado ventana conserva ambas ambos alguna alguno antes
después entonces tiene tienen obtiene obtenido superior inferior inversa inverso actual
resultado resultados paso pasos aviso avisos lista listas casilla casillas interfaz herramienta herramientas
opción cargado cargada cargados selección aplicar aplicada aplica aplicado detectado detectada borrar faltante
aumentar disminuye contiene contienen relativo relativa toda todo anterior siguiente izquierda derecha arriba abajo
carpeta carpetas vaciar porque aunque además siempre nunca tampoco necesario necesaria necesarios existente
importado calcula calculan calculada calculadas configurar configuradas recomendado recomendada predeterminado
predeterminada máximos máximas mínimos mínimas mes meses horario horas anual años semana hora calculando finalizado
completado límites límite frecuencia frecuencias filas fila texto textos pestaña pestañas
'''.split())
# Ambiguous words are valid in the target language, not exceptions.
SHARED = {
    'en': frozenset('error superior inferior actual'.split()),
    'de': frozenset('leer'.split()),
    'fr': frozenset('''la las un con entre distance longitude latitude para par que sobre superposition
                    source sources configuration direction variable inverse information disponible disponibles nombre'''.split()),
}
ENGLISH = frozenset('''the and with without from into for this that these those your their each should must can cannot
could would will only before after when where which while using used use choose select selected selection available
unavailable enabled disabled settings cancel close open save load export results result summary report name names
height width length speed power wind wake wakes loss losses gross net free stream turbine turbines model models
layer layers receiver receivers source sources ground grid grids layout layouts hub array arrays none true false
nearest linear speedup cut in out top scroll left right target screening engine blockage averaging mean
ambient effective turbulence year english predefined engineering farm
cluster clusters input output directory file files folder help tooltip placeholder default custom include column
columns show hide reset clear remove add create update refresh missing unknown fixed calculated computation
noise shadow flicker click check checked project language start stop apply warning failed failure not yes is are
white paper plugin email download website licensed public reference offshore onshore matching
point multipoint polygon linestring site draft removed preset
'''.split())
# «rotor», «simple» and «software» are also Spanish words.
# «in», «out», «is» are codes as well; their exact occurrences need scoped exceptions.

class _Plain(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.ignored = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('style', 'script'):
            self.ignored += 1
    def handle_endtag(self, tag):
        if tag in ('style', 'script'):
            self.ignored -= 1
    def handle_data(self, data):
        if not self.ignored:
            self.parts.append(data)


def plain(text):
    # Inequalities such as r/R > 6 are text, not markup.
    if re.search(r'</?(?:html|p|b|div|span|br|table|a|small|strong|h[1-6])\b', text, re.I):
        parser = _Plain()
        parser.feed(text)
        return ' '.join(parser.parts)
    return unescape(text)


def foreign_markers(text, lang):
    text = plain(text)
    words = set(re.findall(r'[^\W\d_]+', text.casefold()))
    if lang == 'es':
        return sorted(words & ENGLISH)
    words &= SPANISH - SHARED[lang]
    accents = r'[ñáíóú¿¡]' if lang == 'fr' else r'[ñáéíóú¿¡]'
    return sorted(words | set(re.findall(accents, text.casefold())))
