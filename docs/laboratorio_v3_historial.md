# Laboratorio v2 (Capítulo 1, versión 2)

Rama paralela a `main` para probar lo que agrega la versión 2 del Capítulo 1 sin tocar la versión 1. Corrida del 9 de octubre de 2026, mismos datos, misma partición (2000-2018 / 2019-2021 / 2022-2024) y mismos modelos.

## Qué cambia respecto de la versión 1

| Tema | Versión 1 (`main`) | Laboratorio v2 |
|---|---|---|
| Nivel del mar | No astronómico | No astronómico (igual) |
| Corrientes | Rapidez horaria total (incluye marea) | Rapidez del residuo: se quitan la corriente de marea y la circulación media (UTide 2D, ajuste 2000-2018) |
| Validación del nivel | Media diaria del nivel total | Residuo meteorológico del reanálisis contra el de los mareógrafos |
| Comparación de modelos | Valor puntual | Intervalo de confianza del 95 % por bootstrap en bloques de trimestres |
| Tendencias | No había | Mann-Kendall y pendiente de Sen por tramo e indicador |
| Alerta del panel | No había | Mareas vivas previstas para t+1 y estación de temporales |

Código nuevo: `src/marea_v2.py` y `src/analisis.py`. Interruptor: `CORRIENTE_INDICE` en `config.py`.

## Resultados

| Indicador | Versión 1 | Laboratorio v2 |
|---|---|---|
| Rapidez de corriente que se explica por marea y circulación media | (no se quitaba) | 42 % de media; entre 75 % y 90 % en ocho tramos de Sancti Petri a Tarifa |
| Escenarios de sensibilidad que cumplen (< 20 %) | 8 de 10 | 2 de 10 |
| Tramos que cambian de clase entre trimestres | 29 % | 38 % |
| Persistencia en prueba (NDCG@10 / sensibilidad alta) | 0,994 / 0,936 | 0,979 / 0,865 |
| Mejor modelo en prueba (NDCG@10 / sensibilidad alta) | Random Forest 0,980 / 0,897 | LambdaMART 0,967 / 0,859 |
| ¿Algún modelo es significativamente peor que la persistencia en ambas métricas? | Todos | Ninguno de los finalistas: Random Forest y LambdaMART quedan empatados con ella en ambas (intervalos que incluyen el cero); XGBoost empata solo en NDCG |
| Acierto cuando el tramo cambia de clase | 45 % a 51 % | 39 % a 41 % |

Validación del residuo meteorológico contra REDMAR (máximo diario): correlación 0,93 en Huelva, 0,88 en Bonanza y 0,81 en Tarifa; entre 89 % y 100 % de los días extremos del mareógrafo (sobre su percentil 99) también son extremos en el reanálisis.

Tendencias 2000-2024: el viento baja en 10 de 40 tramos (mediana −0,23 m/s por década); oleaje y nivel del mar no tienen tendencia significativa salvo en un tramo cada uno.

## Lectura

- En la versión 1, buena parte del rojo de Tarifa y Conil venía de la marea y de la circulación permanente del Estrecho, que no son exposición a temporales. Quitarlas hace el índice físicamente más honesto.
- El costo es que el índice queda más sensible a los pesos (2 de 10 escenarios) y cambia más entre trimestres. Ahora mide variabilidad meteorológica, que es menos estable que la geografía.
- La persistencia pierde ventaja. Con intervalos de confianza, Random Forest y LambdaMART ya no se distinguen de ella en NDCG ni en sensibilidad de la clase alta. La hipótesis nula del Capítulo 1 sigue sin rechazarse, pero ahora por empate y no por derrota clara.
- La alerta de mareas vivas aporta poco: la pleamar máxima de un trimestre varía solo unos centímetros entre años. La marea pesa más como diferencia fija entre tramos (1,7 m en Huelva contra 0,7 m en Tarifa) que como señal del trimestre siguiente. La parte útil de la alerta es la estación de temporales: en la prueba, el 98 % de los trimestres en alerta alta tuvo temporal, contra 21 % de los sin alerta.

## Ajuste de robustez (segunda corrida del laboratorio)

Para bajar la sensibilidad a los pesos se probaron dos cambios que se justifican por robustez, no por la meta: el nivel del mar con el percentil 95 del máximo diario (igual que oleaje y viento) en vez del máximo del trimestre, y la normalización por percentiles en vez de mínimo y máximo.

| Indicador | v2 inicial | v2 + nivel p95 + percentiles | v2 + nivel p95 (configuración final) |
|---|---|---|---|
| Escenarios de sensibilidad que cumplen | 2 de 10 | 4 de 10 (*) | 3 de 10 |
| Peor escenario | 43,4 % | 37,3 % | 42,1 % |
| Saltos de alta a baja o al revés (peor escenario) | 5,7 % | 4,3 % | 5,7 % |
| Tramos que cambian de clase entre trimestres | 38,3 % | 44,8 % | 36,3 % |
| Persistencia en prueba (NDCG / sensibilidad alta) | 0,979 / 0,865 | 0,967 / 0,673 | 0,976 / 0,808 |
| LambdaMART en prueba (NDCG / sensibilidad alta) | 0,967 / 0,859 | 0,975 / 0,692 | 0,972 / 0,821 |

(*) Con normalización por percentiles todos los indicadores quedan con distribución uniforme y los pesos de entropía salen iguales a los de caso base, así que ese escenario cumple de forma trivial: en rigor son 3 de 9. Además el índice se vuelve más inestable entre trimestres y la persistencia cae a una exactitud balanceada de 0,618. Por eso se descarta.

Configuración final del laboratorio: nivel del mar p95, normalización mínimo-máximo (`NORMALIZACION = "minmax"`). Con ella ningún modelo se distingue de la persistencia en la prueba (todos los intervalos de la diferencia incluyen el cero); LambdaMART la supera en sensibilidad de la clase alta (0,821 contra 0,808) y queda bajo en NDCG (0,972 contra 0,976). Con el nivel p95 aparece una tendencia significativa del nivel del mar en 27 de 40 tramos (mediana +1,9 cm por década), coherente con el alza del nivel medio.

## Marea astronómica como coincidencia con temporales (tercera corrida)

La marea no entra al índice como nivel (eso volvía a medir la geografía de la marea), sino como coincidencia: días del trimestre con temporal (Hs sobre el umbral o marejada ciclónica sobre el p95 del tramo) que caen en pleamar viva (pleamar diaria prevista sobre el p75 del tramo). Como la marea se conoce de antemano, los días de pleamar viva del trimestre siguiente entran también al modelo sin fuga de información. Se probaron dos formas:

| Indicador | Sin coincidencia | Coincidencia solo como entrada del modelo | Coincidencia como quinto indicador (configuración final) |
|---|---|---|---|
| Escenarios originales que cumplen | 3 de 10 | 3 de 10 | 4 de 10 (más 2 de 2 en el peso del nuevo indicador) |
| Peor escenario | 42,1 % | 42,1 % | 37,6 % |
| Saltos de alta a baja o al revés (peor) | 5,7 % | 5,7 % | 3,5 % |
| Persistencia en prueba (NDCG / sens. alta) | 0,976 / 0,808 | 0,976 / 0,808 | 0,972 / 0,840 |
| LambdaMART en prueba (NDCG / sens. alta) | 0,972 / 0,821 | 0,973 / 0,833 | 0,976 / 0,859 |
| ¿Supera a la persistencia en ambas en la prueba? | No | No | Sí (por poco; intervalos incluyen el cero) |
| ¿Supera en validación (criterio de selección)? | No | No | No (0,968 / 0,840 contra 0,972 / 0,846) |

Lectura: como quinto indicador, la coincidencia hace el índice algo más robusto y es la primera configuración en que LambdaMART supera a la persistencia en la prueba en las dos métricas de la Tabla 1. No alcanza para cambiar la decisión: el criterio se aplica en validación, donde la persistencia sigue arriba, y la diferencia no es estadísticamente significativa. Los umbrales de pleamar son relativos a cada tramo, así que el indicador mide coincidencia con la pleamar viva del propio tramo y no el nivel absoluto del agua. Los resultados de las otras dos formas quedan en `resultados/variantes/`.

## Qué queda pendiente

- Validación del índice con daños o eventos reales (necesita datos externos).
- Decidir si la versión del Capítulo 1 queda con corrientes sin marea (lab v2) o con la versión 1, y ajustar el texto de la sensibilidad según eso.
