CREATE EXTENSION POSTGIS;
CREATE EXTENSION HSTORE;
CREATE TABLE cache_node (id INTEGER ,version INTEGER ,tags hstore);
SELECT AddGeometryColumn ('public','cache_node','geom',4326,'POINT',2, false);
