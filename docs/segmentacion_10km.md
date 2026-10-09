# Segmentación de 10 km (9 de octubre de 2026)

El Capítulo 1 define tramos de aproximadamente 10 km. La versión anterior usaba 40 puntos equiespaciados (uno cada 5,8 km), con dos pares que compartían la celda de oleaje del reanálisis. Desde esta fecha el proyecto usa **23 tramos de 9,9 km** sobre la misma poligonal de la costa (226 km entre Ayamonte y Tarifa). La versión de 40 puntos queda en la rama `tramos-40`.

## Por qué 10 km

- **Resolución de los datos:** el reanálisis IBI tiene celdas de unos 3 km (0,027°). Con 10 km cada tramo tiene su propia celda de mar en los cuatro grupos de variables (23 celdas distintas de 23; distancia media celda-tramo 2 a 3 km, máxima 7,7 km).
- **Coherencia espacial de los temporales:** las variaciones trimestrales de oleaje, nivel del mar y días de temporal en pleamar viva tienen correlación de 0,95 o más entre tramos a 15-25 km. Dividir más fino no agrega información independiente. Solo las corrientes se diferencian a esa escala (0,66 a 15-25 km).
- **Escala de gestión:** las obras de emergencia de Costas se deciden por playa o frente urbano, y en la validación cada playa dañada queda a menos de 6 km del centro de su tramo.

## Cómo se armaron los datos

No hizo falta descargar de nuevo. Las cajas de la descarga anterior se solapan y cubren todo el litoral; `src/celdas_10km.py` toma para cada tramo nuevo la celda de mar más cercana entre todas ellas y guarda su serie en `data/raw/copernicus_10km/`. Después corre el flujo normal (procesar, marea, corrientes, marea prevista, validación y modelo).

## Cambios de método que acompañan

- **Primeros lugares del ranking:** NDCG y precisión se miden en la cuarta parte de los tramos (10 de 40 antes; 6 de 23 ahora), para que la exigencia sea la misma.
- **Regla de selección corregida:** un modelo reemplaza a la persistencia solo si la supera en validación en NDCG y en sensibilidad de la clase alta, como dice la Tabla 1. Antes se miraba solo NDCG; con 23 tramos eso habría elegido al SVM por una diferencia de 0,001 aunque su sensibilidad era mucho menor.

## Resultados: 40 puntos frente a 23 tramos de 10 km

| Resultado | 40 puntos | 23 tramos de 10 km |
|---|---|---|
| Pares tramo-trimestre | 4.000 | 2.300 |
| Escenarios originales de sensibilidad que cumplen | 4 de 10 | 3 de 10 |
| Saltos de alta a baja (peor escenario) | 3,5 % | 5,3 % |
| Tramos que cambian de clase entre trimestres | 37 % | 44 % |
| Persistencia en prueba (NDCG / sensibilidad alta) | 0,972 / 0,840 (primeros 10) | 0,959 / 0,646 (primeros 6) |
| LambdaMART en prueba (NDCG / sensibilidad alta) | 0,976 / 0,859 | 0,954 / 0,677 |
| LambdaMART, exactitud balanceada (persistencia) | 0,727 (0,750) | 0,635 (0,595) |
| Modelos frente a la persistencia | Empate estadístico | Empate estadístico |
| Daños: tramos dañados en prioridad alta | 41 % | 31 % (azar: 33 %) |
| Daños: percentil del trimestre en la historia del tramo | 86 | 86 |

## Lectura

Con tramos más largos, el contraste entre tramos baja: el semáforo relativo cambia más entre trimestres y la persistencia pierde fuerza (sensibilidad 0,646). LambdaMART la supera en exactitud balanceada y en sensibilidad de la clase alta, pero queda apenas bajo en NDCG y nada de esto es estadísticamente significativo, así que la persistencia sigue como referencia operativa. La validación con daños confirma lo mismo que antes: el índice detecta muy bien cuándo un tramo está en su peor momento (percentil 86 de su historia), pero no anticipa cuál tramo de la costa será el dañado. La segmentación de 10 km es la que dice el Capítulo 1 y la que se defiende mejor por resolución de datos; sus resultados más débiles en la parte relativa se informan como limitación.
