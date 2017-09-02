CREATE EXTENSION POSTGIS;
CREATE TABLE cache_node (id INTEGER ,version INTEGER );
SELECT AddGeometryColumn ('public','cache_node','geom',4326,'POINT',2, false);
