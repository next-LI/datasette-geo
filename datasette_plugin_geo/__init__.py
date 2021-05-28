import json
from datasette import hookimpl
from .geojson import geojson_render
from .util import get_geo_column, from_spatialite_geom
from .inspect import get_spatial_tables, get_bounds
from .map_style import osm_raster

has_spatialite = False


@hookimpl
def prepare_connection(conn):
    global has_spatialite
    try:
        conn.execute('SELECT spatialite_version()').fetchall()
        has_spatialite = True
    except Exception:
        pass

    if not has_spatialite:
        print("WARNING: Spatialite is not loaded. datasette-geo will not work.")


@hookimpl
def extra_js_urls(template, database, table, datasette):
    if get_geo_column(datasette, database, table) is not None:
        return [
            {"url": "https://api.tiles.mapbox.com/mapbox-gl-js/v0.54.0/mapbox-gl.js"},
            {"url": "/-/static-plugins/datasette_plugin_geo/main.js"},
        ]
    else:
        return []


@hookimpl
def extra_css_urls(template, database, table, datasette):
    if get_geo_column(datasette, database, table) is not None:
        return [
            {"url": "https://api.tiles.mapbox.com/mapbox-gl-js/v0.54.0/mapbox-gl.css"},
            {"url": "/-/static-plugins/datasette_plugin_geo/main.css"},
        ]
    else:
        return []


@hookimpl
def extra_body_script(template, database, table, view_name, datasette):
    if has_spatialite and get_geo_column(datasette, database, table) is not None:
        config = datasette.plugin_config(
            "datasette-geo", database=database, table=table
        ) or {}

        bounds = datasette.inspect()[database]["geo"]["bounds"].get(table)
        if bounds is None:
            # No valid data here.
            return ""

        options = {
            "bounds": bounds,
            "database": database,
            "table": table,
            "view_name": view_name,
            "style": config.get("style", osm_raster),
            "mapbox_token": config.get("mapbox_token"),
        }
        return "geo_init_map({});".format(json.dumps(options))
    return ""


@hookimpl
def inspect(database, conn):
    spatial_tables = get_spatial_tables(conn)
    return {
        "geo": {
            "spatial_tables": spatial_tables,
            "bounds": get_bounds(conn, spatial_tables),
        }
    }


@hookimpl
def register_output_renderer(datasette):
    return {
        "extension": "geojson",
        "callback": lambda args, data, view_name: geojson_render(
            datasette, args, data, view_name
        ),
    }


@hookimpl
def render_cell(value, column, table, database, datasette):
    if get_geo_column(datasette, database, table) != column:
        return None
    geom = from_spatialite_geom(value)
    if geom is None:
        return "<null>"
    if geom.geom_type == "Point":
        return "{:.5}, {:.5}".format(geom.coords[0][0], geom.coords[0][1])
    else:
        return "<{}>".format(geom.geom_type)
