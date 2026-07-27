# Curvas de aerogeneradores incluidas

El catálogo separa explícitamente tres niveles de calidad:

1. **Referencia pública**: datos tabulares o ecuaciones publicadas para casos de referencia abiertos. Se incluye la fuente en `builtin_turbine_candidates.csv`.
2. **Aproximación basada en ficha pública**: el nombre, la potencia, el rotor y los puntos operativos disponibles se anclan a una ficha pública del fabricante. La forma de la curva de potencia y CT la genera VelantisWind y no es OEM ni certificada.
3. **Aproximada genérica**: clases neutrales por potencia y diámetro generadas mediante un modelo paramétrico físicamente plausible. No representan un fabricante concreto.

## Referencias públicas empaquetadas

- V80-2.0 de Horns Rev 1, tal como se distribuye en PyWake.
- IEA37 3,35 MW del benchmark de optimización de layouts.
- IEA-10.0-198-RWT, tabla pública `performance_ccblade.dat`.
- IEA-15-240-RWT, tabla pública `Rotor Performance`.

## Aproximaciones ancladas a ficha

- Vestas V150-4.5 MW y V163-4.5 MW.
- Siemens Gamesa SG 5.0-145 y SG 7.0-170.
- GE Vernova 6.1-158.
- Nordex N163/5.X, N175/6.X y N133/4.8.

Cada entrada muestra en QGIS su calidad, fuente y advertencia. Los ratings elegidos dentro de rangos comerciales, las velocidades nominales, los CT y cualquier punto no publicado están documentados como hipótesis de screening.

## Uso técnico

Antes de emitir un resultado de ingeniería, sustituye las aproximaciones por la curva aplicable al proyecto y revisa densidad del aire, modo de operación, versión del controlador y ajustes específicos del emplazamiento. Una curva pública de referencia tampoco equivale necesariamente a una curva contractual OEM. Si el usuario edita una curva del catálogo, VelantisWind la marca como `user_edited`.
