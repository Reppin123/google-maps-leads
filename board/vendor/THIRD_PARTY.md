# Third-party libraries bundled with the leads board

Inlined into the page at build time so a board works offline and as a single file.

| File | Library | Version | Licence |
|---|---|---|---|
| tabulator.min.js, tabulator.min.css | Tabulator, Oliver Folkerd | 6.3.1 | MIT |
| chart.umd.js | Chart.js | 4.4.7 | MIT |
| leaflet.js, leaflet.css | Leaflet, Volodymyr Agafonkin | 1.9.4 | BSD-2-Clause |
| markercluster.js, markercluster*.css | Leaflet.markercluster, Dave Leaver | 1.x | MIT |
| minisearch.js | MiniSearch, Luca Ongaro | see file | MIT |
| sortable.min.js | SortableJS | 1.15.6 | MIT |
| lz-string.min.js | lz-string, pieroxy | see file | MIT |
| au-states.geojson | Simplified Australian state outlines | - | derived from public boundary data |

Map tiles come from OpenStreetMap at view time (c) OpenStreetMap contributors, ODbL. Seed places for
searches come from GeoNames cities500 (CC BY 4.0), downloaded on first use into `scrape/data/`.
