# Capítulo 1: qué cambió y por qué

Grupo 3, MII712 · 9 de octubre de 2026

La versión 4 del Capítulo 1 corrige cinco errores de datos o de método de la versión entregada y agrega el tratamiento de la marea astronómica, que el texto original no consideraba. El objetivo general, los objetivos específicos, la ventana 2000-2024, la partición temporal, los cuatro modelos y las metas de la Tabla 1 se mantienen.

## Resumen de los cambios

| Sección | Capítulo entregado | Versión 4 | Motivo |
|---|---|---|---|
| Tabla 5, REDMAR | Bonanza desde 1992; Huelva desde 1996 | Huelva desde 2007; Bonanza y Tarifa desde 2009 | Fechas reales del servidor; faltaba Tarifa |
| Tabla 5, fuentes | SIMAR da oleaje y viento; Copernicus, nivel y corrientes | Copernicus da las cuatro variables con una misma malla; SIMAR queda como contraste | Portus no permite descarga automática |
| Nivel del mar | No se definía | No astronómico: se resta la marea por análisis armónico y se usa el percentil 95 del máximo diario | La marea dominaba el indicador |
| Corrientes | Rapidez total | Se resta la corriente de marea | La marea explicaba hasta el 83 % de la rapidez en el Estrecho |
| Marea astronómica | No existía | Tres capas: se resta, cuenta como coincidencia con temporales y entra como previsión al modelo | Separa lo fijo de lo que daña |
| Indicadores del IEECC | Cuatro | Cinco: se suman los días de temporal en pleamar viva | El daño se concentra cuando un temporal coincide con la pleamar |
| Tramos | Aproximadamente 10 km, sin justificar | 23 tramos de 10 km, justificados por resolución de datos y coherencia de los temporales | Cada tramo tiene datos propios |
| Validación del índice | No había | Contraste con daños documentados por temporales y tendencias por tramo | Validez frente a impactos reales |
| OE3, pregunta | No había | Pregunta e hipótesis: ¿hay capacidad predictiva más allá de la persistencia? | El resultado pasa a ser una respuesta |
| OE3, selección | Mejor modelo en la prueba | Mejor en validación y que supere a la persistencia en NDCG y en sensibilidad; resultado final en prueba | No contaminar la evaluación final |
| OE3, estadística | Valores puntuales | Intervalos de confianza del 95 % y análisis de los tramos que cambian de clase | Diferencias chicas pueden ser ruido |
| OE4, panel | Cuatro componentes | Suma una alerta del trimestre siguiente | Distinguir prioridad de alerta |
| Alcance | Exposición, no vulnerabilidad | Agrega que el índice mide variabilidad relativa y no la tendencia del cambio climático | Acota lo que promete la introducción |

## Por qué la versión 4 es más robusta

1. **El índice mide temporales y no la geografía de la marea.** En la versión entregada, el máximo del nivel del mar lo ponía la marea astronómica, mayor en Huelva y menor en Tarifa. Ese indicador iba en contra del oleaje (correlación −0,12). Sin marea, el nivel del mar sube junto con el oleaje en los temporales (correlación 0,71).
2. **La marea se usa donde sí importa.** El daño se concentra cuando un temporal coincide con la pleamar viva. La versión 4 lo mide como quinto indicador y usa la marea del trimestre siguiente, que se conoce de antemano, como entrada del modelo.
3. **Los mareógrafos la confirman.** El nivel del mar sin marea del reanálisis coincide con REDMAR: correlación de 0,93 en Huelva, 0,88 en Bonanza y 0,81 en Tarifa.
4. **Los daños reales la confirman.** En los tramos con obras de emergencia por temporales (2015, 2016, 2018 y 2024), el trimestre del daño quedó en el percentil 86 de la historia del propio tramo (Emma, 2018: percentil 99). La probabilidad de que eso ocurra por azar es menor a 1 en 1.000.
5. **Cada tramo tiene datos propios.** Con 40 puntos, dos pares de tramos compartían la misma celda. Con 23 tramos de 10 km, cada uno tiene la suya, y dividir más fino no agrega información porque los temporales afectan a decenas de kilómetros a la vez.
6. **La evaluación de modelos es más seria.** El modelo se elige en validación con las dos métricas de la Tabla 1 y la prueba se informa con intervalos de confianza. LambdaMART supera a la persistencia en exactitud balanceada (0,635 contra 0,595) y en sensibilidad de la clase alta (0,677 contra 0,646), y queda apenas bajo en NDCG (0,954 contra 0,959). Ninguna diferencia es significativa.
7. **Responde las preguntas que haría un evaluador:** cómo se trata la marea, si el índice tiene que ver con daños reales, si las diferencias entre modelos son ruido y por qué 10 km.

## ¿La versión entregada habría sesgado los resultados?

Sí, y en una dirección engañosa: el índice habría parecido más robusto de lo que es y los modelos, peores de lo que son.

- **La marea fijaba quién estaba en rojo.** Con la marea dentro, el tramo explicaba el 92 % de las diferencias del índice dentro de cada trimestre; sin ella, el 66 %. Tarifa y Conil quedaban casi siempre en rojo en buena parte por la corriente de marea del Estrecho.
- **Robustez inflada en el OE2.** Con la marea, 8 de 10 escenarios de sensibilidad cumplían la meta. Esa estabilidad venía de la marea, que no cambia.
- **Persistencia artificialmente imbatible en el OE3.** Si el orden de los tramos es casi fijo, repetir el trimestre anterior acierta casi siempre (NDCG 0,994) y todos los modelos quedaban como significativamente peores.
- **Elegir el modelo en la prueba** habría inflado el desempeño informado.
- **Datos repetidos y sin intervalos.** Con dos pares de tramos compartiendo celda y sin intervalos de confianza, diferencias de 0,001 podían decidir el modelo.

Las fechas de REDMAR y el rol de SIMAR eran errores del texto, no del cálculo.

## Lo que no cambia

- Objetivo general y los cuatro objetivos específicos.
- Área de estudio y tramos de aproximadamente 10 km.
- Ventana 2000-2024 y partición 2000-2018 / 2019-2021 / 2022-2024.
- Los cuatro modelos frente a persistencia y clase mayoritaria.
- Métricas y metas de la Tabla 1, con el plan previsto si ningún modelo supera a la persistencia.
- Panel con ranking, mapa semáforo, mapa de calor y ficha por tramo con SHAP.

## Lo que cuesta

- **Sensibilidad a los pesos:** 3 de los 10 escenarios originales cumplen la meta. Los saltos de alta a baja no pasan de 5,3 %.
- **El ranking entre tramos explica poco dónde ocurre el daño:** el 31 % de los tramos dañados estaba en prioridad alta (el azar daría 33 %). El lugar del daño depende también de la vulnerabilidad de cada frente, que el índice no mide.
- **Ningún modelo supera a la persistencia con significancia estadística.** La persistencia queda como referencia operativa, como prevé la Tabla 1.

## Pendiente del grupo

- [ ] Aprobar la versión 4 como base del proyecto.
- [ ] Aprobar el paso de cuatro a cinco indicadores.
- [ ] Confirmar Copernicus como fuente de oleaje y viento, con SIMAR como contraste.
- [ ] Revisar si hay límite de páginas (la versión 4 tiene 20).
